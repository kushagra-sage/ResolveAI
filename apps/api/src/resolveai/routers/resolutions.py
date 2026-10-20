import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select

from resolveai.commerce_actions import execute_recommended_action
from resolveai.dependencies import RequestContext, get_request_context
from resolveai.evaluation import enqueue_online_evaluation
from resolveai.models import (
    AgentRun,
    ApprovalDecision,
    ApprovalRequest,
    AuditEvent,
    CustomerSignal,
    PolicyDecisionRecord,
    RecommendedAction,
)
from resolveai.observability import APPROVAL_LATENCY, APPROVAL_TOTAL, BUSINESS_EVENT_TOTAL
from resolveai.policy import (
    ActionRequest,
    PolicyContext,
    PolicyDecision,
    PolicyResult,
    action_digest,
    approval_is_valid,
    evaluate_action,
)
from resolveai.rbac import AuthorizationError, load_access, require_permission
from resolveai.schemas import (
    ApprovalDecisionRequest,
    ApprovalResponse,
    ResolutionRequest,
    ResolutionResponse,
)
from resolveai.tools import ExecuteRefundInput, ToolExecutionError, execute_refund
from resolveai.workflow import run_resolution

router = APIRouter(prefix="/v1", tags=["resolutions"])
RequestContextDependency = Annotated[RequestContext, Depends(get_request_context)]


def _approval_response(request: ApprovalRequest) -> ApprovalResponse:
    return ApprovalResponse(
        id=request.id,
        run_id=request.run_id,
        requester_user_id=request.requester_user_id,
        action_type=request.action_type,
        action_digest=request.action_digest,
        action=request.action_json,
        evidence=request.evidence_json,
        required_role=request.required_role,
        approvals_required=request.approvals_required,
        approvals_completed=request.approvals_completed,
        status=request.status,
        expires_at=request.expires_at,
    )


@router.post("/resolutions", response_model=ResolutionResponse)
def create_resolution(
    payload: ResolutionRequest,
    context: RequestContextDependency,
) -> ResolutionResponse:
    run = run_resolution(
        context.session,
        tenant_id=context.principal.tenant_id,
        user_id=context.principal.user_id,
        roles=context.principal.roles,
        message=payload.message,
        customer_id=context.principal.customer_id,
        order_id=payload.order_id,
        payment_id=payload.payment_id,
        currency=payload.currency,
        reason_code=payload.reason_code,
        refund_autonomous_limit_minor=context.settings.approval_refund_autonomous_limit_minor,
        refund_single_approval_limit_minor=(
            context.settings.approval_refund_single_approval_limit_minor
        ),
        refund_hard_ceiling_minor=context.settings.approval_refund_hard_ceiling_minor,
        approval_ttl_minutes=context.settings.approval_ttl_minutes,
    )
    enqueue_online_evaluation(
        context.session,
        tenant_id=context.principal.tenant_id,
        request_key=f"resolution:{run.id}",
        run_id=run.id,
        payload={
            "run_id": str(run.id),
            "intent": run.intent,
            "risk_level": run.risk_level,
            "status": run.status,
            "has_approval": run.status == "waiting_approval",
        },
    )
    signal_category = {"refund": "REFUND_DELAY", "order_status": "DELIVERY_DELAY"}.get(
        run.intent or ""
    )
    if signal_category is not None:
        context.session.add(
            CustomerSignal(
                tenant_id=context.principal.tenant_id,
                customer_id=context.principal.customer_id,
                order_id=payload.order_id,
                category=signal_category,
                severity="HIGH" if run.risk_level == "high" else "MEDIUM",
                confidence=0.9,
                occurred_at=datetime.now(tz=UTC),
                source="resolution_workflow",
                evidence_json={
                    "run_id": str(run.id),
                    "intent": run.intent,
                    "risk_level": run.risk_level,
                    "status": run.status,
                    "reason_code": payload.reason_code,
                },
                rule_version="resolution-signal-v1",
            )
        )
    context.session.commit()
    approval_id = context.session.scalar(
        select(ApprovalRequest.id).where(ApprovalRequest.run_id == run.id)
    )
    return ResolutionResponse(
        run_id=run.id,
        status=run.status,
        intent=run.intent,
        risk_level=run.risk_level,
        answer=cast(str, run.state_json.get("answer", "")),
        trace_id=run.trace_id,
        approval_request_id=approval_id,
    )


@router.get("/approvals", response_model=list[ApprovalResponse])
def list_approvals(context: RequestContextDependency) -> list[ApprovalResponse]:
    try:
        require_permission(context.principal, "approval:review")
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden") from exc
    requests = context.session.scalars(
        select(ApprovalRequest)
        .where(ApprovalRequest.status == "pending")
        .order_by(ApprovalRequest.created_at)
    ).all()
    return [_approval_response(item) for item in requests]


@router.post("/approvals/{approval_id}/decision", response_model=ApprovalResponse)
def decide_approval(
    approval_id: uuid.UUID,
    payload: ApprovalDecisionRequest,
    context: RequestContextDependency,
) -> ApprovalResponse:
    try:
        require_permission(context.principal, "approval:review")
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden") from exc
    approval = context.session.scalar(
        select(ApprovalRequest).where(ApprovalRequest.id == approval_id).with_for_update()
    )
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="approval not found")
    expires_at = approval.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if approval.status != "pending" or expires_at <= datetime.now(tz=UTC):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="approval is not active")
    if payload.decision == "EDIT" and payload.modified_action is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="EDIT requires modified_action",
        )
    action = payload.modified_action if payload.decision == "EDIT" else approval.action_json
    if action is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="approval action is missing",
        )
    action_request = ActionRequest(
        action=cast(str, action["action"]),
        tenant_id=context.principal.tenant_id,
        resource_tenant_id=context.principal.tenant_id,
        parameters={key: value for key, value in action.items() if key != "action"},
    )
    digest = action_digest(action_request)
    requester_roles, _permissions, _customer_id = load_access(
        context.session,
        approval.requester_user_id,
        context.principal.tenant_id,
    )
    run = context.session.get(AgentRun, approval.run_id)
    commerce_action = context.session.scalar(
        select(RecommendedAction).where(
            RecommendedAction.approval_request_id == approval.id,
            RecommendedAction.tenant_id == context.principal.tenant_id,
        )
    )
    policy = evaluate_action(
        action_request,
        PolicyContext(
            roles=requester_roles,
            risk_level=run.risk_level if run and run.risk_level else "high",
            autonomous_refund_limit_minor=(context.settings.approval_refund_autonomous_limit_minor),
            single_approval_limit_minor=(
                context.settings.approval_refund_single_approval_limit_minor
            ),
            hard_refund_ceiling_minor=context.settings.approval_refund_hard_ceiling_minor,
        ),
    )
    context.session.add(
        PolicyDecisionRecord(
            tenant_id=context.principal.tenant_id,
            run_id=approval.run_id,
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            decision=policy.decision.value,
            reason=policy.reason,
            risk_level=policy.risk_level,
            required_approver_role=policy.required_approver_role,
            approvals_required=policy.approvals_required,
            action_digest=policy.action_digest,
        )
    )
    if policy.decision is PolicyDecision.DENY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"action denied by {policy.policy_id}: {policy.reason}",
        )
    previous_reviewer_ids = frozenset(
        context.session.scalars(
            select(ApprovalDecision.reviewer_user_id).where(
                ApprovalDecision.approval_request_id == approval.id,
                ApprovalDecision.decision == "APPROVE",
            )
        ).all()
    )
    valid = approval_is_valid(
        expected_digest=digest if payload.decision == "EDIT" else approval.action_digest,
        actual_digest=digest,
        requester_user_id=approval.requester_user_id,
        reviewer_user_id=context.principal.user_id,
        reviewer_roles=context.principal.roles,
        required_role=approval.required_role,
        previous_reviewer_ids=(
            previous_reviewer_ids if payload.decision == "APPROVE" else frozenset()
        ),
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="separation of duty failed"
        )
    decision = ApprovalDecision(
        tenant_id=context.principal.tenant_id,
        approval_request_id=approval.id,
        reviewer_user_id=context.principal.user_id,
        decision=payload.decision,
        reason=payload.reason,
        modified_action_json=payload.modified_action,
        action_digest=digest,
    )
    context.session.add(decision)
    response_approval = approval
    if payload.decision == "EDIT":
        approval.status = "replaced"
        response_approval = ApprovalRequest(
            tenant_id=context.principal.tenant_id,
            run_id=approval.run_id,
            requester_user_id=approval.requester_user_id,
            action_type=action_request.action,
            action_json=action,
            action_digest=digest,
            evidence_json=approval.evidence_json,
            required_role=policy.required_approver_role or approval.required_role,
            approvals_required=max(1, policy.approvals_required),
            approvals_completed=0,
            status="pending",
            expires_at=datetime.now(tz=UTC)
            + timedelta(minutes=context.settings.approval_ttl_minutes),
        )
        context.session.add(response_approval)
        context.session.flush()
        if run is not None:
            run.status = "waiting_approval"
            run.state_json = {
                **run.state_json,
                "proposed_action": action,
                "policy": {
                    "decision": policy.decision.value,
                    "policy_id": policy.policy_id,
                    "policy_version": policy.policy_version,
                    "reason": policy.reason,
                    "risk_level": policy.risk_level,
                    "required_approver_role": response_approval.required_role,
                    "approvals_required": response_approval.approvals_required,
                    "action_digest": digest,
                },
                "approval_request_id": str(response_approval.id),
            }
        if commerce_action is not None:
            commerce_action.action_type = action_request.action
            commerce_action.parameters_json = action_request.parameters
            commerce_action.action_digest = digest
            commerce_action.policy_decision = policy.decision.value
            commerce_action.status = "APPROVAL_REQUIRED"
            commerce_action.approval_request_id = response_approval.id
    elif payload.decision == "REJECT":
        approval.status = "rejected"
        if run is not None:
            run.status = "rejected"
        if commerce_action is not None:
            commerce_action.status = "REJECTED"
    else:
        if (
            policy.approvals_required != approval.approvals_required
            or policy.required_approver_role != approval.required_role
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="approval obligations changed; request a fresh approval",
            )
        approval.approvals_completed += 1
        if approval.approvals_completed < approval.approvals_required:
            approval.status = "pending"
            if run is not None:
                run.status = "waiting_approval"
        else:
            execution_result = _execute_approved_action(
                approval=approval,
                action=action,
                policy=policy,
                context=context,
                run=run,
                commerce_action=commerce_action,
            )
            approval.status = "approved"
            if run is not None:
                run.status = "completed"
                run.current_node = "verify_execution"
                run.state_json = {
                    **run.state_json,
                    "status": "completed",
                    "execution_result": execution_result,
                }
    context.session.add(
        AuditEvent(
            tenant_id=context.principal.tenant_id,
            actor_user_id=context.principal.user_id,
            event_type="approval.decided",
            resource_type="approval_request",
            resource_id=approval.id,
            trace_id=run.trace_id if run else uuid.uuid4().hex,
            outcome=approval.status,
            details_json={
                "decision": payload.decision,
                "action_digest": digest,
                "replacement_approval_id": (
                    str(response_approval.id) if response_approval is not approval else None
                ),
                "approvals_completed": response_approval.approvals_completed,
                "approvals_required": response_approval.approvals_required,
            },
        )
    )
    context.session.commit()
    APPROVAL_TOTAL.labels(approval.status).inc()
    created_at = approval.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    APPROVAL_LATENCY.labels(approval.status).observe(
        max(0.0, (datetime.now(tz=UTC) - created_at).total_seconds())
    )
    BUSINESS_EVENT_TOTAL.labels("local", f"approval_{approval.status}").inc()
    return _approval_response(response_approval)


def _execute_approved_action(
    *,
    approval: ApprovalRequest,
    action: dict[str, object],
    policy: PolicyResult,
    context: RequestContext,
    run: AgentRun | None,
    commerce_action: RecommendedAction | None,
) -> dict[str, object]:
    if commerce_action is not None:
        try:
            execution = execute_recommended_action(
                context.session,
                tenant_id=context.principal.tenant_id,
                action=commerce_action,
                valid_approval=True,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        return {
            "execution_record_id": str(execution.id),
            "status": execution.status,
            **execution.verification_json,
        }
    if run is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="agent run is missing")
    if approval.action_type != "execute_refund":
        return {"status": "approved_for_manual_execution", "action": approval.action_type}
    try:
        tool_payload = ExecuteRefundInput.model_validate(
            {key: value for key, value in action.items() if key != "action"}
        )
        result = execute_refund(
            context.session,
            tenant_id=context.principal.tenant_id,
            actor_user_id=approval.requester_user_id,
            run_id=approval.run_id,
            trace_id=run.trace_id,
            idempotency_key=f"approval:{approval.id}:{approval.action_digest}",
            payload=tool_payload,
            policy=policy,
            valid_approval=True,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="approved refund action is incomplete or invalid",
        ) from exc
    except ToolExecutionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return {
        "tool_call_id": str(result.tool_call_id),
        "status": result.status,
        "replayed": result.replayed,
        **result.result,
    }
