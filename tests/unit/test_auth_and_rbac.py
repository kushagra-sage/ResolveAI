from datetime import timedelta

from conftest import make_token
from fastapi.testclient import TestClient
from resolveai.config import Settings
from resolveai.seed import seed_id


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_authenticated_identity_loads_roles_from_database(
    client: TestClient, customer_token: str
) -> None:
    response = client.get("/v1/me", headers=authorization(customer_token))

    assert response.status_code == 200
    body = response.json()
    assert body["roles"] == ["customer"]
    assert body["permissions"] == ["customer:read_own", "order:read_own"]
    assert body["customer_id"] == str(seed_id("customer:acme:demo"))


def test_missing_token_is_rejected(client: TestClient) -> None:
    response = client.get("/v1/me")

    assert response.status_code == 401


def test_expired_token_is_rejected(client: TestClient, settings: Settings) -> None:
    token = make_token(
        settings,
        user_id=seed_id("user:acme:customer"),
        tenant_id=seed_id("tenant:acme"),
        subject="demo-customer",
        expires_delta=timedelta(minutes=-1),
    )

    response = client.get("/v1/me", headers=authorization(token))

    assert response.status_code == 401


def test_customer_can_read_own_profile_and_orders(client: TestClient, customer_token: str) -> None:
    customer_id = seed_id("customer:acme:demo")

    profile = client.get(f"/v1/customers/{customer_id}", headers=authorization(customer_token))
    orders = client.get(
        f"/v1/customers/{customer_id}/orders", headers=authorization(customer_token)
    )

    assert profile.status_code == 200
    assert profile.json()["external_ref"] == "CUS-DEMO-001"
    assert orders.status_code == 200
    assert [order["external_ref"] for order in orders.json()] == ["ORD-DEMO-001"]


def test_customer_cannot_read_another_customer(client: TestClient, customer_token: str) -> None:
    other_customer_id = seed_id("customer:other:demo")

    response = client.get(
        f"/v1/customers/{other_customer_id}", headers=authorization(customer_token)
    )

    assert response.status_code == 403


def test_agent_permission_does_not_bypass_tenant_filter(
    client: TestClient, agent_token: str
) -> None:
    other_customer_id = seed_id("customer:other:demo")

    response = client.get(f"/v1/customers/{other_customer_id}", headers=authorization(agent_token))

    assert response.status_code == 404


def test_signed_tenant_claim_must_match_user_tenant(client: TestClient, settings: Settings) -> None:
    token = make_token(
        settings,
        user_id=seed_id("user:other:customer"),
        tenant_id=seed_id("tenant:acme"),
        subject="other-customer",
    )

    response = client.get("/v1/me", headers=authorization(token))

    assert response.status_code == 401
