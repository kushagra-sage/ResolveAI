from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, select

from resolveai.dependencies import RequestContext, get_request_context
from resolveai.models import CostEvent
from resolveai.rbac import AuthorizationError, require_permission
from resolveai.schemas import CostSummaryRow

router = APIRouter(prefix="/v1/operations", tags=["operations"])
RequestContextDependency = Annotated[RequestContext, Depends(get_request_context)]


@router.get("/cost-summary", response_model=list[CostSummaryRow])
def cost_summary(context: RequestContextDependency) -> list[CostSummaryRow]:
    try:
        require_permission(context.principal, "tenant:admin")
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden") from exc
    dimensions = (
        CostEvent.provider,
        CostEvent.model,
        CostEvent.feature,
        CostEvent.agent,
        CostEvent.prompt_version,
        CostEvent.rag_version,
        CostEvent.endpoint,
        CostEvent.operation_type,
    )
    rows = (
        context.session.execute(
            select(
                CostEvent.provider.label("provider"),
                CostEvent.model.label("model"),
                CostEvent.feature.label("feature"),
                CostEvent.agent.label("agent"),
                CostEvent.prompt_version.label("prompt_version"),
                CostEvent.rag_version.label("rag_version"),
                CostEvent.endpoint.label("endpoint"),
                CostEvent.operation_type.label("operation_type"),
                func.count(CostEvent.id).label("event_count"),
                func.sum(CostEvent.quantity).label("quantity"),
                func.sum(CostEvent.input_tokens).label("input_tokens"),
                func.sum(CostEvent.output_tokens).label("output_tokens"),
                func.sum(CostEvent.cost_usd_micros).label("cost_usd_micros"),
                func.sum(case((CostEvent.cost_usd_micros.is_(None), 1), else_=0)).label(
                    "unknown_cost_events"
                ),
            ).group_by(*dimensions)
        )
        .mappings()
        .all()
    )
    return [
        CostSummaryRow(
            provider=row["provider"],
            model=row["model"],
            feature=row["feature"],
            agent=row["agent"],
            prompt_version=row["prompt_version"],
            rag_version=row["rag_version"],
            endpoint=row["endpoint"],
            operation_type=row["operation_type"],
            event_count=int(row["event_count"] or 0),
            quantity=int(row["quantity"] or 0),
            input_tokens=int(row["input_tokens"] or 0),
            output_tokens=int(row["output_tokens"] or 0),
            cost_usd_micros=(
                int(row["cost_usd_micros"]) if row["cost_usd_micros"] is not None else None
            ),
            unknown_cost_events=int(row["unknown_cost_events"] or 0),
        )
        for row in rows
    ]
