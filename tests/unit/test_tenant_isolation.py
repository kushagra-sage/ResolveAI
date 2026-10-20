import uuid
from datetime import UTC, datetime

import pytest
from resolveai.context import tenant_scope
from resolveai.database import create_database_engine, create_session_factory
from resolveai.models import Customer, Order
from resolveai.seed import seed_id
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError


def test_orm_reads_are_automatically_tenant_scoped(database_url: str) -> None:
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)

    with tenant_scope(seed_id("tenant:acme")), factory() as session:
        customers = session.scalars(select(Customer)).all()

    external_refs = {customer.external_ref for customer in customers}
    assert "CUS-DEMO-001" in external_refs
    assert "CUS-OTHER-001" not in external_refs
    assert len(external_refs) == 12
    engine.dispose()


def test_tenant_scoped_write_rejects_context_mismatch(database_url: str) -> None:
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    mismatched = Customer(
        id=uuid.uuid4(),
        tenant_id=seed_id("tenant:other"),
        external_ref="INVALID-CROSS-TENANT",
        email="invalid@example.test",
        name="Invalid",
    )

    with tenant_scope(seed_id("tenant:acme")), factory() as session:
        session.add(mismatched)
        with pytest.raises(ValueError, match="active tenant"):
            session.flush()
        session.rollback()
    engine.dispose()


def test_composite_foreign_key_rejects_cross_tenant_parent(database_url: str) -> None:
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    invalid_order = Order(
        id=uuid.uuid4(),
        tenant_id=seed_id("tenant:other"),
        customer_id=seed_id("customer:acme:demo"),
        external_ref="INVALID-ORDER",
        status="created",
        currency="INR",
        subtotal_minor=100,
        tax_minor=0,
        shipping_minor=0,
        total_minor=100,
        placed_at=datetime.now(UTC),
    )

    with factory() as session:
        session.add(invalid_order)
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
    engine.dispose()


def test_negative_order_amount_is_rejected(database_url: str) -> None:
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    invalid_order = Order(
        id=uuid.uuid4(),
        tenant_id=seed_id("tenant:acme"),
        customer_id=seed_id("customer:acme:demo"),
        external_ref="NEGATIVE-ORDER",
        status="created",
        currency="INR",
        subtotal_minor=-1,
        tax_minor=0,
        shipping_minor=0,
        total_minor=-1,
        placed_at=datetime.now(UTC),
    )

    with factory() as session:
        session.add(invalid_order)
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
    engine.dispose()
