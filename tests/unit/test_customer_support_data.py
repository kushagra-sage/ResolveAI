from fastapi.testclient import TestClient
from resolveai.database import create_database_engine, create_session_factory
from resolveai.models import Customer, CustomerSignal, SupportTicket, TicketMessage
from resolveai.seed import seed_database, seed_id
from sqlalchemy import func, select


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_agent_can_read_synthetic_customer_support_overview(
    client: TestClient, agent_token: str
) -> None:
    response = client.get("/v1/customers", headers=_headers(agent_token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_source"] == "synthetic-support-v1"
    assert payload["contains_real_pii"] is False
    assert payload["customer_count"] == 12
    assert payload["ticket_count"] == 12
    assert payload["open_ticket_count"] == 8
    assert len({customer["external_ref"] for customer in payload["customers"]}) == 12
    assert all(customer["ticket_count"] == 1 for customer in payload["customers"])
    assert all(customer["order_count"] == 1 for customer in payload["customers"])


def test_customer_cannot_list_tenant_support_workload(
    client: TestClient, customer_token: str
) -> None:
    response = client.get("/v1/customers", headers=_headers(customer_token))

    assert response.status_code == 403


def test_synthetic_support_seed_is_deterministic_and_idempotent(database_url: str) -> None:
    seed_database(database_url)
    seed_database(database_url)
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)

    with factory() as session:
        session.info["tenant_id"] = seed_id("tenant:acme")
        assert session.scalar(select(func.count()).select_from(Customer)) == 12
        assert session.scalar(select(func.count()).select_from(SupportTicket)) == 12
        assert session.scalar(select(func.count()).select_from(TicketMessage)) == 24
        assert session.scalar(select(func.count()).select_from(CustomerSignal)) == 12

    engine.dispose()
