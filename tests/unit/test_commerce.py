from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from resolveai.commerce import robust_deviation
from resolveai.database import create_database_engine, create_session_factory
from resolveai.detector_worker import run_due_once
from resolveai.models import CustomerSignal, DetectorSchedule
from resolveai.seed import seed_id
from sqlalchemy import select


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signal_payload(occurred_at: datetime, *, store_id: str = "STORE-1") -> dict[str, object]:
    return {
        "store_id": store_id,
        "sku_id": "SKU-DEMO-1",
        "category": "DELIVERY_DELAY",
        "severity": "HIGH",
        "confidence": 0.93,
        "occurred_at": occurred_at.isoformat(),
        "source": "synthetic-test-fixture",
        "evidence": {"carrier": "DemoShip", "late_minutes": 90},
        "rule_version": "fixture-v1",
    }


def test_robust_deviation_is_deterministic_with_zero_mad_fallback() -> None:
    center, mad, score = robust_deviation([1, 1, 1, 1], 8)
    assert center == 1
    assert mad == 0
    assert score == 4.949747


def test_customer_cannot_access_commerce_signal_api(
    client: TestClient, customer_token: str
) -> None:
    response = client.get("/v1/customer-signals", headers=_headers(customer_token))
    assert response.status_code == 403


def test_commerce_workflow_is_tenant_scoped_explainable_and_auditable(
    client: TestClient,
    admin_token: str,
    database_url: str,
) -> None:
    window_end = datetime(2026, 10, 5, 12, tzinfo=UTC)
    initial_overview_response = client.get("/v1/commerce/overview", headers=_headers(admin_token))
    assert initial_overview_response.status_code == 200
    initial_overview = initial_overview_response.json()
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    with factory() as session:
        other_tenant = seed_id("tenant:other")
        session.info["tenant_id"] = other_tenant
        session.add(
            CustomerSignal(
                tenant_id=other_tenant,
                store_id="OTHER-STORE",
                sku_id="OTHER-SKU",
                category="DELIVERY_DELAY",
                severity="CRITICAL",
                confidence=1.0,
                occurred_at=window_end - timedelta(minutes=10),
                source="cross-tenant-fixture",
                evidence_json={},
            )
        )
        session.commit()
    engine.dispose()

    for offset in (270, 210, 150, 90):
        response = client.post(
            "/v1/customer-signals",
            json=_signal_payload(window_end - timedelta(minutes=offset)),
            headers=_headers(admin_token),
        )
        assert response.status_code == 201
    for minute in range(8):
        response = client.post(
            "/v1/customer-signals",
            json=_signal_payload(window_end - timedelta(minutes=minute + 1)),
            headers=_headers(admin_token),
        )
        assert response.status_code == 201

    listing = client.get("/v1/customer-signals", headers=_headers(admin_token))
    assert listing.status_code == 200
    assert len(listing.json()) == initial_overview["signal_count"] + 12
    assert all(item["store_id"] != "OTHER-STORE" for item in listing.json())

    detected = client.post(
        "/v1/commerce/anomalies/detect",
        json={
            "category": "DELIVERY_DELAY",
            "entity_type": "TENANT",
            "entity_id": "ALL",
            "window_end": window_end.isoformat(),
            "window_minutes": 60,
            "baseline_windows": 4,
            "minimum_support": 4,
            "threshold": 3.5,
        },
        headers=_headers(admin_token),
    )
    assert detected.status_code == 200
    detection = detected.json()
    assert detection["state"] == "ANOMALY_CREATED"
    assert detection["baseline_counts"] == [1, 1, 1, 1]
    assert detection["observed_count"] == 8
    assert detection["anomaly"]["explanation"]["formula"].startswith("robust_z=")

    anomaly_id = detection["anomaly"]["id"]
    investigated = client.post(
        "/v1/commerce/investigations",
        json={"anomaly_id": anomaly_id},
        headers=_headers(admin_token),
    )
    assert investigated.status_code == 200
    hypotheses = investigated.json()
    assert hypotheses[0]["status"] == "SUPPORTED"
    assert hypotheses[0]["cause_code"] in {"STORE_CONCENTRATION", "SKU_CONCENTRATION"}

    recommended = client.post(
        "/v1/commerce/recommended-actions",
        json={
            "anomaly_id": anomaly_id,
            "hypothesis_id": hypotheses[0]["id"],
            "action_type": "create_ticket",
            "parameters": {"team": "delivery-operations", "priority": "high"},
            "expected_impact": {"metric": "delivery_delay_signals", "direction": "decrease"},
        },
        headers=_headers(admin_token),
    )
    assert recommended.status_code == 201
    recommendation = recommended.json()
    assert recommendation["policy_decision"] == "ALLOW"
    assert recommendation["status"] == "PROPOSED"
    assert len(recommendation["action_digest"]) == 64

    outcome = client.post(
        "/v1/commerce/action-outcomes",
        json={
            "recommended_action_id": recommendation["id"],
            "target_metric": "delivery_delay_signals",
            "before_window_start": (window_end - timedelta(hours=1)).isoformat(),
            "before_window_end": window_end.isoformat(),
            "before_value": 8,
            "after_window_start": window_end.isoformat(),
            "after_window_end": (window_end + timedelta(hours=1)).isoformat(),
            "after_value": 3,
            "confidence": 0.8,
        },
        headers=_headers(admin_token),
    )
    assert outcome.status_code == 201
    assert outcome.json()["status"] == "MEASURED"
    assert outcome.json()["effect_estimate"] == -5
    assert "causal attribution" in outcome.json()["limitations"][-1]

    overview = client.get("/v1/commerce/overview", headers=_headers(admin_token))
    assert overview.status_code == 200
    overview_body = overview.json()
    assert overview_body["signal_count"] == initial_overview["signal_count"] + 12
    assert overview_body["open_anomaly_count"] == initial_overview["open_anomaly_count"] + 1
    assert (
        overview_body["supported_hypothesis_count"]
        == initial_overview["supported_hypothesis_count"] + 2
    )
    assert overview_body["pending_action_count"] == initial_overview["pending_action_count"] + 1
    assert overview_body["measured_outcome_count"] == initial_overview["measured_outcome_count"] + 1
    assert overview_body["signals_by_category"]["DELIVERY_DELAY"] == (
        initial_overview["signals_by_category"].get("DELIVERY_DELAY", 0) + 12
    )

    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    with factory() as session:
        session.info["tenant_id"] = seed_id("tenant:other")
        rows = session.scalars(select(CustomerSignal)).all()
        assert len(rows) == 1
        assert rows[0].store_id == "OTHER-STORE"
    engine.dispose()


def test_detection_reports_insufficient_evidence(
    client: TestClient,
    admin_token: str,
) -> None:
    response = client.post(
        "/v1/commerce/anomalies/detect",
        json={
            "category": "PAYMENT_FAILURE",
            "window_end": "2026-10-05T12:00:00Z",
            "baseline_windows": 4,
            "minimum_support": 5,
        },
        headers=_headers(admin_token),
    )
    assert response.status_code == 200
    assert response.json()["state"] == "INSUFFICIENT_EVIDENCE"
    assert response.json()["anomaly"] is None


def test_operational_facts_risk_apis_and_detector_evaluation(
    client: TestClient,
    admin_token: str,
) -> None:
    headers = _headers(admin_token)
    now = datetime.now(tz=UTC)
    assert (
        client.post(
            "/v1/commerce/stores",
            json={
                "external_ref": "BLR-WH-01",
                "name": "Bengaluru Warehouse",
                "region": "South",
                "capacity_units": 1000,
            },
            headers=headers,
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/v1/commerce/skus",
            json={
                "external_ref": "SKU-RISK-1",
                "name": "Risk Fixture",
                "category": "accessories",
            },
            headers=headers,
        ).status_code
        == 201
    )
    inventory = client.post(
        "/v1/commerce/inventory-snapshots",
        json={
            "store_ref": "BLR-WH-01",
            "sku_ref": "SKU-RISK-1",
            "on_hand_units": 4,
            "reserved_units": 2,
            "reorder_point_units": 5,
            "observed_at": now.isoformat(),
            "source": "fixture-erp",
        },
        headers=headers,
    )
    assert inventory.status_code == 201
    for event_type in ("FAILED", "DELIVERED"):
        response = client.post(
            "/v1/commerce/fulfillment-events",
            json={
                "order_ref": f"ORD-{event_type}",
                "store_ref": "BLR-WH-01",
                "sku_ref": "SKU-RISK-1",
                "event_type": event_type,
                "occurred_at": now.isoformat(),
                "source": "fixture-wms",
            },
            headers=headers,
        )
        assert response.status_code == 201
    quality = client.post(
        "/v1/commerce/quality-reports",
        json={
            "sku_ref": "SKU-RISK-1",
            "defect_type": "unstable hinge",
            "severity": "HIGH",
            "affected_units": 3,
            "reported_at": now.isoformat(),
            "source": "fixture-quality",
        },
        headers=headers,
    )
    assert quality.status_code == 201

    inventory_risk = client.get("/v1/commerce/inventory-risk", headers=headers).json()
    delivery_risk = client.get("/v1/commerce/delivery-risk", headers=headers).json()
    product_quality = client.get("/v1/commerce/product-quality", headers=headers).json()
    assert inventory_risk[0]["risk_level"] == "HIGH"
    assert inventory_risk[0]["available_units"] == 2
    assert delivery_risk[0]["risk_level"] == "CRITICAL"
    assert delivery_risk[0]["risk_rate"] == 0.5
    assert product_quality[0]["risk_level"] == "HIGH"

    evaluation = client.post(
        "/v1/commerce/detectors/evaluate",
        json={
            "detector": "robust_z",
            "threshold": 3.5,
            "minimum_support": 4,
            "cases": [
                {
                    "case_key": "spike",
                    "baseline_counts": [1, 1, 1, 1],
                    "observed_count": 8,
                    "expected_anomaly": True,
                },
                {
                    "case_key": "normal",
                    "baseline_counts": [2, 2, 2, 2],
                    "observed_count": 2,
                    "expected_anomaly": False,
                },
            ],
        },
        headers=headers,
    )
    assert evaluation.status_code == 201
    assert evaluation.json()["precision"] == 1
    assert evaluation.json()["recall"] == 1

    schedule = client.post(
        "/v1/commerce/detector-schedules",
        json={
            "name": "hourly-delivery-delay",
            "detector": "ewma",
            "category": "DELIVERY_DELAY",
            "interval_minutes": 60,
        },
        headers=headers,
    )
    assert schedule.status_code == 201
    due = client.post("/v1/commerce/detector-schedules/run-due", headers=headers)
    assert due.status_code == 200
    assert due.json()[0]["state"] == "INSUFFICIENT_EVIDENCE"


def test_high_impact_commerce_action_uses_human_approval_and_idempotent_execution(
    client: TestClient,
    admin_token: str,
    supervisor_token: str,
) -> None:
    admin_headers = _headers(admin_token)
    supervisor_headers = _headers(supervisor_token)
    now = datetime.now(tz=UTC)
    batch = client.post(
        "/v1/commerce/product-batches",
        json={
            "batch_ref": "BATCH-RISK-1",
            "sku_ref": "SKU-RISK-1",
            "produced_at": now.isoformat(),
            "units_produced": 50,
        },
        headers=admin_headers,
    )
    assert batch.status_code == 201
    recommendation = client.post(
        "/v1/commerce/recommended-actions",
        json={
            "action_type": "quarantine_batch",
            "parameters": {"batch_ref": "BATCH-RISK-1"},
            "expected_impact": {"metric": "quality_reports", "direction": "decrease"},
        },
        headers=admin_headers,
    )
    assert recommendation.status_code == 201
    body = recommendation.json()
    assert body["policy_decision"] == "REQUIRE_APPROVAL"
    assert body["status"] == "APPROVAL_REQUIRED"
    approval_id = body["approval_request_id"]
    assert approval_id is not None

    same_actor = client.post(
        f"/v1/approvals/{approval_id}/decision",
        json={"decision": "APPROVE", "reason": "Attempting self approval"},
        headers=admin_headers,
    )
    assert same_actor.status_code == 403
    approved = client.post(
        f"/v1/approvals/{approval_id}/decision",
        json={"decision": "APPROVE", "reason": "Verified quality evidence"},
        headers=supervisor_headers,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    actions = client.get("/v1/commerce/recommended-actions", headers=admin_headers).json()
    assert actions[0]["status"] == "EXECUTED"
    replay = client.post(
        f"/v1/commerce/recommended-actions/{body['id']}/execute",
        headers=admin_headers,
    )
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True


def test_detector_worker_claims_due_schedules(database_url: str) -> None:
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    tenant_id = seed_id("tenant:acme")
    now = datetime(2026, 10, 6, 8, tzinfo=UTC)
    with factory() as session:
        session.info["tenant_id"] = tenant_id
        session.add(
            DetectorSchedule(
                tenant_id=tenant_id,
                name="worker-fixture",
                detector_name="rate_change",
                category="PAYMENT_FAILURE",
                entity_type="TENANT",
                entity_id="ALL",
                configuration_json={
                    "window_minutes": 60,
                    "baseline_windows": 4,
                    "minimum_support": 5,
                    "threshold": 3.5,
                },
                enabled=True,
                interval_minutes=60,
                next_run_at=now - timedelta(minutes=1),
            )
        )
        session.commit()
    assert run_due_once(factory, now=now) == (1, 0)
    with factory() as session:
        session.info["tenant_id"] = tenant_id
        schedule = session.scalar(
            select(DetectorSchedule).where(DetectorSchedule.name == "worker-fixture")
        )
        assert schedule is not None
        assert schedule.last_run_at is not None
        assert schedule.next_run_at.replace(tzinfo=UTC) == now + timedelta(hours=1)
    engine.dispose()
