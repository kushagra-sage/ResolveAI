import hashlib
import time
import uuid
from collections.abc import Callable
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from resolveai.dependencies import RequestContext, get_request_context
from resolveai.interfaces import (
    AdapterConflict,
    AdapterError,
    AdapterRegistry,
    AdapterTimeout,
    AdapterUnavailable,
)
from resolveai.models import AuditEvent
from resolveai.rbac import AuthorizationError, require_permission

router = APIRouter(prefix="/v1/integrations", tags=["integrations"])
RequestContextDependency = Annotated[RequestContext, Depends(get_request_context)]


class StrictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TransferPayload(StrictPayload):
    sku_ref: str = Field(min_length=1, max_length=120)
    source_store: str = Field(min_length=1, max_length=120)
    destination_store: str = Field(min_length=1, max_length=120)
    quantity: int = Field(gt=0, le=100_000)
    idempotency_key: str = Field(min_length=8, max_length=200)


class RefundPayload(StrictPayload):
    payment_ref: str = Field(min_length=1, max_length=160)
    amount_minor: int = Field(gt=0, le=100_000_000)
    currency: str = Field(pattern="^[A-Za-z]{3}$")
    idempotency_key: str = Field(min_length=8, max_length=200)


class ReschedulePayload(StrictPayload):
    delivery_date: date
    idempotency_key: str = Field(min_length=8, max_length=200)


class ModelCompletionPayload(StrictPayload):
    prompt: str = Field(min_length=1, max_length=8_000)


def _authorize(context: RequestContext, permission: str) -> None:
    try:
        require_permission(context.principal, permission)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden") from exc


def _registry(request: Request) -> AdapterRegistry:
    registry: AdapterRegistry = request.app.state.adapter_registry
    return registry


def _invoke(
    request: Request,
    context: RequestContext,
    *,
    adapter: str,
    operation: str,
    call: Callable[[], dict[str, object]],
) -> dict[str, object]:
    started = time.perf_counter()
    outcome = "succeeded"
    try:
        return call()
    except AdapterTimeout as exc:
        outcome = "timeout"
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except AdapterConflict as exc:
        outcome = "conflict"
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AdapterUnavailable as exc:
        outcome = "unavailable"
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AdapterError as exc:
        outcome = "failed"
        raise HTTPException(status_code=502, detail="adapter request failed") from exc
    finally:
        context.session.add(
            AuditEvent(
                tenant_id=context.principal.tenant_id,
                actor_user_id=context.principal.user_id,
                event_type="integration.adapter.call",
                resource_type=adapter,
                resource_id=None,
                trace_id=getattr(request.state, "trace_id", uuid.uuid4().hex),
                outcome=outcome,
                details_json={
                    "operation": operation,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                },
            )
        )
        context.session.commit()


def _local_write_only(context: RequestContext) -> None:
    _authorize(context, "tenant:admin")
    if context.settings.environment not in {"local", "test"}:
        raise HTTPException(status_code=404, detail="sandbox diagnostics are disabled")


@router.get("/status")
def integration_status(request: Request, context: RequestContextDependency) -> dict[str, Any]:
    _authorize(context, "commerce:read")
    registry = _registry(request)
    settings = context.settings
    provider_configured = {
        "erp": registry.mode == "mock" or bool(settings.erp_base_url),
        "wms": registry.mode == "mock" or bool(settings.wms_base_url),
        "payment": registry.mode == "mock" or bool(settings.payment_base_url),
        "shipment": registry.mode == "mock" or bool(settings.shipment_base_url),
        "model": settings.model_provider_mode == "deterministic" or bool(settings.model_base_url),
    }
    return {
        "mode": registry.mode,
        "providers": {
            "erp": {"name": registry.erp.name, "available": provider_configured["erp"]},
            "wms": {"name": registry.wms.name, "available": provider_configured["wms"]},
            "payment": {
                "name": registry.payment.name,
                "available": provider_configured["payment"],
            },
            "shipment": {
                "name": registry.shipment.name,
                "available": provider_configured["shipment"],
            },
            "model": {
                "name": registry.model.name,
                "model": registry.model.model,
                "available": provider_configured["model"],
            },
        },
    }


@router.get("/erp/inventory/{store_ref}/{sku_ref}")
def erp_inventory(
    store_ref: str, sku_ref: str, request: Request, context: RequestContextDependency
) -> dict[str, object]:
    _authorize(context, "commerce:read")
    adapter = _registry(request).erp
    return _invoke(
        request,
        context,
        adapter=adapter.name,
        operation="inventory",
        call=lambda: adapter.inventory(
            tenant_id=str(context.principal.tenant_id), store_ref=store_ref, sku_ref=sku_ref
        ),
    )


@router.get("/wms/fulfillments/{order_ref}")
def wms_fulfillment(
    order_ref: str, request: Request, context: RequestContextDependency
) -> dict[str, object]:
    _authorize(context, "commerce:read")
    adapter = _registry(request).wms
    return _invoke(
        request,
        context,
        adapter=adapter.name,
        operation="fulfillment",
        call=lambda: adapter.fulfillment(
            tenant_id=str(context.principal.tenant_id), order_ref=order_ref
        ),
    )


@router.get("/shipments/{shipment_ref}")
def shipment_status(
    shipment_ref: str, request: Request, context: RequestContextDependency
) -> dict[str, object]:
    _authorize(context, "commerce:read")
    adapter = _registry(request).shipment
    return _invoke(
        request,
        context,
        adapter=adapter.name,
        operation="status",
        call=lambda: adapter.status(
            tenant_id=str(context.principal.tenant_id), shipment_ref=shipment_ref
        ),
    )


@router.post("/sandbox/erp/transfers")
def create_transfer(
    payload: TransferPayload, request: Request, context: RequestContextDependency
) -> dict[str, object]:
    _local_write_only(context)
    adapter = _registry(request).erp
    return _invoke(
        request,
        context,
        adapter=adapter.name,
        operation="create_transfer",
        call=lambda: adapter.create_transfer(
            tenant_id=str(context.principal.tenant_id), **payload.model_dump()
        ),
    )


@router.post("/sandbox/payments/refunds")
def sandbox_refund(
    payload: RefundPayload, request: Request, context: RequestContextDependency
) -> dict[str, object]:
    _local_write_only(context)
    adapter = _registry(request).payment
    return _invoke(
        request,
        context,
        adapter=adapter.name,
        operation="refund",
        call=lambda: adapter.refund(
            tenant_id=str(context.principal.tenant_id), **payload.model_dump()
        ),
    )


@router.post("/sandbox/shipments/{shipment_ref}/reschedule")
def sandbox_reschedule(
    shipment_ref: str,
    payload: ReschedulePayload,
    request: Request,
    context: RequestContextDependency,
) -> dict[str, object]:
    _local_write_only(context)
    adapter = _registry(request).shipment
    return _invoke(
        request,
        context,
        adapter=adapter.name,
        operation="reschedule",
        call=lambda: adapter.reschedule(
            tenant_id=str(context.principal.tenant_id),
            shipment_ref=shipment_ref,
            delivery_date=payload.delivery_date.isoformat(),
            idempotency_key=payload.idempotency_key,
        ),
    )


@router.post("/sandbox/model/completions")
def sandbox_completion(
    payload: ModelCompletionPayload, request: Request, context: RequestContextDependency
) -> dict[str, object]:
    _local_write_only(context)
    adapter = _registry(request).model
    result = _invoke(
        request,
        context,
        adapter=adapter.name,
        operation="complete",
        call=lambda: adapter.complete(payload.prompt),
    )
    result["prompt_sha256"] = hashlib.sha256(payload.prompt.encode()).hexdigest()
    return result
