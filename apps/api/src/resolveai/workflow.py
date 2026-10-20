import hashlib
import re
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from typing import Any, NotRequired, TypedDict, cast

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from resolveai.embeddings import HashEmbeddingProvider
from resolveai.guardrails import inspect_input, inspect_output
from resolveai.models import (
    AgentRun,
    AgentStep,
    ApprovalRequest,
    AuditEvent,
    GuardrailEvent,
    PolicyDecisionRecord,
)
from resolveai.observability import AGENT_NODE_LATENCY, GUARDRAIL_TRIGGER_TOTAL
from resolveai.policy import ActionRequest, PolicyContext, PolicyDecision, evaluate_action
from resolveai.rag import retrieve
from resolveai.tools import ToolExecutionError, get_order_authorized


class ResolutionState(TypedDict):
    tenant_id: str
    user_id: str
    roles: list[str]
    message: str
    trace_id: str
    order_id: NotRequired[str | None]
    payment_id: NotRequired[str | None]
    currency: NotRequired[str]
    reason_code: NotRequired[str]
    customer_id: NotRequired[str | None]
    order_context: NotRequired[dict[str, object] | None]
    intent: NotRequired[str]
    risk_level: NotRequired[str]
    blocked: NotRequired[bool]
    proposed_action: NotRequired[dict[str, object] | None]
    policy: NotRequired[dict[str, object] | None]
    evidence: NotRequired[list[dict[str, object]]]
    answer: NotRequired[str]
    status: NotRequired[str]
    error_category: NotRequired[str | None]
    refund_autonomous_limit_minor: NotRequired[int]
    refund_single_approval_limit_minor: NotRequired[int]
    refund_hard_ceiling_minor: NotRequired[int]


def _unchanged(_state: ResolutionState) -> dict[str, object]:
    return {}


def _input_guard(state: ResolutionState) -> dict[str, object]:
    result = inspect_input(state["message"])
    return {
        "blocked": result.decision == "block",
        "message": result.sanitized_text,
        "error_category": "INPUT_GUARD_BLOCK" if result.decision == "block" else None,
    }


def _classify_intent(state: ResolutionState) -> dict[str, object]:
    text = state["message"].lower()
    if "refund" in text:
        intent = "refund"
    elif "close" in text or "delete my account" in text or "cancel my subscription" in text:
        intent = "account_closure"
    elif "order" in text or "shipment" in text:
        intent = "order_status"
    else:
        intent = "knowledge_question"
    return {"intent": intent}


def _classify_risk(state: ResolutionState) -> dict[str, object]:
    high_markers = ("immediately", "ignore", "card number", "bank", "secret")
    risk = "high" if any(marker in state["message"].lower() for marker in high_markers) else "low"
    return {"risk_level": risk}


def _plan_response(state: ResolutionState) -> dict[str, object]:
    if state.get("blocked"):
        return {"answer": "I cannot process that request safely.", "proposed_action": None}
    intent = state.get("intent")
    if intent == "refund":
        amounts = re.findall(r"(?:₹|rs\.?\s*)([\d,]+)", state["message"], re.I)
        amount_minor = int(amounts[0].replace(",", "")) * 100 if amounts else 0
        return {
            "answer": "The refund request was evaluated against deterministic policy.",
            "proposed_action": {
                "action": "execute_refund",
                "amount_minor": amount_minor,
                "order_id": state.get("order_id"),
                "payment_id": state.get("payment_id"),
                "currency": state.get("currency", "INR"),
                "reason_code": state.get("reason_code", "customer_request"),
            },
        }
    if intent == "account_closure":
        return {
            "answer": "The account-closure request requires review.",
            "proposed_action": {"action": "request_account_closure"},
        }
    if intent == "order_status":
        order = state.get("order_context")
        if order:
            shipment_statuses = ", ".join(
                str(item.get("status", "unknown"))
                for item in cast(list[dict[str, object]], order.get("shipments", []))
            )
            return {
                "answer": (
                    f"Order {order['external_ref']} is {order['status']}. "
                    f"Shipment status: {shipment_statuses or 'not available'}."
                ),
                "proposed_action": None,
            }
        return {
            "answer": "Order status requires an authorized order lookup.",
            "proposed_action": None,
        }
    evidence = state.get("evidence", [])
    if evidence:
        top = evidence[0]
        return {
            "answer": f"{top['content']} [cite:{top['chunk_id']}]",
            "proposed_action": None,
        }
    return {
        "answer": "I do not have sufficient evidence.",
        "proposed_action": None,
        "error_category": "INSUFFICIENT_EVIDENCE",
    }


def _policy_check(state: ResolutionState) -> dict[str, object]:
    proposed = state.get("proposed_action")
    if proposed is None:
        return {"policy": None}
    action = cast(str, proposed["action"])
    request = ActionRequest(
        action=action,
        tenant_id=uuid.UUID(state["tenant_id"]),
        resource_tenant_id=uuid.UUID(state["tenant_id"]),
        parameters={key: value for key, value in proposed.items() if key != "action"},
    )
    result = evaluate_action(
        request,
        PolicyContext(
            roles=frozenset(state["roles"]),
            risk_level=state.get("risk_level", "high"),
            autonomous_refund_limit_minor=state.get("refund_autonomous_limit_minor", 5_000),
            single_approval_limit_minor=state.get("refund_single_approval_limit_minor", 50_000),
            hard_refund_ceiling_minor=state.get("refund_hard_ceiling_minor", 100_000),
        ),
    )
    return {
        "policy": {
            "decision": result.decision.value,
            "policy_id": result.policy_id,
            "policy_version": result.policy_version,
            "reason": result.reason,
            "risk_level": result.risk_level,
            "required_approver_role": result.required_approver_role,
            "approvals_required": result.approvals_required,
            "action_digest": result.action_digest,
        }
    }


def _request_approval(state: ResolutionState) -> dict[str, object]:
    policy = state.get("policy")
    if policy and policy["decision"] == PolicyDecision.REQUIRE_APPROVAL.value:
        return {"status": "waiting_approval"}
    return {}


def _execute_tool(state: ResolutionState) -> dict[str, object]:
    policy = state.get("policy")
    if policy and policy["decision"] == PolicyDecision.DENY.value:
        return {"status": "denied", "answer": "The requested action is not permitted."}
    if policy and policy["decision"] == PolicyDecision.REQUIRE_APPROVAL.value:
        return {}
    if policy and policy["decision"] == PolicyDecision.ALLOW.value:
        return {"status": "planned"}
    return {}


def _output_guard(state: ResolutionState) -> dict[str, object]:
    supported_ids = {str(item["chunk_id"]) for item in state.get("evidence", [])}
    result = inspect_output(state.get("answer", ""), supported_ids)
    if result.decision == "block":
        return {
            "answer": "The response was withheld by output safety checks.",
            "status": "blocked",
            "error_category": "OUTPUT_GUARD_BLOCK",
        }
    return {"answer": result.sanitized_text}


def _finalize(state: ResolutionState) -> dict[str, object]:
    if "status" not in state:
        return {"status": "completed"}
    return {}


def _instrument_node(
    name: str, node: Callable[[ResolutionState], dict[str, object]]
) -> Callable[[ResolutionState], dict[str, object]]:
    def measured(state: ResolutionState) -> dict[str, object]:
        started = time.perf_counter()
        outcome = "completed"
        try:
            return node(state)
        except Exception:
            outcome = "failed"
            raise
        finally:
            AGENT_NODE_LATENCY.labels(name, outcome).observe(time.perf_counter() - started)

    return measured


def build_resolution_graph() -> Any:
    graph = StateGraph(ResolutionState)
    nodes: dict[str, Callable[[ResolutionState], dict[str, object]]] = {
        "authenticate": _unchanged,
        "input_guard": _input_guard,
        "classify_intent": _classify_intent,
        "classify_risk": _classify_risk,
        "load_customer": _unchanged,
        "retrieve_context": _unchanged,
        "rerank": _unchanged,
        "plan_response": _plan_response,
        "grounding_check": _unchanged,
        "propose_action": _unchanged,
        "policy_check": _policy_check,
        "request_approval": _request_approval,
        "execute_tool": _execute_tool,
        "verify_execution": _unchanged,
        "output_guard": _output_guard,
        "finalize": _finalize,
        "audit": _unchanged,
    }
    for name, node in nodes.items():
        graph.add_node(name, _instrument_node(name, node))  # type: ignore[call-overload]
    ordered = list(nodes)
    graph.add_edge(START, ordered[0])
    for left, right in pairwise(ordered):
        graph.add_edge(left, right)
    graph.add_edge(ordered[-1], END)
    return graph.compile()


def run_resolution(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    roles: frozenset[str],
    message: str,
    customer_id: uuid.UUID | None = None,
    order_id: uuid.UUID | None = None,
    payment_id: uuid.UUID | None = None,
    currency: str = "INR",
    reason_code: str = "customer_request",
    max_steps: int = 20,
    refund_autonomous_limit_minor: int = 5_000,
    refund_single_approval_limit_minor: int = 50_000,
    refund_hard_ceiling_minor: int = 100_000,
    approval_ttl_minutes: int = 30,
) -> AgentRun:
    if max_steps < 17:
        raise ValueError("max_steps must permit the 17-node safety workflow")
    trace_id = uuid.uuid4().hex
    run = AgentRun(
        tenant_id=tenant_id,
        user_id=user_id,
        status="running",
        current_node="authenticate",
        state_json={},
        trace_id=trace_id,
    )
    session.add(run)
    session.flush()
    order_context: dict[str, object] | None = None
    if order_id is not None and inspect_input(message).decision == "allow":
        try:
            order_context = get_order_authorized(
                session,
                tenant_id=tenant_id,
                roles=roles,
                customer_id=customer_id,
                order_id=order_id,
            )
        except ToolExecutionError:
            order_context = None
    evidence: list[dict[str, object]] = []
    lowered = message.lower()
    needs_knowledge = not any(
        marker in lowered for marker in ("refund", "order", "shipment", "close", "delete")
    )
    if needs_knowledge and inspect_input(message).decision == "allow":
        retrieval = retrieve(
            session,
            HashEmbeddingProvider(),
            tenant_id=tenant_id,
            query=message,
            top_k=5,
        )
        evidence = [
            {
                "chunk_id": str(item.chunk_id),
                "document_id": str(item.document_id),
                "document_version_id": str(item.document_version_id),
                "title": item.title,
                "source_uri": item.source_uri,
                "content": item.content,
                "heading_path": list(item.heading_path),
                "score": item.score,
            }
            for item in retrieval.evidence
        ]
    initial: ResolutionState = {
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "roles": sorted(roles),
        "message": message,
        "trace_id": trace_id,
        "order_id": str(order_id) if order_id else None,
        "payment_id": str(payment_id) if payment_id else None,
        "currency": currency.upper(),
        "reason_code": reason_code,
        "customer_id": str(customer_id) if customer_id else None,
        "order_context": order_context,
        "evidence": evidence,
        "refund_autonomous_limit_minor": refund_autonomous_limit_minor,
        "refund_single_approval_limit_minor": refund_single_approval_limit_minor,
        "refund_hard_ceiling_minor": refund_hard_ceiling_minor,
    }
    graph = build_resolution_graph()
    final_state = initial
    seen: dict[str, int] = {}
    for sequence, event in enumerate(graph.stream(initial, {"recursion_limit": max_steps})):
        node, update = next(iter(event.items()))
        seen[node] = seen.get(node, 0) + 1
        if seen[node] > 2:
            raise RuntimeError("agent_loop_detected")
        normalized_update = cast(dict[str, object], update or {})
        final_state = {**final_state, **normalized_update}  # type: ignore[typeddict-item]
        session.add(
            AgentStep(
                tenant_id=tenant_id,
                run_id=run.id,
                sequence=sequence,
                node=node,
                status="succeeded",
                input_sha256=hashlib.sha256(message.encode()).hexdigest(),
                output_json=normalized_update,
            )
        )
        run.current_node = node
        run.step_count = sequence + 1
    run.status = final_state.get("status", "completed")
    run.intent = final_state.get("intent")
    run.risk_level = final_state.get("risk_level")
    run.state_json = cast(dict[str, object], final_state)
    policy = final_state.get("policy")
    if policy:
        session.add(
            PolicyDecisionRecord(
                tenant_id=tenant_id,
                run_id=run.id,
                policy_id=cast(str, policy["policy_id"]),
                policy_version=cast(str, policy["policy_version"]),
                decision=cast(str, policy["decision"]),
                reason=cast(str, policy["reason"]),
                risk_level=cast(str, policy["risk_level"]),
                required_approver_role=cast(str | None, policy["required_approver_role"]),
                approvals_required=cast(int, policy["approvals_required"]),
                action_digest=cast(str, policy["action_digest"]),
            )
        )
        if policy["decision"] == PolicyDecision.REQUIRE_APPROVAL.value:
            session.add(
                ApprovalRequest(
                    tenant_id=tenant_id,
                    run_id=run.id,
                    requester_user_id=user_id,
                    action_type=cast(dict[str, object], final_state["proposed_action"])["action"],
                    action_digest=cast(str, policy["action_digest"]),
                    action_json=cast(dict[str, object], final_state["proposed_action"]),
                    required_role=cast(str, policy["required_approver_role"]),
                    approvals_required=cast(int, policy["approvals_required"]),
                    expires_at=datetime.now(tz=UTC) + timedelta(minutes=approval_ttl_minutes),
                )
            )
    input_guard = inspect_input(message)
    supported_ids = {str(item["chunk_id"]) for item in final_state.get("evidence", [])}
    output_guard = inspect_output(final_state.get("answer", ""), supported_ids)
    for stage, result in (("input", input_guard), ("output", output_guard)):
        GUARDRAIL_TRIGGER_TOTAL.labels(result.guardrail, result.decision).inc()
        session.add(
            GuardrailEvent(
                tenant_id=tenant_id,
                run_id=run.id,
                guardrail=result.guardrail,
                stage=stage,
                decision=result.decision,
                reason=result.reason,
                content_sha256=result.content_sha256,
                latency_ms=result.latency_ms,
                model_version="deterministic-v1",
            )
        )
    session.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=user_id,
            event_type="agent.run.finalized",
            resource_type="agent_run",
            resource_id=run.id,
            trace_id=trace_id,
            outcome=run.status,
            details_json={"intent": run.intent, "risk_level": run.risk_level},
        )
    )
    session.flush()
    return run
