import hashlib
import json
import math
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import median, pstdev
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from resolveai.models import (
    CommerceAnomaly,
    CustomerSignal,
    FulfillmentEvent,
    InventorySnapshot,
    QualityReport,
    RootCauseHypothesis,
)

DETECTOR_NAME = "robust_signal_volume"
DETECTOR_VERSION = "1.0.0"
MAX_DETECTION_ROWS = 10_000


def utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def robust_deviation(values: list[int], observed: int) -> tuple[float, float, float]:
    """Return median, MAD and a deterministic robust deviation score."""
    if not values:
        raise ValueError("baseline values are required")
    center = float(median(values))
    mad = float(median([abs(value - center) for value in values]))
    if mad > 0:
        score = (observed - center) / (1.4826 * mad)
    else:
        score = (observed - center) / max(math.sqrt(center + 1), 1.0)
    return center, mad, round(score, 6)


def detector_score(
    detector: str, values: list[int], observed: int
) -> tuple[float, float, dict[str, object]]:
    if detector == "robust_z":
        center, mad, score = robust_deviation(values, observed)
        return center, score, {"baseline_mad": mad}
    if detector == "ewma":
        alpha = 0.3
        forecast = float(values[0])
        residuals: list[float] = []
        for value in values[1:]:
            residuals.append(value - forecast)
            forecast = alpha * value + (1 - alpha) * forecast
        scale = max(pstdev(residuals) if len(residuals) > 1 else 0.0, math.sqrt(forecast + 1), 1.0)
        return (
            round(forecast, 6),
            round((observed - forecast) / scale, 6),
            {
                "alpha": alpha,
                "residual_scale": round(scale, 6),
            },
        )
    if detector == "rate_change":
        center = float(median(values))
        score = (observed - center) / max(center, 1.0)
        return center, round(score, 6), {"rate_change": round(score, 6)}
    raise ValueError(f"unsupported detector: {detector}")


def evaluate_detector_cases(
    *,
    detector: str,
    threshold: float,
    minimum_support: int,
    cases: list[dict[str, object]],
) -> tuple[dict[str, object], str, list[dict[str, object]]]:
    results: list[dict[str, object]] = []
    true_positives = false_positives = true_negatives = false_negatives = insufficient = 0
    for case in cases:
        baseline = [int(value) for value in cast(list[int], case["baseline_counts"])]
        observed = cast(int, case["observed_count"])
        expected = bool(case["expected_anomaly"])
        if sum(baseline) < minimum_support:
            predicted: bool | None = None
            score: float | None = None
            insufficient += 1
        else:
            center, score, _details = detector_score(detector, baseline, observed)
            predicted = observed > center and score >= threshold
            if predicted and expected:
                true_positives += 1
            elif predicted and not expected:
                false_positives += 1
            elif not predicted and expected:
                false_negatives += 1
            else:
                true_negatives += 1
        results.append(
            {
                "case_key": str(case["case_key"]),
                "expected_anomaly": expected,
                "predicted_anomaly": predicted,
                "score": score,
            }
        )
    precision_denominator = true_positives + false_positives
    recall_denominator = true_positives + false_negatives
    false_positive_denominator = false_positives + true_negatives
    metrics: dict[str, object] = {
        "true_positives": true_positives,
        "false_positives": false_positives,
        "true_negatives": true_negatives,
        "false_negatives": false_negatives,
        "precision": (
            round(true_positives / precision_denominator, 6) if precision_denominator else None
        ),
        "recall": round(true_positives / recall_denominator, 6) if recall_denominator else None,
        "false_positive_rate": (
            round(false_positives / false_positive_denominator, 6)
            if false_positive_denominator
            else None
        ),
        "insufficient_evidence_count": insufficient,
    }
    canonical = json.dumps(cases, sort_keys=True, separators=(",", ":"))
    return metrics, hashlib.sha256(canonical.encode()).hexdigest(), results


@dataclass(frozen=True, slots=True)
class DetectionResult:
    state: str
    reason: str
    baseline_counts: list[int]
    observed_count: int
    baseline_median: float | None
    deviation_score: float | None
    anomaly: CommerceAnomaly | None


def _entity_matches(signal: CustomerSignal, entity_type: str, entity_id: str) -> bool:
    if entity_type == "TENANT":
        return True
    if entity_type == "STORE":
        return signal.store_id == entity_id
    if entity_type == "SKU":
        return signal.sku_id == entity_id
    return False


def detect_signal_volume_anomaly(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    category: str,
    detector: str,
    entity_type: str,
    entity_id: str,
    window_end: datetime,
    window_minutes: int,
    baseline_windows: int,
    minimum_support: int,
    threshold: float,
) -> DetectionResult:
    end = utc(window_end)
    window = timedelta(minutes=window_minutes)
    current_start = end - window
    baseline_start = current_start - baseline_windows * window
    rows = session.scalars(
        select(CustomerSignal)
        .where(
            CustomerSignal.tenant_id == tenant_id,
            CustomerSignal.category == category,
            CustomerSignal.occurred_at >= baseline_start,
            CustomerSignal.occurred_at < end,
        )
        .order_by(CustomerSignal.occurred_at)
        .limit(MAX_DETECTION_ROWS + 1)
    ).all()
    if len(rows) > MAX_DETECTION_ROWS:
        raise ValueError("detection window exceeds the bounded 10000-signal limit")
    matching = [row for row in rows if _entity_matches(row, entity_type, entity_id)]
    baseline_counts = [0 for _ in range(baseline_windows)]
    observed_count = 0
    for signal in matching:
        occurred_at = utc(signal.occurred_at)
        if current_start <= occurred_at < end:
            observed_count += 1
            continue
        if baseline_start <= occurred_at < current_start:
            bucket = int((occurred_at - baseline_start) // window)
            if 0 <= bucket < baseline_windows:
                baseline_counts[bucket] += 1

    support = sum(baseline_counts)
    if support < minimum_support:
        return DetectionResult(
            state="INSUFFICIENT_EVIDENCE",
            reason=f"baseline support {support} is below required {minimum_support}",
            baseline_counts=baseline_counts,
            observed_count=observed_count,
            baseline_median=None,
            deviation_score=None,
            anomaly=None,
        )

    center, score, detector_details = detector_score(detector, baseline_counts, observed_count)
    if observed_count <= center or score < threshold:
        return DetectionResult(
            state="NO_ANOMALY",
            reason="observed volume did not exceed the configured robust threshold",
            baseline_counts=baseline_counts,
            observed_count=observed_count,
            baseline_median=center,
            deviation_score=score,
            anomaly=None,
        )

    confidence = min(0.99, round(0.55 + min(score / 20, 0.3) + min(support / 100, 0.14), 4))
    anomaly = CommerceAnomaly(
        tenant_id=tenant_id,
        metric_name="customer_signal_count",
        entity_type=entity_type,
        entity_id=entity_id,
        category=category,
        status="OPEN",
        window_start=current_start,
        window_end=end,
        sample_count=support + observed_count,
        baseline_value=center,
        observed_value=float(observed_count),
        deviation_score=score,
        confidence=confidence,
        detector_name=f"{detector}_signal_volume",
        detector_version=DETECTOR_VERSION,
        threshold=threshold,
        explanation_json={
            "baseline_windows": baseline_windows,
            "window_minutes": window_minutes,
            "baseline_counts": baseline_counts,
            "baseline_median": center,
            "observed_count": observed_count,
            "minimum_support": minimum_support,
            "formula": {
                "robust_z": "robust_z=(observed-median)/(1.4826*MAD); sqrt fallback when MAD=0",
                "ewma": "(observed-EWMA forecast)/residual scale; alpha=0.3",
                "rate_change": "(observed-baseline median)/max(baseline median,1)",
            }[detector],
            **detector_details,
        },
    )
    session.add(anomaly)
    session.flush()
    return DetectionResult(
        state="ANOMALY_CREATED",
        reason="observed volume exceeded the configured robust threshold",
        baseline_counts=baseline_counts,
        observed_count=observed_count,
        baseline_median=center,
        deviation_score=score,
        anomaly=anomaly,
    )


def investigate_anomaly(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    anomaly: CommerceAnomaly,
) -> list[RootCauseHypothesis]:
    existing = session.scalars(
        select(RootCauseHypothesis)
        .where(
            RootCauseHypothesis.tenant_id == tenant_id,
            RootCauseHypothesis.anomaly_id == anomaly.id,
        )
        .order_by(RootCauseHypothesis.rank)
    ).all()
    if existing:
        return list(existing)

    signals = session.scalars(
        select(CustomerSignal).where(
            CustomerSignal.tenant_id == tenant_id,
            CustomerSignal.category == anomaly.category,
            CustomerSignal.occurred_at >= anomaly.window_start,
            CustomerSignal.occurred_at < anomaly.window_end,
        )
    ).all()
    total = len(signals)
    candidates: list[tuple[str, str, int, float]] = []
    for entity_type, values in (
        ("STORE", [signal.store_id for signal in signals if signal.store_id]),
        ("SKU", [signal.sku_id for signal in signals if signal.sku_id]),
    ):
        if values:
            entity_id, count = Counter(values).most_common(1)[0]
            share = count / total if total else 0
            if count >= 2 and share >= 0.5:
                candidates.append((entity_type, entity_id, count, share))
    candidates.sort(key=lambda item: (-item[3], -item[2], item[0], item[1]))

    affected_stores = {signal.store_id for signal in signals if signal.store_id}
    affected_skus = {signal.sku_id for signal in signals if signal.sku_id}
    inventory_rows = session.scalars(
        select(InventorySnapshot)
        .where(
            InventorySnapshot.tenant_id == tenant_id,
            InventorySnapshot.observed_at <= anomaly.window_end,
        )
        .order_by(InventorySnapshot.observed_at.desc())
        .limit(500)
    ).all()
    seen_inventory: set[tuple[str, str]] = set()
    for snapshot in inventory_rows:
        key = (snapshot.store_ref, snapshot.sku_ref)
        if key in seen_inventory:
            continue
        seen_inventory.add(key)
        if affected_stores and snapshot.store_ref not in affected_stores:
            continue
        if affected_skus and snapshot.sku_ref not in affected_skus:
            continue
        available = snapshot.on_hand_units - snapshot.reserved_units
        if available <= snapshot.reorder_point_units:
            candidates.append(("INVENTORY", f"{snapshot.store_ref}/{snapshot.sku_ref}", 1, 0.9))
    disruption_count = int(
        session.scalar(
            select(func.count(FulfillmentEvent.id)).where(
                FulfillmentEvent.tenant_id == tenant_id,
                FulfillmentEvent.occurred_at >= anomaly.window_start,
                FulfillmentEvent.occurred_at < anomaly.window_end,
                FulfillmentEvent.event_type.in_(["DELAYED", "FAILED"]),
            )
        )
        or 0
    )
    if disruption_count >= 2:
        candidates.append(("FULFILLMENT", "DELAYED_OR_FAILED", disruption_count, 0.85))
    quality_count = int(
        session.scalar(
            select(func.count(QualityReport.id)).where(
                QualityReport.tenant_id == tenant_id,
                QualityReport.reported_at >= anomaly.window_start - timedelta(days=7),
                QualityReport.reported_at < anomaly.window_end,
                QualityReport.severity.in_(["HIGH", "CRITICAL"]),
            )
        )
        or 0
    )
    if quality_count >= 2:
        candidates.append(("QUALITY", "HIGH_SEVERITY_REPORTS", quality_count, 0.8))
    candidates.sort(key=lambda item: (-item[3], -item[2], item[0], item[1]))

    hypotheses: list[RootCauseHypothesis] = []
    for rank, (entity_type, entity_id, count, share) in enumerate(candidates[:3], start=1):
        cause_code = {
            "INVENTORY": "INVENTORY_SHORTAGE",
            "FULFILLMENT": "FULFILLMENT_DISRUPTION",
            "QUALITY": "QUALITY_REPORT_CLUSTER",
        }.get(entity_type, f"{entity_type}_CONCENTRATION")
        if entity_type in {"STORE", "SKU"}:
            summary = (
                f"{entity_type.title()} {entity_id} accounts for {count} of {total} "
                "signals in the anomaly window."
            )
            evidence_kind = "signal_concentration"
        else:
            summary = {
                "INVENTORY": f"Latest inventory for {entity_id} is at or below its reorder point.",
                "FULFILLMENT": (
                    f"{count} delayed or failed fulfillment events align with the anomaly window."
                ),
                "QUALITY": (
                    f"{count} high-severity quality reports align with the affected period."
                ),
            }[entity_type]
            evidence_kind = "operational_fact"
        hypothesis = RootCauseHypothesis(
            tenant_id=tenant_id,
            anomaly_id=anomaly.id,
            rank=rank,
            status="SUPPORTED",
            cause_code=cause_code,
            summary=summary,
            confidence=min(0.95, round(0.45 + share * 0.5, 4)),
            supporting_evidence_json=[
                {
                    "kind": evidence_kind,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "count": count,
                    "signal_total": total,
                    "evidence_weight": round(share, 4),
                }
            ],
            contradicting_evidence_json=[],
            affected_entities_json=[{"type": entity_type, "id": entity_id}],
            time_alignment_json={
                "window_start": utc(anomaly.window_start).isoformat(),
                "window_end": utc(anomaly.window_end).isoformat(),
            },
        )
        session.add(hypothesis)
        hypotheses.append(hypothesis)

    if not hypotheses:
        hypothesis = RootCauseHypothesis(
            tenant_id=tenant_id,
            anomaly_id=anomaly.id,
            rank=1,
            status="INSUFFICIENT_EVIDENCE",
            cause_code="INSUFFICIENT_EVIDENCE",
            summary="No store or SKU explains at least half of the signals with minimum support.",
            confidence=0.0,
            supporting_evidence_json=[{"kind": "signal_count", "count": total}],
            contradicting_evidence_json=[],
            affected_entities_json=[],
            time_alignment_json={
                "window_start": utc(anomaly.window_start).isoformat(),
                "window_end": utc(anomaly.window_end).isoformat(),
            },
        )
        session.add(hypothesis)
        hypotheses.append(hypothesis)
    session.flush()
    return hypotheses
