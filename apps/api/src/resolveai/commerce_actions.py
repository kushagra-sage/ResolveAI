import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from resolveai.models import (
    CommerceSku,
    ExecutionRecord,
    OutboxEvent,
    ProductBatch,
    RecommendedAction,
)


def execute_recommended_action(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    action: RecommendedAction,
    valid_approval: bool,
) -> ExecutionRecord:
    idempotency_key = f"commerce-action:{action.id}:{action.action_digest}"
    existing = session.scalar(
        select(ExecutionRecord).where(
            ExecutionRecord.tenant_id == tenant_id,
            ExecutionRecord.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return existing
    if action.policy_decision == "DENY":
        raise ValueError("denied recommendation cannot execute")
    if action.policy_decision == "REQUIRE_APPROVAL" and not valid_approval:
        raise ValueError("valid approval is required")

    parameters = action.parameters_json
    result: dict[str, object] = {
        "action_type": action.action_type,
        "executed_at": datetime.now(tz=UTC).isoformat(),
        "adapter": "local-governed-commerce",
    }
    if action.action_type == "disable_sku":
        sku_ref = parameters.get("sku_ref")
        if not isinstance(sku_ref, str) or not sku_ref:
            raise ValueError("disable_sku requires sku_ref")
        sku = session.scalar(
            select(CommerceSku).where(
                CommerceSku.tenant_id == tenant_id,
                CommerceSku.external_ref == sku_ref,
            )
        )
        if sku is None:
            raise ValueError("SKU not found")
        sku.status = "DISABLED"
        result["sku_ref"] = sku_ref
        result["new_status"] = sku.status
    elif action.action_type == "quarantine_batch":
        batch_ref = parameters.get("batch_ref")
        if not isinstance(batch_ref, str) or not batch_ref:
            raise ValueError("quarantine_batch requires batch_ref")
        batch = session.scalar(
            select(ProductBatch).where(
                ProductBatch.tenant_id == tenant_id,
                ProductBatch.batch_ref == batch_ref,
            )
        )
        if batch is None:
            raise ValueError("batch not found")
        batch.status = "QUARANTINED"
        result["batch_ref"] = batch_ref
        result["new_status"] = batch.status
    elif action.action_type not in {
        "create_ticket",
        "add_ticket_note",
        "inventory_transfer",
        "adjust_delivery_radius",
    }:
        raise ValueError("unsupported commerce action")

    execution = ExecutionRecord(
        tenant_id=tenant_id,
        run_id=action.id,
        tool_call_id=uuid.uuid4(),
        action_digest=action.action_digest,
        idempotency_key=idempotency_key,
        status="succeeded",
        verification_json=result,
    )
    session.add(execution)
    session.flush()
    session.add(
        OutboxEvent(
            tenant_id=tenant_id,
            topic="commerce.action.executed",
            aggregate_type="recommended_action",
            aggregate_id=action.id,
            payload_json={
                "recommended_action_id": str(action.id),
                "execution_record_id": str(execution.id),
                "action_type": action.action_type,
                "action_digest": action.action_digest,
                "result": result,
            },
            status="pending",
            attempts=0,
            available_at=datetime.now(tz=UTC),
        )
    )
    action.status = "EXECUTED"
    return execution
