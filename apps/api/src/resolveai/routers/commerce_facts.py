import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from resolveai.commerce import (
    DETECTOR_VERSION,
    detect_signal_volume_anomaly,
    evaluate_detector_cases,
)
from resolveai.dependencies import RequestContext, get_request_context
from resolveai.models import (
    AuditEvent,
    CommerceSku,
    CommerceStore,
    DetectorEvaluationRun,
    DetectorSchedule,
    FulfillmentEvent,
    InventorySnapshot,
    ProductBatch,
    QualityReport,
)
from resolveai.rbac import AuthorizationError, require_permission
from resolveai.schemas import (
    CommerceSkuCreate,
    CommerceSkuRead,
    CommerceStoreCreate,
    CommerceStoreRead,
    DeliveryRiskRow,
    DetectorEvaluationRequest,
    DetectorEvaluationResponse,
    DetectorScheduleCreate,
    DetectorScheduleRead,
    DetectorScheduleRunResult,
    FulfillmentEventCreate,
    FulfillmentEventRead,
    InventoryRiskRow,
    InventorySnapshotCreate,
    InventorySnapshotRead,
    ProductBatchCreate,
    ProductBatchRead,
    ProductQualityRow,
    QualityReportCreate,
    QualityReportRead,
)

router = APIRouter(prefix="/v1/commerce", tags=["commerce-facts"])
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


def _commit_or_conflict(context: RequestContext, detail: str) -> None:
    try:
        context.session.commit()
    except IntegrityError as exc:
        context.session.rollback()
        raise HTTPException(status_code=409, detail=detail) from exc


@router.post("/stores", response_model=CommerceStoreRead, status_code=201)
def create_store(
    payload: CommerceStoreCreate, request: Request, context: RequestContextDependency
) -> CommerceStoreRead:
    _authorize(context, "commerce:write")
    row = CommerceStore(tenant_id=context.principal.tenant_id, **payload.model_dump())
    context.session.add(row)
    context.session.flush()
    _audit(
        request,
        context,
        event_type="commerce.store.created",
        resource_type="commerce_store",
        resource_id=row.id,
        details={"external_ref": row.external_ref},
    )
    _commit_or_conflict(context, "store reference already exists")
    return CommerceStoreRead(id=row.id, created_at=row.created_at, **payload.model_dump())


@router.post("/skus", response_model=CommerceSkuRead, status_code=201)
def create_sku(
    payload: CommerceSkuCreate, request: Request, context: RequestContextDependency
) -> CommerceSkuRead:
    _authorize(context, "commerce:write")
    row = CommerceSku(tenant_id=context.principal.tenant_id, **payload.model_dump())
    context.session.add(row)
    context.session.flush()
    _audit(
        request,
        context,
        event_type="commerce.sku.created",
        resource_type="commerce_sku",
        resource_id=row.id,
        details={"external_ref": row.external_ref},
    )
    _commit_or_conflict(context, "SKU reference already exists")
    return CommerceSkuRead(id=row.id, created_at=row.created_at, **payload.model_dump())


@router.post("/inventory-snapshots", response_model=InventorySnapshotRead, status_code=201)
def create_inventory_snapshot(
    payload: InventorySnapshotCreate,
    request: Request,
    context: RequestContextDependency,
) -> InventorySnapshotRead:
    _authorize(context, "commerce:write")
    row = InventorySnapshot(tenant_id=context.principal.tenant_id, **payload.model_dump())
    context.session.add(row)
    context.session.flush()
    _audit(
        request,
        context,
        event_type="commerce.inventory.observed",
        resource_type="inventory_snapshot",
        resource_id=row.id,
        details={"store_ref": row.store_ref, "sku_ref": row.sku_ref},
    )
    context.session.commit()
    return InventorySnapshotRead(id=row.id, created_at=row.created_at, **payload.model_dump())


@router.post("/fulfillment-events", response_model=FulfillmentEventRead, status_code=201)
def create_fulfillment_event(
    payload: FulfillmentEventCreate,
    request: Request,
    context: RequestContextDependency,
) -> FulfillmentEventRead:
    _authorize(context, "commerce:write")
    values = payload.model_dump(exclude={"metadata"})
    row = FulfillmentEvent(
        tenant_id=context.principal.tenant_id,
        metadata_json=payload.metadata,
        **values,
    )
    context.session.add(row)
    context.session.flush()
    _audit(
        request,
        context,
        event_type="commerce.fulfillment.observed",
        resource_type="fulfillment_event",
        resource_id=row.id,
        details={"event_type": row.event_type, "order_ref": row.order_ref},
    )
    context.session.commit()
    return FulfillmentEventRead(id=row.id, created_at=row.created_at, **payload.model_dump())


@router.post("/product-batches", response_model=ProductBatchRead, status_code=201)
def create_product_batch(
    payload: ProductBatchCreate,
    request: Request,
    context: RequestContextDependency,
) -> ProductBatchRead:
    _authorize(context, "commerce:write")
    row = ProductBatch(tenant_id=context.principal.tenant_id, **payload.model_dump())
    context.session.add(row)
    context.session.flush()
    _audit(
        request,
        context,
        event_type="commerce.batch.created",
        resource_type="product_batch",
        resource_id=row.id,
        details={"batch_ref": row.batch_ref, "sku_ref": row.sku_ref},
    )
    _commit_or_conflict(context, "batch reference already exists")
    return ProductBatchRead(id=row.id, created_at=row.created_at, **payload.model_dump())


@router.post("/quality-reports", response_model=QualityReportRead, status_code=201)
def create_quality_report(
    payload: QualityReportCreate,
    request: Request,
    context: RequestContextDependency,
) -> QualityReportRead:
    _authorize(context, "commerce:write")
    values = payload.model_dump(exclude={"evidence"})
    row = QualityReport(
        tenant_id=context.principal.tenant_id,
        evidence_json=payload.evidence,
        **values,
    )
    context.session.add(row)
    context.session.flush()
    _audit(
        request,
        context,
        event_type="commerce.quality.reported",
        resource_type="quality_report",
        resource_id=row.id,
        details={"sku_ref": row.sku_ref, "severity": row.severity},
    )
    context.session.commit()
    return QualityReportRead(id=row.id, created_at=row.created_at, **payload.model_dump())


@router.get("/inventory-risk", response_model=list[InventoryRiskRow])
def inventory_risk(
    context: RequestContextDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[InventoryRiskRow]:
    _authorize(context, "commerce:read")
    rows = context.session.scalars(
        select(InventorySnapshot)
        .where(InventorySnapshot.tenant_id == context.principal.tenant_id)
        .order_by(InventorySnapshot.observed_at.desc())
        .limit(2000)
    ).all()
    seen: set[tuple[str, str]] = set()
    result: list[InventoryRiskRow] = []
    for row in rows:
        key = (row.store_ref, row.sku_ref)
        if key in seen:
            continue
        seen.add(key)
        available = row.on_hand_units - row.reserved_units
        if available <= 0:
            risk_level = "CRITICAL"
        elif available <= row.reorder_point_units:
            risk_level = "HIGH"
        elif available <= row.reorder_point_units * 1.5:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        result.append(
            InventoryRiskRow(
                store_ref=row.store_ref,
                sku_ref=row.sku_ref,
                available_units=available,
                reorder_point_units=row.reorder_point_units,
                risk_level=risk_level,
                observed_at=row.observed_at,
                provenance={"snapshot_id": str(row.id), "source": row.source},
            )
        )
        if len(result) >= limit:
            break
    return result


@router.get("/delivery-risk", response_model=list[DeliveryRiskRow])
def delivery_risk(
    context: RequestContextDependency,
    days: Annotated[int, Query(ge=1, le=90)] = 7,
) -> list[DeliveryRiskRow]:
    _authorize(context, "commerce:read")
    window_end = datetime.now(tz=UTC)
    window_start = window_end - timedelta(days=days)
    rows = context.session.scalars(
        select(FulfillmentEvent).where(
            FulfillmentEvent.tenant_id == context.principal.tenant_id,
            FulfillmentEvent.occurred_at >= window_start,
            FulfillmentEvent.occurred_at < window_end,
        )
    ).all()
    groups: dict[str, list[FulfillmentEvent]] = defaultdict(list)
    for row in rows:
        groups[row.store_ref or "UNKNOWN"].append(row)
    result: list[DeliveryRiskRow] = []
    for store_ref, events in sorted(groups.items()):
        delayed = sum(event.event_type == "DELAYED" for event in events)
        failed = sum(event.event_type == "FAILED" for event in events)
        rate = (delayed + failed) / len(events)
        risk_level = (
            "CRITICAL"
            if failed > 0 and rate >= 0.2
            else "HIGH"
            if rate >= 0.25
            else "MEDIUM"
            if rate >= 0.1
            else "LOW"
        )
        result.append(
            DeliveryRiskRow(
                store_ref=store_ref,
                event_count=len(events),
                delayed_count=delayed,
                failed_count=failed,
                risk_rate=round(rate, 6),
                risk_level=risk_level,
                window_start=window_start,
                window_end=window_end,
                provenance={"event_ids": [str(event.id) for event in events[:20]]},
            )
        )
    return result


@router.get("/product-quality", response_model=list[ProductQualityRow])
def product_quality(
    context: RequestContextDependency,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> list[ProductQualityRow]:
    _authorize(context, "commerce:read")
    window_end = datetime.now(tz=UTC)
    window_start = window_end - timedelta(days=days)
    rows = context.session.scalars(
        select(QualityReport).where(
            QualityReport.tenant_id == context.principal.tenant_id,
            QualityReport.reported_at >= window_start,
            QualityReport.reported_at < window_end,
        )
    ).all()
    groups: dict[str, list[QualityReport]] = defaultdict(list)
    for row in rows:
        groups[row.sku_ref].append(row)
    result: list[ProductQualityRow] = []
    for sku_ref, reports in sorted(groups.items()):
        critical = sum(report.severity == "CRITICAL" for report in reports)
        affected = sum(report.affected_units for report in reports)
        risk_level = (
            "CRITICAL"
            if critical > 0
            else "HIGH"
            if any(report.severity == "HIGH" for report in reports)
            else "MEDIUM"
            if len(reports) >= 2
            else "LOW"
        )
        result.append(
            ProductQualityRow(
                sku_ref=sku_ref,
                report_count=len(reports),
                affected_units=affected,
                critical_reports=critical,
                risk_level=risk_level,
                window_start=window_start,
                window_end=window_end,
                provenance={"report_ids": [str(report.id) for report in reports[:20]]},
            )
        )
    return result


@router.post("/detectors/evaluate", response_model=DetectorEvaluationResponse, status_code=201)
def evaluate_detector(
    payload: DetectorEvaluationRequest,
    request: Request,
    context: RequestContextDependency,
) -> DetectorEvaluationResponse:
    _authorize(context, "commerce:investigate")
    cases = [case.model_dump() for case in payload.cases]
    metrics, dataset_sha256, results = evaluate_detector_cases(
        detector=payload.detector,
        threshold=payload.threshold,
        minimum_support=payload.minimum_support,
        cases=cases,
    )
    row = DetectorEvaluationRun(
        tenant_id=context.principal.tenant_id,
        detector_name=payload.detector,
        detector_version=DETECTOR_VERSION,
        dataset_sha256=dataset_sha256,
        sample_count=len(cases),
        metrics_json=metrics,
        cases_json=results,
    )
    context.session.add(row)
    context.session.flush()
    _audit(
        request,
        context,
        event_type="commerce.detector.evaluated",
        resource_type="detector_evaluation_run",
        resource_id=row.id,
        details={"detector": payload.detector, "dataset_sha256": dataset_sha256},
    )
    context.session.commit()
    return DetectorEvaluationResponse(
        id=row.id,
        detector=payload.detector,
        detector_version=DETECTOR_VERSION,
        dataset_sha256=dataset_sha256,
        sample_count=len(cases),
        created_at=row.created_at,
        **metrics,
    )


def _schedule_read(row: DetectorSchedule) -> DetectorScheduleRead:
    config = row.configuration_json
    return DetectorScheduleRead(
        id=row.id,
        name=row.name,
        detector=row.detector_name,
        category=row.category,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        interval_minutes=row.interval_minutes,
        window_minutes=cast(int, config["window_minutes"]),
        baseline_windows=cast(int, config["baseline_windows"]),
        minimum_support=cast(int, config["minimum_support"]),
        threshold=cast(float, config["threshold"]),
        enabled=row.enabled,
        last_run_at=row.last_run_at,
        next_run_at=row.next_run_at,
        created_at=row.created_at,
    )


@router.post("/detector-schedules", response_model=DetectorScheduleRead, status_code=201)
def create_detector_schedule(
    payload: DetectorScheduleCreate,
    request: Request,
    context: RequestContextDependency,
) -> DetectorScheduleRead:
    _authorize(context, "commerce:investigate")
    now = datetime.now(tz=UTC)
    row = DetectorSchedule(
        tenant_id=context.principal.tenant_id,
        name=payload.name,
        detector_name=payload.detector,
        category=payload.category,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        configuration_json={
            "window_minutes": payload.window_minutes,
            "baseline_windows": payload.baseline_windows,
            "minimum_support": payload.minimum_support,
            "threshold": payload.threshold,
        },
        enabled=payload.enabled,
        interval_minutes=payload.interval_minutes,
        next_run_at=now,
    )
    context.session.add(row)
    context.session.flush()
    _audit(
        request,
        context,
        event_type="commerce.detector.schedule.created",
        resource_type="detector_schedule",
        resource_id=row.id,
        details={"name": row.name, "detector": row.detector_name},
    )
    _commit_or_conflict(context, "detector schedule name already exists")
    return _schedule_read(row)


@router.get("/detector-schedules", response_model=list[DetectorScheduleRead])
def list_detector_schedules(context: RequestContextDependency) -> list[DetectorScheduleRead]:
    _authorize(context, "commerce:read")
    rows = context.session.scalars(
        select(DetectorSchedule)
        .where(DetectorSchedule.tenant_id == context.principal.tenant_id)
        .order_by(DetectorSchedule.name)
    ).all()
    return [_schedule_read(row) for row in rows]


@router.post("/detector-schedules/run-due", response_model=list[DetectorScheduleRunResult])
def run_due_detector_schedules(
    request: Request, context: RequestContextDependency
) -> list[DetectorScheduleRunResult]:
    _authorize(context, "commerce:investigate")
    now = datetime.now(tz=UTC)
    rows = context.session.scalars(
        select(DetectorSchedule)
        .where(
            DetectorSchedule.tenant_id == context.principal.tenant_id,
            DetectorSchedule.enabled.is_(True),
            DetectorSchedule.next_run_at <= now,
        )
        .order_by(DetectorSchedule.next_run_at)
        .limit(20)
        .with_for_update()
    ).all()
    results: list[DetectorScheduleRunResult] = []
    for row in rows:
        config = row.configuration_json
        detection = detect_signal_volume_anomaly(
            context.session,
            tenant_id=context.principal.tenant_id,
            category=row.category,
            detector=row.detector_name,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            window_end=now,
            window_minutes=cast(int, config["window_minutes"]),
            baseline_windows=cast(int, config["baseline_windows"]),
            minimum_support=cast(int, config["minimum_support"]),
            threshold=cast(float, config["threshold"]),
        )
        row.last_run_at = now
        row.next_run_at = now + timedelta(minutes=row.interval_minutes)
        results.append(
            DetectorScheduleRunResult(
                schedule_id=row.id,
                schedule_name=row.name,
                state=detection.state,
                anomaly_id=detection.anomaly.id if detection.anomaly else None,
                next_run_at=row.next_run_at,
            )
        )
        _audit(
            request,
            context,
            event_type="commerce.detector.schedule.executed",
            resource_type="detector_schedule",
            resource_id=row.id,
            details={"state": detection.state},
        )
    context.session.commit()
    return results
