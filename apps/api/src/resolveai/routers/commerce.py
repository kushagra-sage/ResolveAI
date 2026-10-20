import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select

from resolveai.commerce import detect_signal_volume_anomaly, investigate_anomaly
from resolveai.commerce_actions import execute_recommended_action
from resolveai.dependencies import RequestContext, get_request_context
from resolveai.models import (
    ActionOutcome,
    ApprovalRequest,
    AuditEvent,
    CommerceAnomaly,
    CustomerSignal,
    ExecutionRecord,
    OperationalMetricPoint,
    RecommendedAction,
    RootCauseHypothesis,
)
from resolveai.policy import ActionRequest, PolicyContext, evaluate_action
from resolveai.rbac import AuthorizationError, require_permission
from resolveai.schemas import (
    ActionOutcomeCreate,
    ActionOutcomeRead,
    AnomalyDetectionRequest,
    AnomalyDetectionResponse,
    CommerceActionExecutionRead,
    CommerceAnomalyRead,
    CommerceOverview,
    CustomerSignalCreate,
    CustomerSignalRead,
    InvestigationRequest,
    MetricPointCreate,
    MetricPointRead,
    RecommendedActionCreate,
    RecommendedActionRead,
    RootCauseHypothesisRead,
)

router = APIRouter(tags=["commerce"])
RequestContextDependency = Annotated[RequestContext, Depends(get_request_context)]


def _authorize(context: RequestContext, permission: str) -> None:
    try:
        require_permission(context.principal, permission)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden") from exc


def _audit(
    request: Request,
    context: RequestContext,
    *,
    event_type: str,
    resource_type: str,
    resource_id: uuid.UUID,
    details: dict[str, object],
) -> None:
    context.session.add(
        AuditEvent(
            tenant_id=context.principal.tenant_id,
            actor_user_id=context.principal.user_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            trace_id=getattr(request.state, "trace_id", uuid.uuid4().hex),
            outcome="success",
            details_json=details,
        )
    )


def _signal_read(signal: CustomerSignal) -> CustomerSignalRead:
    return CustomerSignalRead(
        id=signal.id,
        ticket_id=signal.ticket_id,
        customer_id=signal.customer_id,
        order_id=signal.order_id,
        store_id=signal.store_id,
        sku_id=signal.sku_id,
        category=signal.category,
        severity=signal.severity,
        confidence=signal.confidence,
        occurred_at=signal.occurred_at,
        source=signal.source,
        evidence=signal.evidence_json,
        model_version=signal.model_version,
        rule_version=signal.rule_version,
        created_at=signal.created_at,
    )


def _metric_read(point: OperationalMetricPoint) -> MetricPointRead:
    return MetricPointRead(
        id=point.id,
        metric_name=point.metric_name,
        entity_type=point.entity_type,
        entity_id=point.entity_id,
        value=point.value,
        unit=point.unit,
        observed_at=point.observed_at,
        dimensions=point.dimensions_json,
        source=point.source,
        created_at=point.created_at,
    )


def _anomaly_read(anomaly: CommerceAnomaly) -> CommerceAnomalyRead:
    return CommerceAnomalyRead(
        id=anomaly.id,
        metric_name=anomaly.metric_name,
        entity_type=anomaly.entity_type,
        entity_id=anomaly.entity_id,
        category=anomaly.category,
        status=anomaly.status,
        window_start=anomaly.window_start,
        window_end=anomaly.window_end,
        sample_count=anomaly.sample_count,
        baseline_value=anomaly.baseline_value,
        observed_value=anomaly.observed_value,
        deviation_score=anomaly.deviation_score,
        confidence=anomaly.confidence,
        detector_name=anomaly.detector_name,
        detector_version=anomaly.detector_version,
        threshold=anomaly.threshold,
        explanation=anomaly.explanation_json,
        created_at=anomaly.created_at,
    )


def _hypothesis_read(hypothesis: RootCauseHypothesis) -> RootCauseHypothesisRead:
    return RootCauseHypothesisRead(
        id=hypothesis.id,
        anomaly_id=hypothesis.anomaly_id,
        rank=hypothesis.rank,
        status=hypothesis.status,
        cause_code=hypothesis.cause_code,
        summary=hypothesis.summary,
        confidence=hypothesis.confidence,
        supporting_evidence=hypothesis.supporting_evidence_json,
        contradicting_evidence=hypothesis.contradicting_evidence_json,
        affected_entities=hypothesis.affected_entities_json,
        time_alignment=hypothesis.time_alignment_json,
        created_at=hypothesis.created_at,
    )


def _action_read(action: RecommendedAction) -> RecommendedActionRead:
    return RecommendedActionRead(
        id=action.id,
        anomaly_id=action.anomaly_id,
        hypothesis_id=action.hypothesis_id,
        action_type=action.action_type,
        parameters=action.parameters_json,
        expected_impact=action.expected_impact_json,
        status=action.status,
        policy_decision=action.policy_decision,
        approval_request_id=action.approval_request_id,
        action_digest=action.action_digest,
        created_at=action.created_at,
    )


def _outcome_read(outcome: ActionOutcome) -> ActionOutcomeRead:
    return ActionOutcomeRead(
        id=outcome.id,
        recommended_action_id=outcome.recommended_action_id,
        target_metric=outcome.target_metric,
        before_window_start=outcome.before_window_start,
        before_window_end=outcome.before_window_end,
        before_value=outcome.before_value,
        after_window_start=outcome.after_window_start,
        after_window_end=outcome.after_window_end,
        after_value=outcome.after_value,
        confidence=outcome.confidence,
        limitations=outcome.limitations_json,
        effect_estimate=outcome.effect_estimate,
        status=outcome.status,
        created_at=outcome.created_at,
    )


@router.post("/v1/customer-signals", response_model=CustomerSignalRead, status_code=201)
def create_customer_signal(
    payload: CustomerSignalCreate,
    request: Request,
    context: RequestContextDependency,
) -> CustomerSignalRead:
    _authorize(context, "commerce:write")
    signal = CustomerSignal(
        tenant_id=context.principal.tenant_id,
        ticket_id=payload.ticket_id,
        customer_id=payload.customer_id,
        order_id=payload.order_id,
        store_id=payload.store_id,
        sku_id=payload.sku_id,
        category=payload.category,
        severity=payload.severity,
        confidence=payload.confidence,
        occurred_at=payload.occurred_at,
        source=payload.source,
        evidence_json=payload.evidence,
        model_version=payload.model_version,
        rule_version=payload.rule_version,
    )
    context.session.add(signal)
    context.session.flush()
    _audit(
        request,
        context,
        event_type="commerce.signal.created",
        resource_type="customer_signal",
        resource_id=signal.id,
        details={"category": signal.category, "source": signal.source},
    )
    context.session.commit()
    return _signal_read(signal)


@router.get("/v1/customer-signals", response_model=list[CustomerSignalRead])
def list_customer_signals(
    context: RequestContextDependency,
    category: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[CustomerSignalRead]:
    _authorize(context, "commerce:read")
    statement = select(CustomerSignal).where(
        CustomerSignal.tenant_id == context.principal.tenant_id
    )
    if category:
        statement = statement.where(CustomerSignal.category == category)
    rows = context.session.scalars(
        statement.order_by(CustomerSignal.occurred_at.desc()).limit(limit)
    ).all()
    return [_signal_read(row) for row in rows]


@router.post("/v1/commerce/metric-points", response_model=MetricPointRead, status_code=201)
def create_metric_point(
    payload: MetricPointCreate,
    request: Request,
    context: RequestContextDependency,
) -> MetricPointRead:
    _authorize(context, "commerce:write")
    point = OperationalMetricPoint(
        tenant_id=context.principal.tenant_id,
        metric_name=payload.metric_name,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        value=payload.value,
        unit=payload.unit,
        observed_at=payload.observed_at,
        dimensions_json=payload.dimensions,
        source=payload.source,
    )
    context.session.add(point)
    context.session.flush()
    _audit(
        request,
        context,
        event_type="commerce.metric.created",
        resource_type="operational_metric_point",
        resource_id=point.id,
        details={"metric_name": point.metric_name, "entity_type": point.entity_type},
    )
    context.session.commit()
    return _metric_read(point)


@router.get("/v1/commerce/overview", response_model=CommerceOverview)
def commerce_overview(context: RequestContextDependency) -> CommerceOverview:
    _authorize(context, "commerce:read")
    tenant_id = context.principal.tenant_id
    category_rows = context.session.execute(
        select(CustomerSignal.category, func.count(CustomerSignal.id))
        .where(CustomerSignal.tenant_id == tenant_id)
        .group_by(CustomerSignal.category)
    ).all()
    return CommerceOverview(
        signal_count=int(
            context.session.scalar(
                select(func.count(CustomerSignal.id)).where(CustomerSignal.tenant_id == tenant_id)
            )
            or 0
        ),
        open_anomaly_count=int(
            context.session.scalar(
                select(func.count(CommerceAnomaly.id)).where(
                    CommerceAnomaly.tenant_id == tenant_id,
                    CommerceAnomaly.status == "OPEN",
                )
            )
            or 0
        ),
        supported_hypothesis_count=int(
            context.session.scalar(
                select(func.count(RootCauseHypothesis.id)).where(
                    RootCauseHypothesis.tenant_id == tenant_id,
                    RootCauseHypothesis.status == "SUPPORTED",
                )
            )
            or 0
        ),
        pending_action_count=int(
            context.session.scalar(
                select(func.count(RecommendedAction.id)).where(
                    RecommendedAction.tenant_id == tenant_id,
                    RecommendedAction.status.in_(["PROPOSED", "APPROVAL_REQUIRED"]),
                )
            )
            or 0
        ),
        measured_outcome_count=int(
            context.session.scalar(
                select(func.count(ActionOutcome.id)).where(
                    ActionOutcome.tenant_id == tenant_id,
                    ActionOutcome.status == "MEASURED",
                )
            )
            or 0
        ),
        signals_by_category={category: int(value) for category, value in category_rows},
    )


@router.get("/v1/commerce/anomalies", response_model=list[CommerceAnomalyRead])
def list_anomalies(
    context: RequestContextDependency,
    anomaly_status: str | None = Query(default=None, alias="status"),
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[CommerceAnomalyRead]:
    _authorize(context, "commerce:read")
    statement = select(CommerceAnomaly).where(
        CommerceAnomaly.tenant_id == context.principal.tenant_id
    )
    if anomaly_status:
        statement = statement.where(CommerceAnomaly.status == anomaly_status)
    rows = context.session.scalars(
        statement.order_by(CommerceAnomaly.window_end.desc()).limit(limit)
    ).all()
    return [_anomaly_read(row) for row in rows]


@router.post("/v1/commerce/anomalies/detect", response_model=AnomalyDetectionResponse)
def detect_anomalies(
    payload: AnomalyDetectionRequest,
    request: Request,
    context: RequestContextDependency,
) -> AnomalyDetectionResponse:
    _authorize(context, "commerce:investigate")
    try:
        result = detect_signal_volume_anomaly(
            context.session,
            tenant_id=context.principal.tenant_id,
            category=payload.category,
            detector=payload.detector,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            window_end=payload.window_end or datetime.now(tz=UTC),
            window_minutes=payload.window_minutes,
            baseline_windows=payload.baseline_windows,
            minimum_support=payload.minimum_support,
            threshold=payload.threshold,
        )
    except ValueError as exc:
        context.session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result.anomaly is not None:
        _audit(
            request,
            context,
            event_type="commerce.anomaly.detected",
            resource_type="commerce_anomaly",
            resource_id=result.anomaly.id,
            details={"category": payload.category, "deviation_score": result.deviation_score},
        )
    context.session.commit()
    return AnomalyDetectionResponse(
        state=result.state,
        reason=result.reason,
        baseline_counts=result.baseline_counts,
        observed_count=result.observed_count,
        baseline_median=result.baseline_median,
        deviation_score=result.deviation_score,
        anomaly=_anomaly_read(result.anomaly) if result.anomaly else None,
    )


@router.post("/v1/commerce/investigations", response_model=list[RootCauseHypothesisRead])
def investigate(
    payload: InvestigationRequest,
    request: Request,
    context: RequestContextDependency,
) -> list[RootCauseHypothesisRead]:
    _authorize(context, "commerce:investigate")
    anomaly = context.session.scalar(
        select(CommerceAnomaly).where(
            CommerceAnomaly.id == payload.anomaly_id,
            CommerceAnomaly.tenant_id == context.principal.tenant_id,
        )
    )
    if anomaly is None:
        raise HTTPException(status_code=404, detail="anomaly not found")
    hypotheses = investigate_anomaly(
        context.session, tenant_id=context.principal.tenant_id, anomaly=anomaly
    )
    for hypothesis in hypotheses:
        _audit(
            request,
            context,
            event_type="commerce.hypothesis.created",
            resource_type="root_cause_hypothesis",
            resource_id=hypothesis.id,
            details={"cause_code": hypothesis.cause_code, "status": hypothesis.status},
        )
    context.session.commit()
    return [_hypothesis_read(hypothesis) for hypothesis in hypotheses]


@router.post(
    "/v1/commerce/recommended-actions", response_model=RecommendedActionRead, status_code=201
)
def create_recommended_action(
    payload: RecommendedActionCreate,
    request: Request,
    context: RequestContextDependency,
) -> RecommendedActionRead:
    _authorize(context, "commerce:investigate")
    tenant_id = context.principal.tenant_id
    if (
        payload.anomaly_id
        and context.session.scalar(
            select(CommerceAnomaly.id).where(
                CommerceAnomaly.id == payload.anomaly_id, CommerceAnomaly.tenant_id == tenant_id
            )
        )
        is None
    ):
        raise HTTPException(status_code=404, detail="anomaly not found")
    if (
        payload.hypothesis_id
        and context.session.scalar(
            select(RootCauseHypothesis.id).where(
                RootCauseHypothesis.id == payload.hypothesis_id,
                RootCauseHypothesis.tenant_id == tenant_id,
            )
        )
        is None
    ):
        raise HTTPException(status_code=404, detail="hypothesis not found")
    policy = evaluate_action(
        ActionRequest(payload.action_type, tenant_id, tenant_id, payload.parameters),
        PolicyContext(context.principal.roles, "high"),
    )
    action_status = {
        "ALLOW": "PROPOSED",
        "REQUIRE_APPROVAL": "APPROVAL_REQUIRED",
        "DENY": "REJECTED",
    }[policy.decision.value]
    action = RecommendedAction(
        tenant_id=tenant_id,
        anomaly_id=payload.anomaly_id,
        hypothesis_id=payload.hypothesis_id,
        action_type=payload.action_type,
        parameters_json=payload.parameters,
        expected_impact_json=payload.expected_impact,
        status=action_status,
        policy_decision=policy.decision.value,
        action_digest=policy.action_digest,
    )
    context.session.add(action)
    context.session.flush()
    if policy.decision.value == "REQUIRE_APPROVAL":
        approval = ApprovalRequest(
            tenant_id=tenant_id,
            run_id=action.id,
            requester_user_id=context.principal.user_id,
            action_type=action.action_type,
            action_digest=action.action_digest,
            action_json={"action": action.action_type, **payload.parameters},
            evidence_json=[
                {
                    "anomaly_id": str(payload.anomaly_id) if payload.anomaly_id else None,
                    "hypothesis_id": (
                        str(payload.hypothesis_id) if payload.hypothesis_id else None
                    ),
                    "expected_impact": payload.expected_impact,
                }
            ],
            required_role=policy.required_approver_role or "supervisor",
            approvals_required=max(1, policy.approvals_required),
            approvals_completed=0,
            status="pending",
            expires_at=datetime.now(tz=UTC)
            + timedelta(minutes=context.settings.approval_ttl_minutes),
        )
        context.session.add(approval)
        context.session.flush()
        action.approval_request_id = approval.id
    _audit(
        request,
        context,
        event_type="commerce.action.recommended",
        resource_type="recommended_action",
        resource_id=action.id,
        details={
            "action_type": action.action_type,
            "policy_decision": action.policy_decision,
            "policy_id": policy.policy_id,
            "policy_version": policy.policy_version,
            "policy_reason": policy.reason,
        },
    )
    context.session.commit()
    return _action_read(action)


@router.get("/v1/commerce/recommended-actions", response_model=list[RecommendedActionRead])
def list_recommended_actions(
    context: RequestContextDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[RecommendedActionRead]:
    _authorize(context, "commerce:read")
    rows = context.session.scalars(
        select(RecommendedAction)
        .where(RecommendedAction.tenant_id == context.principal.tenant_id)
        .order_by(RecommendedAction.created_at.desc())
        .limit(limit)
    ).all()
    return [_action_read(row) for row in rows]


@router.get("/v1/commerce/root-causes", response_model=list[RootCauseHypothesisRead])
def list_root_causes(
    context: RequestContextDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[RootCauseHypothesisRead]:
    _authorize(context, "commerce:read")
    rows = context.session.scalars(
        select(RootCauseHypothesis)
        .where(RootCauseHypothesis.tenant_id == context.principal.tenant_id)
        .order_by(RootCauseHypothesis.created_at.desc(), RootCauseHypothesis.rank)
        .limit(limit)
    ).all()
    return [_hypothesis_read(row) for row in rows]


@router.post(
    "/v1/commerce/recommended-actions/{action_id}/execute",
    response_model=CommerceActionExecutionRead,
)
def execute_action(
    action_id: uuid.UUID,
    request: Request,
    context: RequestContextDependency,
) -> CommerceActionExecutionRead:
    _authorize(context, "commerce:investigate")
    action = context.session.scalar(
        select(RecommendedAction).where(
            RecommendedAction.id == action_id,
            RecommendedAction.tenant_id == context.principal.tenant_id,
        )
    )
    if action is None:
        raise HTTPException(status_code=404, detail="recommended action not found")
    existing = context.session.scalar(
        select(ExecutionRecord).where(
            ExecutionRecord.tenant_id == context.principal.tenant_id,
            ExecutionRecord.idempotency_key
            == f"commerce-action:{action.id}:{action.action_digest}",
        )
    )
    try:
        execution = execute_recommended_action(
            context.session,
            tenant_id=context.principal.tenant_id,
            action=action,
            valid_approval=action.status == "APPROVED",
        )
    except ValueError as exc:
        context.session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _audit(
        request,
        context,
        event_type="commerce.action.executed",
        resource_type="recommended_action",
        resource_id=action.id,
        details={"execution_record_id": str(execution.id), "replayed": existing is not None},
    )
    context.session.commit()
    return CommerceActionExecutionRead(
        recommended_action_id=action.id,
        execution_record_id=execution.id,
        status=execution.status,
        replayed=existing is not None,
        verification=execution.verification_json,
    )


@router.post("/v1/commerce/action-outcomes", response_model=ActionOutcomeRead, status_code=201)
def create_action_outcome(
    payload: ActionOutcomeCreate,
    request: Request,
    context: RequestContextDependency,
) -> ActionOutcomeRead:
    _authorize(context, "commerce:investigate")
    tenant_id = context.principal.tenant_id
    action = context.session.scalar(
        select(RecommendedAction).where(
            RecommendedAction.id == payload.recommended_action_id,
            RecommendedAction.tenant_id == tenant_id,
        )
    )
    if action is None:
        raise HTTPException(status_code=404, detail="recommended action not found")
    if payload.before_window_end <= payload.before_window_start:
        raise HTTPException(status_code=422, detail="before window must have positive duration")
    after_fields = (payload.after_window_start, payload.after_window_end, payload.after_value)
    if any(value is not None for value in after_fields) and not all(
        value is not None for value in after_fields
    ):
        raise HTTPException(
            status_code=422, detail="after window and value must be provided together"
        )
    if payload.after_window_start and payload.after_window_end:
        if payload.after_window_end <= payload.after_window_start:
            raise HTTPException(status_code=422, detail="after window must have positive duration")
        effect = (
            payload.after_value - payload.before_value if payload.after_value is not None else None
        )
        outcome_status = "MEASURED"
    else:
        effect = None
        outcome_status = "NOT_MEASURED"
    limitations = list(payload.limitations)
    default_limitation = "Observational comparison only; causal attribution is not established."
    if default_limitation not in limitations:
        limitations.append(default_limitation)
    outcome = ActionOutcome(
        tenant_id=tenant_id,
        recommended_action_id=action.id,
        target_metric=payload.target_metric,
        before_window_start=payload.before_window_start,
        before_window_end=payload.before_window_end,
        before_value=payload.before_value,
        after_window_start=payload.after_window_start,
        after_window_end=payload.after_window_end,
        after_value=payload.after_value,
        effect_estimate=effect,
        confidence=payload.confidence,
        limitations_json=limitations,
        status=outcome_status,
    )
    context.session.add(outcome)
    context.session.flush()
    _audit(
        request,
        context,
        event_type="commerce.outcome.recorded",
        resource_type="action_outcome",
        resource_id=outcome.id,
        details={"target_metric": outcome.target_metric, "status": outcome.status},
    )
    context.session.commit()
    return _outcome_read(outcome)


@router.get("/v1/commerce/action-outcomes", response_model=list[ActionOutcomeRead])
def list_action_outcomes(
    context: RequestContextDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[ActionOutcomeRead]:
    _authorize(context, "commerce:read")
    rows = context.session.scalars(
        select(ActionOutcome)
        .where(ActionOutcome.tenant_id == context.principal.tenant_id)
        .order_by(ActionOutcome.created_at.desc())
        .limit(limit)
    ).all()
    return [_outcome_read(row) for row in rows]
