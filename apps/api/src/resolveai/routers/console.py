import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select

from resolveai.dependencies import RequestContext, get_request_context
from resolveai.models import (
    AgentRun,
    AgentStep,
    Artifact,
    AuditEvent,
    CostEvent,
    DeploymentRecord,
    EvaluationCase,
    EvaluationDataset,
    EvaluationJob,
    EvaluationResult,
    EvaluationRun,
    ExecutionRecord,
    GuardrailEvent,
    KnowledgeChunk,
    ModelVersion,
    OutboxEvent,
    PolicyDecisionRecord,
    PromptVersion,
    RagVersion,
    RetrievalEvent,
    Tenant,
    ToolCall,
    User,
)

router = APIRouter(prefix="/v1/console", tags=["console"])
RequestContextDependency = Annotated[RequestContext, Depends(get_request_context)]


def _require_role(context: RequestContext, *roles: str) -> None:
    if not context.principal.roles.intersection(roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


@router.get("/overview")
def overview(context: RequestContextDependency) -> dict[str, object]:
    _require_role(context, "support_agent", "supervisor", "admin")
    session = context.session
    latest_run = session.scalar(select(AgentRun).order_by(AgentRun.created_at.desc()).limit(1))
    latest_eval = session.scalar(
        select(EvaluationRun).order_by(EvaluationRun.created_at.desc()).limit(1)
    )
    return {
        "agent_runs": session.scalar(select(func.count(AgentRun.id))) or 0,
        "completed_runs": session.scalar(
            select(func.count(AgentRun.id)).where(AgentRun.status == "completed")
        )
        or 0,
        "latest_step_count": latest_run.step_count if latest_run else 0,
        "latest_run_status": latest_run.status if latest_run else "none",
        "audit_events": session.scalar(select(func.count(AuditEvent.id))) or 0,
        "evaluation_cases": session.scalar(select(func.count(EvaluationCase.id))) or 0,
        "latest_evaluation_status": latest_eval.status if latest_eval else "none",
        "pending_approvals": session.scalar(
            select(func.count(PolicyDecisionRecord.id)).where(
                PolicyDecisionRecord.decision == "REQUIRE_APPROVAL"
            )
        )
        or 0,
        "generated_at": datetime.now(UTC).isoformat(),
    }


@router.get("/traces")
def traces(
    context: RequestContextDependency,
    run_status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, object]:
    _require_role(context, "support_agent", "supervisor", "admin")
    statement = select(AgentRun).order_by(AgentRun.created_at.desc())
    count_statement = select(func.count(AgentRun.id))
    if run_status:
        statement = statement.where(AgentRun.status == run_status)
        count_statement = count_statement.where(AgentRun.status == run_status)
    runs = context.session.scalars(statement.offset(offset).limit(limit)).all()
    items: list[dict[str, object]] = []
    for run in runs:
        steps = context.session.scalars(
            select(AgentStep).where(AgentStep.run_id == run.id).order_by(AgentStep.sequence)
        ).all()
        items.append(
            {
                "id": str(run.id),
                "trace_id": run.trace_id,
                "status": run.status,
                "intent": run.intent,
                "risk_level": run.risk_level,
                "current_node": run.current_node,
                "step_count": run.step_count,
                "created_at": _iso(run.created_at),
                "steps": [
                    {
                        "sequence": step.sequence,
                        "node": step.node,
                        "status": step.status,
                        "error_category": step.error_category,
                    }
                    for step in steps
                ],
            }
        )
    return {
        "items": items,
        "total": context.session.scalar(count_statement) or 0,
        "limit": limit,
        "offset": offset,
    }


@router.get("/evaluations")
def evaluations(context: RequestContextDependency) -> dict[str, object]:
    _require_role(context, "supervisor", "admin")
    session = context.session
    runs = session.scalars(select(EvaluationRun).order_by(EvaluationRun.created_at.desc())).all()
    datasets = {row.id: row for row in session.scalars(select(EvaluationDataset)).all()}
    items: list[dict[str, object]] = []
    for run in runs:
        results = session.scalars(
            select(EvaluationResult).where(EvaluationResult.run_id == run.id)
        ).all()
        scored = [result.score for result in results if result.score is not None]
        dataset = datasets.get(run.dataset_id)
        items.append(
            {
                "id": str(run.id),
                "dataset": dataset.name if dataset else "unknown",
                "dataset_version": dataset.version if dataset else "unknown",
                "status": run.status,
                "sample_count": run.sample_count,
                "rag_version": run.rag_version,
                "prompt_version": run.prompt_version,
                "model_version": run.model_version,
                "mean_score": sum(scored) / len(scored) if scored else None,
                "result_count": len(results),
                "passed_results": sum(result.status == "passed" for result in results),
                "created_at": _iso(run.created_at),
                "results": [
                    {
                        "evaluator": result.evaluator,
                        "status": result.status,
                        "score": result.score,
                        "details": result.details_json,
                    }
                    for result in results
                ],
            }
        )
    return {"items": items, "total": len(items)}


@router.get("/rag")
def rag_evolution(context: RequestContextDependency) -> dict[str, object]:
    _require_role(context, "supervisor", "admin")
    session = context.session
    versions = session.scalars(select(RagVersion).order_by(RagVersion.created_at.desc())).all()
    return {
        "items": [
            {
                "id": str(version.id),
                "name": version.name,
                "status": version.status,
                "chunker": version.chunker,
                "chunk_size": version.chunk_size,
                "chunk_overlap": version.chunk_overlap,
                "embedding_model": version.embedding_model,
                "minimum_relevance": version.minimum_relevance,
                "document_chunks": session.scalar(
                    select(func.count(KnowledgeChunk.id)).where(
                        KnowledgeChunk.rag_version_id == version.id
                    )
                )
                or 0,
                "retrieval_count": session.scalar(
                    select(func.count(RetrievalEvent.id)).where(
                        RetrievalEvent.rag_version_id == version.id
                    )
                )
                or 0,
            }
            for version in versions
        ]
    }


@router.get("/cost")
def cost_reliability(context: RequestContextDependency) -> dict[str, object]:
    _require_role(context, "supervisor", "admin")
    session = context.session
    events = session.scalars(select(CostEvent).order_by(CostEvent.created_at.desc())).all()
    tool_calls = session.scalars(select(ToolCall)).all()
    return {
        "event_count": len(events),
        "input_tokens": sum(event.input_tokens for event in events),
        "output_tokens": sum(event.output_tokens for event in events),
        "known_cost_usd_micros": sum(
            event.cost_usd_micros or 0 for event in events if event.cost_usd_micros is not None
        ),
        "unknown_cost_events": sum(event.cost_usd_micros is None for event in events),
        "tool_call_count": len(tool_calls),
        "failed_tool_calls": sum(call.status == "failed" for call in tool_calls),
        "guardrail_events": session.scalar(select(func.count(GuardrailEvent.id))) or 0,
        "execution_records": session.scalar(select(func.count(ExecutionRecord.id))) or 0,
        "items": [
            {
                "provider": event.provider,
                "model": event.model,
                "feature": event.feature,
                "operation_type": event.operation_type,
                "input_tokens": event.input_tokens,
                "output_tokens": event.output_tokens,
                "cost_usd_micros": event.cost_usd_micros,
                "created_at": _iso(event.created_at),
            }
            for event in events[:100]
        ],
    }


@router.get("/models")
def models(context: RequestContextDependency) -> dict[str, object]:
    _require_role(context, "admin")
    session = context.session
    model_rows = session.scalars(
        select(ModelVersion).order_by(ModelVersion.created_at.desc())
    ).all()
    prompts = session.scalars(select(PromptVersion).order_by(PromptVersion.created_at.desc())).all()
    deployments = session.scalars(
        select(DeploymentRecord).order_by(DeploymentRecord.created_at.desc())
    ).all()
    return {
        "models": [
            {
                "id": str(row.id),
                "name": row.name,
                "provider": row.provider,
                "model": row.model,
                "status": row.status,
                "config": row.config_json,
                "created_at": _iso(row.created_at),
            }
            for row in model_rows
        ],
        "prompts": [
            {
                "id": str(row.id),
                "name": row.name,
                "version": row.version,
                "status": row.status,
                "checksum": row.template_sha256,
            }
            for row in prompts
        ],
        "deployments": [
            {
                "id": str(row.id),
                "environment": row.environment,
                "status": row.status,
                "git_commit": row.git_commit,
                "candidate_allocation_percent": row.candidate_allocation_percent,
                "created_at": _iso(row.created_at),
            }
            for row in deployments
        ],
    }


@router.get("/policies")
def policies(context: RequestContextDependency) -> dict[str, object]:
    _require_role(context, "supervisor", "admin")
    rows = context.session.scalars(
        select(PolicyDecisionRecord).order_by(PolicyDecisionRecord.created_at.desc()).limit(200)
    ).all()
    return {
        "autonomous_limit_minor": context.settings.approval_refund_autonomous_limit_minor,
        "single_approval_limit_minor": (
            context.settings.approval_refund_single_approval_limit_minor
        ),
        "hard_ceiling_minor": context.settings.approval_refund_hard_ceiling_minor,
        "items": [
            {
                "id": str(row.id),
                "run_id": str(row.run_id),
                "policy_id": row.policy_id,
                "policy_version": row.policy_version,
                "decision": row.decision,
                "reason": row.reason,
                "risk_level": row.risk_level,
                "required_approver_role": row.required_approver_role,
                "created_at": _iso(row.created_at),
            }
            for row in rows
        ],
    }


@router.get("/audit")
def audit(
    context: RequestContextDependency,
    event_type: str | None = None,
    outcome: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, object]:
    _require_role(context, "supervisor", "admin")
    statement = select(AuditEvent).order_by(AuditEvent.created_at.desc())
    count_statement = select(func.count(AuditEvent.id))
    if event_type:
        statement = statement.where(AuditEvent.event_type == event_type)
        count_statement = count_statement.where(AuditEvent.event_type == event_type)
    if outcome:
        statement = statement.where(AuditEvent.outcome == outcome)
        count_statement = count_statement.where(AuditEvent.outcome == outcome)
    rows = context.session.scalars(statement.offset(offset).limit(limit)).all()
    return {
        "items": [
            {
                "id": str(row.id),
                "event_type": row.event_type,
                "resource_type": row.resource_type,
                "resource_id": str(row.resource_id) if row.resource_id else None,
                "actor_user_id": str(row.actor_user_id) if row.actor_user_id else None,
                "trace_id": row.trace_id,
                "outcome": row.outcome,
                "details": row.details_json,
                "created_at": _iso(row.created_at),
            }
            for row in rows
        ],
        "total": context.session.scalar(count_statement) or 0,
        "limit": limit,
        "offset": offset,
    }


@router.get("/reports")
def reports(context: RequestContextDependency) -> dict[str, object]:
    _require_role(context, "supervisor", "admin")
    artifacts = context.session.scalars(
        select(Artifact).order_by(Artifact.created_at.desc()).limit(100)
    ).all()
    runs = context.session.scalars(
        select(EvaluationRun).order_by(EvaluationRun.created_at.desc()).limit(100)
    ).all()
    return {
        "artifacts": [
            {
                "id": str(row.id),
                "type": row.artifact_type,
                "object_key": row.object_key,
                "content_type": row.content_type,
                "size_bytes": row.size_bytes,
                "checksum": row.checksum_sha256,
                "created_at": _iso(row.created_at),
            }
            for row in artifacts
        ],
        "evaluation_runs": [
            {
                "id": str(row.id),
                "status": row.status,
                "sample_count": row.sample_count,
                "rag_version": row.rag_version,
                "model_version": row.model_version,
                "git_commit": row.git_commit,
                "created_at": _iso(row.created_at),
            }
            for row in runs
        ],
    }


@router.get("/health")
def system_health(context: RequestContextDependency) -> dict[str, object]:
    _require_role(context, "admin")
    session = context.session
    session.execute(select(1)).scalar_one()
    jobs = session.scalars(select(EvaluationJob).order_by(EvaluationJob.created_at.desc())).all()
    outbox = session.scalars(select(OutboxEvent).order_by(OutboxEvent.created_at.desc())).all()
    return {
        "api": "ready",
        "database": "ready",
        "environment": context.settings.environment,
        "auth_mode": context.settings.auth_mode,
        "evaluation_queue_depth": sum(job.status == "pending" for job in jobs),
        "failed_evaluation_jobs": sum(job.status in {"failed", "dead_letter"} for job in jobs),
        "evaluation_retry_count": sum(job.attempts for job in jobs),
        "outbox_queue_depth": sum(event.status == "pending" for event in outbox),
        "failed_outbox_events": sum(event.status == "failed" for event in outbox),
        "outbox_retry_count": sum(event.attempts for event in outbox),
        "jobs": [
            {
                "id": str(job.id),
                "request_key": job.request_key,
                "status": job.status,
                "attempts": job.attempts,
                "max_attempts": job.max_attempts,
                "error_category": job.error_category,
                "available_at": _iso(job.available_at),
            }
            for job in jobs[:50]
        ],
        "outbox": [
            {
                "id": str(event.id),
                "topic": event.topic,
                "aggregate_type": event.aggregate_type,
                "status": event.status,
                "attempts": event.attempts,
                "available_at": _iso(event.available_at),
            }
            for event in outbox[:50]
        ],
        "checked_at": datetime.now(UTC).isoformat(),
    }


def _record_recovery_audit(
    request: Request,
    context: RequestContext,
    *,
    event_type: str,
    resource_type: str,
    resource_id: uuid.UUID | None,
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


@router.post("/health/evaluation-jobs/{job_id}/replay")
def replay_evaluation_job(
    job_id: uuid.UUID,
    request: Request,
    context: RequestContextDependency,
) -> dict[str, object]:
    _require_role(context, "admin")
    job = context.session.scalar(select(EvaluationJob).where(EvaluationJob.id == job_id))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    if job.status not in {"failed", "dead_letter"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"job in {job.status} state cannot be replayed",
        )
    previous_status = job.status
    job.status = "pending"
    job.attempts = 0
    job.available_at = datetime.now(UTC)
    job.error_category = None
    _record_recovery_audit(
        request,
        context,
        event_type="evaluation_job.replayed",
        resource_type="evaluation_job",
        resource_id=job.id,
        details={"previous_status": previous_status},
    )
    return {"id": str(job.id), "status": job.status, "replayed": True}


@router.post("/health/outbox/{event_id}/replay")
def replay_outbox_event(
    event_id: uuid.UUID,
    request: Request,
    context: RequestContextDependency,
) -> dict[str, object]:
    _require_role(context, "admin")
    event = context.session.scalar(select(OutboxEvent).where(OutboxEvent.id == event_id))
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="event not found")
    if event.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"event in {event.status} state cannot be replayed",
        )
    event.status = "pending"
    event.attempts = 0
    event.available_at = datetime.now(UTC)
    _record_recovery_audit(
        request,
        context,
        event_type="outbox_event.replayed",
        resource_type="outbox_event",
        resource_id=event.id,
        details={"topic": event.topic},
    )
    return {"id": str(event.id), "status": event.status, "replayed": True}


@router.post("/health/reconcile")
def reconcile_stalled_work(
    request: Request,
    context: RequestContextDependency,
) -> dict[str, object]:
    """Return stale in-flight evaluation work to the durable queue."""
    _require_role(context, "admin")
    cutoff = datetime.now(UTC) - timedelta(minutes=5)
    jobs = context.session.scalars(
        select(EvaluationJob).where(
            EvaluationJob.status == "running",
            EvaluationJob.updated_at < cutoff,
        )
    ).all()
    now = datetime.now(UTC)
    for job in jobs:
        job.status = "pending"
        job.available_at = now
        job.error_category = "reconciled_stalled_worker"
    _record_recovery_audit(
        request,
        context,
        event_type="durable_work.reconciled",
        resource_type="evaluation_queue",
        resource_id=None,
        details={"requeued_jobs": len(jobs), "stale_before": cutoff.isoformat()},
    )
    return {"requeued_jobs": len(jobs), "checked_at": now.isoformat()}


@router.get("/settings")
def settings(context: RequestContextDependency) -> dict[str, object]:
    _require_role(context, "admin")
    tenant = context.session.get(Tenant, context.principal.tenant_id)
    users = context.session.scalar(select(func.count(User.id))) or 0
    return {
        "tenant": {
            "id": str(tenant.id) if tenant else str(context.principal.tenant_id),
            "name": tenant.name if tenant else "Unknown tenant",
            "slug": tenant.slug if tenant else "unknown",
            "status": tenant.status if tenant else "unknown",
            "user_count": users,
        },
        "runtime": {
            "environment": context.settings.environment,
            "auth_mode": context.settings.auth_mode,
            "jwt_issuer": context.settings.jwt_issuer,
            "jwt_audience": context.settings.jwt_audience,
            "external_adapter_mode": context.settings.external_adapter_mode,
            "model_provider_mode": context.settings.model_provider_mode,
            "model_name": context.settings.model_name,
            "artifact_bucket": context.settings.artifact_bucket,
            "approval_ttl_minutes": context.settings.approval_ttl_minutes,
        },
    }
