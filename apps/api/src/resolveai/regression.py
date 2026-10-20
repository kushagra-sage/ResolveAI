from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Gate:
    metric: str
    minimum: float
    minimum_samples: int
    safety_critical: bool = False


@dataclass(frozen=True, slots=True)
class GateResult:
    metric: str
    status: str
    reason: str


def evaluate_gate(
    gate: Gate, *, value: float | None, sample_count: int, evaluator_failed: bool = False
) -> GateResult:
    if evaluator_failed:
        return GateResult(gate.metric, "FAIL", "EVALUATOR_FAILURE")
    if value is None:
        return GateResult(gate.metric, "FAIL", "MISSING_METRIC")
    if sample_count < gate.minimum_samples:
        return GateResult(gate.metric, "FAIL", "INSUFFICIENT_SAMPLES")
    if value < gate.minimum:
        return GateResult(gate.metric, "FAIL", "THRESHOLD_BREACH")
    return GateResult(gate.metric, "PASS", "THRESHOLD_MET")


def release_allowed(results: list[GateResult]) -> bool:
    return bool(results) and all(result.status == "PASS" for result in results)
