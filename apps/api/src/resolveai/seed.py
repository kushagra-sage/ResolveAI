import uuid
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from sqlalchemy import select

from resolveai.config import get_settings
from resolveai.database import create_database_engine, create_session_factory
from resolveai.models import (
    Customer,
    CustomerSignal,
    Order,
    OrderItem,
    Payment,
    Permission,
    RagVersion,
    Role,
    RolePermission,
    Shipment,
    SupportAgent,
    SupportTicket,
    Tenant,
    TicketMessage,
    User,
    UserRole,
)
from resolveai.synthetic_support import SYNTHETIC_SUPPORT_CASES

SEED_NAMESPACE = uuid.UUID("431ab04d-b6c5-4d60-91bf-dbd4b9a779a4")


def seed_id(value: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, value)


def seed_database(database_url: str) -> None:
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    placed_at = datetime(2026, 9, 25, 10, 30, tzinfo=UTC)

    tenants = [
        Tenant(id=seed_id("tenant:acme"), slug="acme-demo", name="Acme Commerce"),
        Tenant(id=seed_id("tenant:other"), slug="other-demo", name="Other Commerce"),
    ]
    permissions = [
        Permission(
            id=seed_id("permission:customer:read_own"),
            code="customer:read_own",
            resource="customer",
            action="read_own",
            description="Read the caller's own customer profile",
        ),
        Permission(
            id=seed_id("permission:order:read_own"),
            code="order:read_own",
            resource="order",
            action="read_own",
            description="Read the caller's own orders",
        ),
        Permission(
            id=seed_id("permission:customer:read"),
            code="customer:read",
            resource="customer",
            action="read",
            description="Read tenant-scoped customer profiles",
        ),
        Permission(
            id=seed_id("permission:order:read"),
            code="order:read",
            resource="order",
            action="read",
            description="Read tenant-scoped orders",
        ),
        Permission(
            id=seed_id("permission:approval:review"),
            code="approval:review",
            resource="approval",
            action="review",
            description="Review approval requests",
        ),
        Permission(
            id=seed_id("permission:tenant:admin"),
            code="tenant:admin",
            resource="tenant",
            action="admin",
            description="Administer tenant configuration",
        ),
        Permission(
            id=seed_id("permission:knowledge:read"),
            code="knowledge:read",
            resource="knowledge",
            action="read",
            description="Search tenant knowledge",
        ),
        Permission(
            id=seed_id("permission:knowledge:write"),
            code="knowledge:write",
            resource="knowledge",
            action="write",
            description="Ingest tenant knowledge",
        ),
        Permission(
            id=seed_id("permission:commerce:read"),
            code="commerce:read",
            resource="commerce",
            action="read",
            description="Read tenant-scoped commerce intelligence",
        ),
        Permission(
            id=seed_id("permission:commerce:write"),
            code="commerce:write",
            resource="commerce",
            action="write",
            description="Ingest tenant-scoped commerce signals and metrics",
        ),
        Permission(
            id=seed_id("permission:commerce:investigate"),
            code="commerce:investigate",
            resource="commerce",
            action="investigate",
            description="Run detectors and create governed commerce recommendations",
        ),
    ]

    with factory() as session:
        for tenant in tenants:
            session.merge(tenant)
        for permission in permissions:
            session.merge(permission)
        session.flush()

        for tenant in tenants:
            role_permissions = {
                "customer": ["customer:read_own", "order:read_own"],
                "support_agent": [
                    "customer:read",
                    "order:read",
                    "knowledge:read",
                    "commerce:read",
                    "commerce:write",
                ],
                "service_principal": ["knowledge:read", "commerce:write"],
                "supervisor": [
                    "customer:read",
                    "order:read",
                    "approval:review",
                    "knowledge:read",
                    "commerce:read",
                    "commerce:investigate",
                ],
                "admin": [
                    "customer:read",
                    "order:read",
                    "approval:review",
                    "tenant:admin",
                    "knowledge:read",
                    "knowledge:write",
                    "commerce:read",
                    "commerce:write",
                    "commerce:investigate",
                ],
            }
            for role_name, permission_codes in role_permissions.items():
                role = Role(
                    id=seed_id(f"role:{tenant.slug}:{role_name}"),
                    tenant_id=tenant.id,
                    name=role_name,
                    description=f"Seeded {role_name} role",
                )
                session.merge(role)
                session.flush()
                for code in permission_codes:
                    session.merge(
                        RolePermission(
                            tenant_id=tenant.id,
                            role_id=role.id,
                            permission_id=seed_id(f"permission:{code}"),
                        )
                    )
            session.merge(
                RagVersion(
                    id=seed_id(f"rag:{tenant.slug}:v001"),
                    tenant_id=tenant.id,
                    name="rag_v001",
                    chunker="heading_aware",
                    chunk_size=120,
                    chunk_overlap=20,
                    embedding_model="deterministic-hash-v1",
                    embedding_dimensions=384,
                    minimum_relevance=0.05,
                    config_json={
                        "retriever": "hybrid_rrf",
                        "dense_top_k": 20,
                        "keyword_top_k": 20,
                        "rerank_top_n": 5,
                    },
                )
            )
        session.flush()

        acme_id = seed_id("tenant:acme")
        customer_user = User(
            id=seed_id("user:acme:customer"),
            tenant_id=acme_id,
            external_subject="demo-customer",
            email="customer@example.test",
            display_name="Demo Customer",
        )
        agent_user = User(
            id=seed_id("user:acme:agent"),
            tenant_id=acme_id,
            external_subject="demo-agent",
            email="agent@example.test",
            display_name="Demo Support Agent",
        )
        admin_user = User(
            id=seed_id("user:acme:admin"),
            tenant_id=acme_id,
            external_subject="demo-admin",
            email="admin@example.test",
            display_name="Demo Administrator",
        )
        supervisor_user = User(
            id=seed_id("user:acme:supervisor"),
            tenant_id=acme_id,
            external_subject="demo-supervisor",
            email="supervisor@example.test",
            display_name="Demo Supervisor",
        )
        service_user = User(
            id=seed_id("user:acme:service_principal"),
            tenant_id=acme_id,
            external_subject="service-account-resolveai-service",
            email="resolveai-service@example.test",
            display_name="ResolveAI Local Service Principal",
        )
        session.merge(customer_user)
        session.merge(agent_user)
        session.merge(admin_user)
        session.merge(supervisor_user)
        session.merge(service_user)
        session.flush()
        session.merge(
            SupportAgent(
                id=seed_id("agent:acme:demo"),
                tenant_id=acme_id,
                user_id=agent_user.id,
                team="general",
            )
        )
        session.merge(
            UserRole(
                tenant_id=acme_id,
                user_id=customer_user.id,
                role_id=seed_id("role:acme-demo:customer"),
            )
        )
        session.merge(
            UserRole(
                tenant_id=acme_id,
                user_id=supervisor_user.id,
                role_id=seed_id("role:acme-demo:supervisor"),
            )
        )
        session.merge(
            UserRole(
                tenant_id=acme_id,
                user_id=admin_user.id,
                role_id=seed_id("role:acme-demo:admin"),
            )
        )
        session.merge(
            UserRole(
                tenant_id=acme_id,
                user_id=agent_user.id,
                role_id=seed_id("role:acme-demo:support_agent"),
            )
        )
        session.merge(
            UserRole(
                tenant_id=acme_id,
                user_id=service_user.id,
                role_id=seed_id("role:acme-demo:service_principal"),
            )
        )
        session.flush()
        customer = Customer(
            id=seed_id("customer:acme:demo"),
            tenant_id=acme_id,
            external_ref="CUS-DEMO-001",
            user_id=customer_user.id,
            email=customer_user.email,
            name=customer_user.display_name,
            locale="en-IN",
        )
        session.merge(customer)
        session.flush()
        order = Order(
            id=seed_id("order:acme:demo"),
            tenant_id=acme_id,
            customer_id=customer.id,
            external_ref="ORD-DEMO-001",
            status="shipped",
            currency="INR",
            subtotal_minor=200000,
            tax_minor=36000,
            shipping_minor=0,
            total_minor=236000,
            placed_at=placed_at,
        )
        session.merge(order)
        session.flush()
        session.merge(
            OrderItem(
                id=seed_id("item:acme:demo"),
                tenant_id=acme_id,
                order_id=order.id,
                sku="LAPTOP-STAND-01",
                name="Aluminium Laptop Stand",
                quantity=1,
                unit_price_minor=200000,
                total_minor=200000,
            )
        )
        session.merge(
            Shipment(
                id=seed_id("shipment:acme:demo"),
                tenant_id=acme_id,
                order_id=order.id,
                carrier="DemoShip",
                tracking_number="DEMO123456789",
                status="in_transit",
            )
        )
        session.merge(
            Payment(
                id=seed_id("payment:acme:demo"),
                tenant_id=acme_id,
                order_id=order.id,
                provider="sandbox",
                provider_payment_ref="PAY-DEMO-001",
                status="captured",
                amount_minor=236000,
                currency="INR",
                method_type="card",
                method_fingerprint="demo-fingerprint-not-a-pan",
            )
        )

        support_agent_id = seed_id("agent:acme:demo")
        support_start = datetime(2026, 9, 26, 8, 0, tzinfo=UTC)
        for index, support_case in enumerate(SYNTHETIC_SUPPORT_CASES, start=1):
            customer_id = (
                customer.id
                if support_case.key == "demo"
                else seed_id(f"customer:acme:synthetic:{support_case.key}")
            )
            if support_case.key != "demo":
                session.merge(
                    Customer(
                        id=customer_id,
                        tenant_id=acme_id,
                        external_ref=f"CUS-SYN-{index:03d}",
                        user_id=None,
                        email=support_case.email,
                        name=support_case.name,
                        locale=support_case.locale,
                        status="active",
                    )
                )
                session.flush()

            order_id = (
                order.id
                if support_case.key == "demo"
                else seed_id(f"order:acme:synthetic:{support_case.key}")
            )
            activity_at = support_start + timedelta(hours=index * 11)
            if support_case.key != "demo":
                session.merge(
                    Order(
                        id=order_id,
                        tenant_id=acme_id,
                        customer_id=customer_id,
                        external_ref=f"ORD-SYN-{index:03d}",
                        status=support_case.order_status,
                        currency="INR",
                        subtotal_minor=support_case.total_minor,
                        tax_minor=0,
                        shipping_minor=0,
                        total_minor=support_case.total_minor,
                        placed_at=activity_at - timedelta(days=5),
                    )
                )
                session.flush()

            ticket_id = seed_id(f"ticket:acme:synthetic:{support_case.key}")
            session.merge(
                SupportTicket(
                    id=ticket_id,
                    tenant_id=acme_id,
                    customer_id=customer_id,
                    external_ref=f"TKT-SYN-{index:03d}",
                    subject=support_case.subject,
                    status=support_case.ticket_status,
                    priority=support_case.priority,
                    assigned_agent_id=support_agent_id,
                    created_at=activity_at,
                    updated_at=activity_at + timedelta(hours=2),
                )
            )
            session.flush()

            messages = (
                ("customer", "inbound", support_case.customer_message, activity_at),
                (
                    "agent",
                    "outbound",
                    support_case.agent_message,
                    activity_at + timedelta(hours=2),
                ),
            )
            for message_index, (author, direction, body, created_at) in enumerate(
                messages, start=1
            ):
                session.merge(
                    TicketMessage(
                        id=seed_id(
                            f"message:acme:synthetic:{support_case.key}:{message_index}"
                        ),
                        tenant_id=acme_id,
                        ticket_id=ticket_id,
                        author_type=author,
                        direction=direction,
                        body=body,
                        body_sha256=sha256(body.encode()).hexdigest(),
                        created_at=created_at,
                        updated_at=created_at,
                    )
                )

            session.merge(
                CustomerSignal(
                    id=seed_id(f"signal:acme:synthetic:{support_case.key}"),
                    tenant_id=acme_id,
                    ticket_id=ticket_id,
                    customer_id=customer_id,
                    order_id=order_id,
                    store_id="BLR-DEMO-01",
                    sku_id=support_case.sku,
                    category=support_case.signal_category,
                    severity=support_case.severity,
                    confidence=round(0.82 + (index % 5) * 0.03, 2),
                    occurred_at=activity_at,
                    source="synthetic-support-v1",
                    evidence_json={
                        "ticket_ref": f"TKT-SYN-{index:03d}",
                        "synthetic": True,
                        "contains_real_pii": False,
                    },
                    model_version="deterministic-support-v1",
                    rule_version="synthetic-fixture-v1",
                    created_at=activity_at,
                    updated_at=activity_at,
                )
            )

        other_id = seed_id("tenant:other")
        other_user = User(
            id=seed_id("user:other:customer"),
            tenant_id=other_id,
            external_subject="other-customer",
            email="other@example.test",
            display_name="Other Customer",
        )
        session.merge(other_user)
        session.flush()
        session.merge(
            UserRole(
                tenant_id=other_id,
                user_id=other_user.id,
                role_id=seed_id("role:other-demo:customer"),
            )
        )
        session.flush()
        session.merge(
            Customer(
                id=seed_id("customer:other:demo"),
                tenant_id=other_id,
                external_ref="CUS-OTHER-001",
                user_id=other_user.id,
                email=other_user.email,
                name=other_user.display_name,
            )
        )
        session.commit()

        count = session.scalar(select(Tenant.id).limit(1))
        if count is None:
            raise RuntimeError("seed verification failed")
    engine.dispose()


def main() -> None:
    settings = get_settings()
    seed_database(settings.alembic_database_url)
    print("ResolveAI synthetic seed data loaded.")


if __name__ == "__main__":
    main()
