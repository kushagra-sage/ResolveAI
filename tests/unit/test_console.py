from fastapi.testclient import TestClient


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_console_surfaces_are_live_and_role_scoped(
    client: TestClient,
    admin_token: str,
    supervisor_token: str,
) -> None:
    admin_paths = ("models", "health", "settings")
    supervisor_paths = (
        "overview",
        "traces",
        "evaluations",
        "rag",
        "cost",
        "policies",
        "audit",
        "reports",
    )

    for path in admin_paths:
        response = client.get(f"/v1/console/{path}", headers=_headers(admin_token))
        assert response.status_code == 200, response.text
        assert isinstance(response.json(), dict)

    for path in supervisor_paths:
        response = client.get(f"/v1/console/{path}", headers=_headers(supervisor_token))
        assert response.status_code == 200, response.text
        assert isinstance(response.json(), dict)

    forbidden = client.get("/v1/console/settings", headers=_headers(supervisor_token))
    assert forbidden.status_code == 403


def test_customer_workspace_and_knowledge_inventory_use_seeded_data(
    client: TestClient,
    admin_token: str,
) -> None:
    headers = _headers(admin_token)
    customers = client.get("/v1/customers", headers=headers)
    assert customers.status_code == 200
    customer_id = customers.json()["customers"][0]["id"]

    workspace = client.get(f"/v1/customers/{customer_id}/workspace", headers=headers)
    assert workspace.status_code == 200
    assert workspace.json()["customer"]["id"] == customer_id
    assert set(workspace.json()) == {
        "customer",
        "orders",
        "payments",
        "shipments",
        "tickets",
        "messages",
        "refunds",
        "resolution_outcomes",
    }

    knowledge = client.get("/v1/knowledge/documents", headers=headers)
    assert knowledge.status_code == 200
    assert knowledge.json()["total"] == len(knowledge.json()["items"])
