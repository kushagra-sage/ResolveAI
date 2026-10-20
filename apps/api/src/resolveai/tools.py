import hashlib
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from resolveai.models import (
    AuditEvent,
    CostEvent,
    ExecutionRecord,
    Order,
    OutboxEvent,
    Payment,
    Refund,
    Shipment,
    SupportTicket,
    ToolCall,
)
from resolveai.observability import TOOL_CALL_TOTAL, TOOL_LATENCY
from resolveai.policy import PolicyDecision, PolicyResult


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GetOrderInput(ToolInput):
    order_id: uuid.UUID


class CreateTicketInput(ToolInput):
    customer_id: uuid.UUID
    subject: str = Field(min_length=1, max_length=300)
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")


class ExecuteRefundInput(ToolInput):
    payment_id: uuid.UUID
    order_id: uuid.UUID
    amount_minor: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    reason_code: str = Field(min_length=1, max_length=80)


@dataclass(frozen=True, slots=True)
class ToolResult:
    tool_call_id: uuid.UUID
    status: str
    result: dict[str, object]
    replayed: bool


class ToolExecutionError(RuntimeError):
    pass


def _record_audit(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    event_type: str,
    resource_type: str,
    resource_id: uuid.UUID | None,
    trace_id: str,
    outcome: str,
) -> None:
    session.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            trace_id=trace_id,
            outcome=outcome,
            details_json={},
        )
    )


def get_order(session: Session, order_id: uuid.UUID) -> dict[str, object]:
    order = session.get(Order, order_id)
    if order is None:
        raise ToolExecutionError("order_not_found")
    shipments = session.scalars(select(Shipment).where(Shipment.order_id == order.id)).all()
    return {
        "id": str(order.id),
        "external_ref": order.external_ref,
        "status": order.status,
        "total_minor": order.total_minor,
        "currency": order.currency,
        "shipments": [
            {
                "carrier": shipment.carrier,
                "tracking_number": shipment.tracking_number,
                "status": shipment.status,
            }
            for shipment in shipments
        ],
    }


def get_order_authorized(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    roles: frozenset[str],
    customer_id: uuid.UUID | None,
    order_id: uuid.UUID,
) -> dict[str, object]:
    """Read an order only after tenant, role, and ownership authorization."""
    order = session.get(Order, order_id)
    if order is None or order.tenant_id != tenant_id:
        raise ToolExecutionError("order_not_found")
    privileged = bool(roles & {"support_agent", "supervisor", "admin"})
    owns_order = (
        "customer" in roles and customer_id is not None and order.customer_id == customer_id
    )
    if not privileged and not owns_order:
        raise ToolExecutionError("order_read_forbidden")
    return get_order(session, order_id)


def create_ticket(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    run_id: uuid.UUID,
    trace_id: str,
    idempotency_key: str,
    payload: CreateTicketInput,
    policy: PolicyResult,
) -> ToolResult:
    if policy.decision is not PolicyDecision.ALLOW:
        raise ToolExecutionError("policy_did_not_allow")
    existing = session.scalar(select(ToolCall).where(ToolCall.idempotency_key == idempotency_key))
    if existing is not None:
        return ToolResult(existing.id, existing.status, existing.result_json, True)
    call = ToolCall(
        tenant_id=tenant_id,
        run_id=run_id,
        tool_name="create_ticket",
        idempotency_key=idempotency_key,
        arguments_json=payload.model_dump(mode="json"),
        status="started",
    )
    session.add(call)
    session.flush()
    execution = ExecutionRecord(
        tenant_id=tenant_id,
        run_id=run_id,
        tool_call_id=call.id,
        action_digest=policy.action_digest,
        idempotency_key=idempotency_key,
        status="started",
    )
    session.add(execution)
    session.flush()
    external_ref = "TKT-" + hashlib.sha256(idempotency_key.encode()).hexdigest()[:12].upper()
    ticket = SupportTicket(
        tenant_id=tenant_id,
        customer_id=payload.customer_id,
        external_ref=external_ref,
        subject=payload.subject,
        priority=payload.priority,
    )
    session.add(ticket)
    session.flush()
    call.status = "succeeded"
    call.result_json = {"ticket_id": str(ticket.id), "external_ref": external_ref}
    call.provider_reference = external_ref
    execution.status = "verified"
    execution.verification_json = {"ticket_id": str(ticket.id), "exists": True}
    session.add(
        OutboxEvent(
            tenant_id=tenant_id,
            topic="ticket.created",
            aggregate_type="support_ticket",
            aggregate_id=ticket.id,
            payload_json={"ticket_id": str(ticket.id)},
            available_at=datetime.now(tz=UTC),
        )
    )
    session.add(
        CostEvent(
            tenant_id=tenant_id,
            run_id=run_id,
            provider="sandbox",
            model="ticket-tool-v1",
            feature="ticket_creation",
            agent="resolution_agent",
            endpoint="create_ticket",
            operation_type="tool",
            quantity=1,
            unit="tool_call",
            input_tokens=0,
            output_tokens=0,
            cached_tokens=0,
            cost_usd_micros=0,
            pricing_version="local-sandbox-v1",
        )
    )
    _record_audit(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        event_type="tool.create_ticket",
        resource_type="support_ticket",
        resource_id=ticket.id,
        trace_id=trace_id,
        outcome="succeeded",
    )
    session.flush()
    return ToolResult(call.id, call.status, call.result_json, False)


def execute_refund(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    run_id: uuid.UUID,
    trace_id: str,
    idempotency_key: str,
    payload: ExecuteRefundInput,
    policy: PolicyResult,
    valid_approval: bool,
) -> ToolResult:
    started = time.perf_counter()
    authorized = policy.decision is PolicyDecision.ALLOW or (
        policy.decision is PolicyDecision.REQUIRE_APPROVAL and valid_approval
    )
    if not authorized:
        raise ToolExecutionError("policy_or_approval_did_not_allow")
    call = session.scalar(select(ToolCall).where(ToolCall.idempotency_key == idempotency_key))
    execution = session.scalar(
        select(ExecutionRecord).where(ExecutionRecord.idempotency_key == idempotency_key)
    )
    existing_refund = session.scalar(
        select(Refund).where(Refund.idempotency_key == idempotency_key)
    )
    expected_arguments = payload.model_dump(mode="json")
    if call is not None and call.arguments_json != expected_arguments:
        raise ToolExecutionError("idempotency_key_payload_conflict")
    if call is not None and existing_refund is not None:
        call.status = "succeeded"
        call.result_json = {
            "refund_id": str(existing_refund.id),
            "status": existing_refund.status,
        }
        call.provider_reference = str(existing_refund.id)
        if execution is not None:
            execution.status = "verified"
            execution.verification_json = {
                "refund_id": str(existing_refund.id),
                "status": existing_refund.status,
                "reconciled": True,
            }
        session.flush()
        return ToolResult(call.id, call.status, call.result_json, True)
    if call is not None and call.status not in {"started", "unknown"}:
        return ToolResult(call.id, call.status, call.result_json, True)
    payment = session.get(Payment, payload.payment_id)
    if (
        payment is None
        or payment.order_id != payload.order_id
        or payment.status != "captured"
        or payment.currency.upper() != payload.currency.upper()
    ):
        raise ToolExecutionError("payment_not_refundable")
    refunded_minor = session.scalar(
        select(func.coalesce(func.sum(Refund.amount_minor), 0)).where(
            Refund.payment_id == payload.payment_id,
            Refund.status == "succeeded",
        )
    )
    if int(refunded_minor or 0) + payload.amount_minor > payment.amount_minor:
        raise ToolExecutionError("refund_exceeds_captured_amount")
    if call is None:
        call = ToolCall(
            tenant_id=tenant_id,
            run_id=run_id,
            tool_name="execute_refund",
            idempotency_key=idempotency_key,
            arguments_json=expected_arguments,
            status="started",
        )
        session.add(call)
        session.flush()
    if execution is None:
        execution = ExecutionRecord(
            tenant_id=tenant_id,
            run_id=run_id,
            tool_call_id=call.id,
            action_digest=policy.action_digest,
            idempotency_key=idempotency_key,
            status="started",
        )
        session.add(execution)
        session.flush()
    refund = Refund(
        tenant_id=tenant_id,
        payment_id=payload.payment_id,
        order_id=payload.order_id,
        idempotency_key=idempotency_key,
        status="succeeded",
        amount_minor=payload.amount_minor,
        currency=payload.currency.upper(),
        reason_code=payload.reason_code,
    )
    session.add(refund)
    session.flush()
    call.status = "succeeded"
    total_refunded = int(refunded_minor or 0) + refund.amount_minor
    call.result_json = {
        "refund_id": str(refund.id),
        "status": refund.status,
        "requested_amount_minor": payload.amount_minor,
        "approved_amount_minor": payload.amount_minor,
        "refunded_amount_minor": total_refunded,
        "remaining_refundable_amount_minor": payment.amount_minor - total_refunded,
        "currency": refund.currency,
    }
    call.provider_reference = str(refund.id)
    execution.status = "verified"
    execution.verification_json = {"refund_id": str(refund.id), "status": refund.status}
    session.add(
        OutboxEvent(
            tenant_id=tenant_id,
            topic="refund.succeeded",
            aggregate_type="refund",
            aggregate_id=refund.id,
            payload_json={"refund_id": str(refund.id), "amount_minor": refund.amount_minor},
            available_at=datetime.now(tz=UTC),
        )
    )
    session.add(
        CostEvent(
            tenant_id=tenant_id,
            run_id=run_id,
            provider="sandbox",
            model="refund-tool-v1",
            feature="refund_execution",
            agent="resolution_agent",
            endpoint="execute_refund",
            operation_type="tool",
            quantity=1,
            unit="tool_call",
            input_tokens=0,
            output_tokens=0,
            cached_tokens=0,
            cost_usd_micros=0,
            pricing_version="local-sandbox-v1",
        )
    )
    _record_audit(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        event_type="tool.execute_refund",
        resource_type="refund",
        resource_id=refund.id,
        trace_id=trace_id,
        outcome="succeeded",
    )
    session.flush()
    TOOL_CALL_TOTAL.labels("execute_refund", "succeeded").inc()
    TOOL_LATENCY.labels("execute_refund", "succeeded").observe(time.perf_counter() - started)
    return ToolResult(call.id, call.status, call.result_json, False)
