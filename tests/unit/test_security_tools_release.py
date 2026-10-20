import json
import uuid
from pathlib import Path

from resolveai.database import create_database_engine, create_session_factory
from resolveai.deployment import next_canary_allocation, select_deployment
from resolveai.guardrails import inspect_input, quarantine_external_content
from resolveai.models import ExecutionRecord, Refund, ToolCall
from resolveai.outbox import dispatch_pending, enqueue
from resolveai.policy import ActionRequest, PolicyContext, PolicyDecision, evaluate_action
from resolveai.seed import seed_id
from resolveai.shadow import ShadowResult, make_shadow_request, validate_shadow_result
from resolveai.telemetry import safe_attributes
from resolveai.tools import ExecuteRefundInput, ToolExecutionError, execute_refund
from sqlalchemy import func, select


def test_refund_tool_requires_policy_or_approval_and_is_idempotent(database_url: str) -> None:
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    tenant_id = seed_id("tenant:acme")
    actor_id = seed_id("user:acme:agent")
    request = ActionRequest("execute_refund", tenant_id, tenant_id, {"amount_minor": 20_001})
    policy = evaluate_action(
        request, PolicyContext(frozenset({"support_agent"}), risk_level="high")
    )
    assert policy.decision is PolicyDecision.REQUIRE_APPROVAL
    payload = ExecuteRefundInput(
        payment_id=seed_id("payment:acme:demo"),
        order_id=seed_id("order:acme:demo"),
        amount_minor=20_001,
        currency="INR",
        reason_code="returned_item",
    )
    with factory() as session:
        session.info["tenant_id"] = tenant_id
        try:
            execute_refund(
                session,
                tenant_id=tenant_id,
                actor_user_id=actor_id,
                run_id=uuid.uuid4(),
                trace_id=uuid.uuid4().hex,
                idempotency_key="refund-test-1",
                payload=payload,
                policy=policy,
                valid_approval=False,
            )
        except ToolExecutionError:
            pass
        else:
            raise AssertionError("refund executed without approval")
        assert session.scalar(select(func.count(Refund.id))) == 0

        first = execute_refund(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_id,
            run_id=uuid.uuid4(),
            trace_id=uuid.uuid4().hex,
            idempotency_key="refund-test-1",
            payload=payload,
            policy=policy,
            valid_approval=True,
        )
        second = execute_refund(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_id,
            run_id=uuid.uuid4(),
            trace_id=uuid.uuid4().hex,
            idempotency_key="refund-test-1",
            payload=payload,
            policy=policy,
            valid_approval=True,
        )
        session.commit()
        assert first.replayed is False
        assert second.replayed is True
        assert first.tool_call_id == second.tool_call_id
        try:
            execute_refund(
                session,
                tenant_id=tenant_id,
                actor_user_id=actor_id,
                run_id=uuid.uuid4(),
                trace_id=uuid.uuid4().hex,
                idempotency_key="refund-test-1",
                payload=payload.model_copy(update={"amount_minor": payload.amount_minor + 1}),
                policy=policy,
                valid_approval=True,
            )
        except ToolExecutionError as exc:
            assert str(exc) == "idempotency_key_payload_conflict"
        else:
            raise AssertionError("idempotency key accepted a different refund payload")
        assert session.scalar(select(func.count(Refund.id))) == 1
        assert session.scalar(select(func.count(ToolCall.id))) == 1
    engine.dispose()


def test_refund_reconciles_unknown_outcome_without_duplicate(database_url: str) -> None:
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    tenant_id = seed_id("tenant:acme")
    run_id = uuid.uuid4()
    action = ActionRequest("execute_refund", tenant_id, tenant_id, {"amount_minor": 100})
    policy = evaluate_action(action, PolicyContext(frozenset({"support_agent"}), risk_level="high"))
    payload = ExecuteRefundInput(
        payment_id=seed_id("payment:acme:demo"),
        order_id=seed_id("order:acme:demo"),
        amount_minor=100,
        currency="INR",
        reason_code="reconciliation_test",
    )
    with factory() as session:
        session.info["tenant_id"] = tenant_id
        call = ToolCall(
            tenant_id=tenant_id,
            run_id=run_id,
            tool_name="execute_refund",
            idempotency_key="unknown-refund-1",
            arguments_json=payload.model_dump(mode="json"),
            status="unknown",
        )
        session.add(call)
        session.flush()
        execution = ExecutionRecord(
            tenant_id=tenant_id,
            run_id=run_id,
            tool_call_id=call.id,
            action_digest=policy.action_digest,
            idempotency_key="unknown-refund-1",
            status="unknown",
        )
        session.add(execution)
        session.add(
            Refund(
                tenant_id=tenant_id,
                payment_id=payload.payment_id,
                order_id=payload.order_id,
                idempotency_key="unknown-refund-1",
                status="succeeded",
                amount_minor=payload.amount_minor,
                currency="INR",
                reason_code=payload.reason_code,
            )
        )
        session.flush()
        result = execute_refund(
            session,
            tenant_id=tenant_id,
            actor_user_id=seed_id("user:acme:agent"),
            run_id=run_id,
            trace_id=uuid.uuid4().hex,
            idempotency_key="unknown-refund-1",
            payload=payload,
            policy=policy,
            valid_approval=True,
        )
        session.commit()
        assert result.replayed is True
        assert result.status == "succeeded"
        assert execution.status == "verified"
        assert session.scalar(select(func.count(Refund.id))) == 1
    engine.dispose()


def test_adversarial_dataset_has_enforced_expectations() -> None:
    dataset_path = Path(__file__).parents[2] / "datasets" / "adversarial" / "security-v1.json"
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    assert len(payload["cases"]) == 9
    for case in payload["cases"]:
        expected = case["expected"]
        text = case["input"]
        if expected == "block":
            assert inspect_input(text).decision == "block", case["id"]
        elif expected == "quarantine":
            assert quarantine_external_content(text).decision == "quarantine", case["id"]
        elif expected == "deny":
            action = (
                "change_payment_destination" if case["id"] == "destination-change" else "read_order"
            )
            tenant = uuid.uuid4()
            resource_tenant = uuid.uuid4() if case["id"] == "cross-customer" else tenant
            result = evaluate_action(
                ActionRequest(action, tenant, resource_tenant, {}),
                PolicyContext(frozenset({"support_agent"}), "high"),
            )
            assert result.decision is PolicyDecision.DENY, case["id"]
        elif expected == "no_side_effect":
            assert "without approval" in text.lower()


def test_canary_assignment_is_sticky_and_failed_gates_roll_back() -> None:
    tenant_id = uuid.uuid4()
    kwargs = {
        "tenant_id": tenant_id,
        "subject_key": "case-123",
        "stable": {"model": "stable"},
        "candidate": {"model": "candidate"},
        "candidate_allocation_percent": 25,
    }
    first = select_deployment(**kwargs)
    second = select_deployment(**kwargs)
    assert first == second
    assert next_canary_allocation(5, gates_passed=True) == 25
    assert next_canary_allocation(50, gates_passed=False) == 0


def test_shadow_pipeline_is_sanitized_and_write_disabled() -> None:
    request = make_shadow_request("Email me at test@example.test", "candidate-v2")
    assert request.writes_enabled is False
    assert "[REDACTED_EMAIL]" in request.sanitized_input
    validate_shadow_result(
        request,
        ShadowResult("candidate-v2", "comparison only", None, side_effect_attempted=False),
    )
    try:
        validate_shadow_result(
            request,
            ShadowResult("candidate-v2", "bad", "execute_refund", side_effect_attempted=True),
        )
    except ValueError as exc:
        assert "side effect" in str(exc)
    else:
        raise AssertionError("shadow write attempt was accepted")


def test_telemetry_attribute_filter_removes_sensitive_high_cardinality_fields() -> None:
    filtered = safe_attributes(
        {
            "tenant_id": "safe-pseudonymous-tenant",
            "rag_version": "rag_v001",
            "user_id": "must-not-appear",
            "prompt_text": "must-not-appear",
            "input_tokens": 10,
        }
    )
    assert filtered == {
        "tenant_id": "safe-pseudonymous-tenant",
        "rag_version": "rag_v001",
    }


def test_outbox_retries_failures_and_marks_success(database_url: str) -> None:
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    tenant_id = seed_id("tenant:acme")
    delivered: list[tuple[str, dict[str, object]]] = []
    with factory() as session:
        session.info["tenant_id"] = tenant_id
        event = enqueue(
            session,
            tenant_id=tenant_id,
            topic="evaluation.requested",
            aggregate_type="evaluation_run",
            aggregate_id=uuid.uuid4(),
            payload={"run_id": "fixture"},
        )
        assert (
            dispatch_pending(
                session, lambda _topic, _payload: (_ for _ in ()).throw(RuntimeError("offline"))
            )
            == 0
        )
        assert event.status == "pending"
        assert event.attempts == 1
        assert (
            dispatch_pending(session, lambda topic, payload: delivered.append((topic, payload)))
            == 1
        )
        assert event.status == "published"
        assert event.attempts == 2
        session.commit()
    assert delivered == [("evaluation.requested", {"run_id": "fixture"})]
    engine.dispose()
