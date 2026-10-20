from resolveai.adapters.mock import MockPaymentAdapter
from resolveai.interfaces import AdapterConflict


def test_mock_payment_is_idempotent_and_detects_payload_conflicts() -> None:
    adapter = MockPaymentAdapter()
    values = {
        "tenant_id": "tenant-a",
        "payment_ref": "PAY-100",
        "amount_minor": 2500,
        "currency": "inr",
        "idempotency_key": "refund-key-100",
    }
    first = adapter.refund(**values)
    second = adapter.refund(**values)
    assert first["replayed"] is False
    assert second["replayed"] is True
    assert first["refund_ref"] == second["refund_ref"]
    try:
        adapter.refund(**{**values, "amount_minor": 2600})
    except AdapterConflict as exc:
        assert "different payload" in str(exc)
    else:
        raise AssertionError("idempotency payload conflict was accepted")


def test_integration_status_and_read_adapters_are_authenticated(
    client, admin_token: str
) -> None:
    assert client.get("/v1/integrations/status").status_code == 401
    response = client.get(
        "/v1/integrations/status", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "mock"
    assert all(item["available"] for item in payload["providers"].values())

    inventory = client.get(
        "/v1/integrations/erp/inventory/BLR-01/SKU-LAPTOP",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert inventory.status_code == 200
    assert inventory.json()["source"] == "mock-erp"
    assert inventory.json()["available_units"] > 0


def test_sandbox_adapter_endpoints_require_admin_and_replay(
    client, admin_token: str, agent_token: str
) -> None:
    payload = {
        "payment_ref": "PAY-DEMO-001",
        "amount_minor": 1400,
        "currency": "INR",
        "idempotency_key": "adapter-refund-demo-001",
    }
    forbidden = client.post(
        "/v1/integrations/sandbox/payments/refunds",
        headers={"Authorization": f"Bearer {agent_token}"},
        json=payload,
    )
    assert forbidden.status_code == 403
    headers = {"Authorization": f"Bearer {admin_token}"}
    first = client.post(
        "/v1/integrations/sandbox/payments/refunds", headers=headers, json=payload
    )
    second = client.post(
        "/v1/integrations/sandbox/payments/refunds", headers=headers, json=payload
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["replayed"] is False
    assert second.json()["replayed"] is True
    assert first.json()["refund_ref"] == second.json()["refund_ref"]


def test_adapter_failure_modes_are_normalized(client, admin_token: str) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    timed_out = client.get(
        "/v1/integrations/shipments/timeout-case", headers=headers
    )
    unavailable = client.get(
        "/v1/integrations/wms/fulfillments/upstream-error", headers=headers
    )
    assert timed_out.status_code == 504
    assert unavailable.status_code == 503


def test_deterministic_model_requires_no_provider_key(client, admin_token: str) -> None:
    response = client.post(
        "/v1/integrations/sandbox/model/completions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"prompt": "Summarize the delayed refund case without PII."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "deterministic"
    assert payload["model"] == "resolveai-deterministic-v1"
    assert len(payload["prompt_sha256"]) == 64
