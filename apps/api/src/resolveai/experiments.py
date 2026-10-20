import itertools
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    chunker: str
    retriever: str
    dense_top_k: int
    keyword_top_k: int
    rerank_top_n: int
    embedding_model: str
    model: str
    prompt_version: str


@dataclass(frozen=True, slots=True)
class ExperimentMeasurement:
    config: ExperimentConfig
    quality: float
    safety: float
    latency_ms: float
    cost_usd: float | None
    sample_count: int


def experiment_matrix(factors: dict[str, list[object]]) -> list[dict[str, object]]:
    names = tuple(sorted(factors))
    return [
        dict(zip(names, values, strict=True))
        for values in itertools.product(*(factors[name] for name in names))
    ]


def paired_delta(baseline: dict[str, float], candidate: dict[str, float]) -> dict[str, float]:
    if baseline.keys() != candidate.keys():
        raise ValueError("paired comparison requires identical case sets")
    return {key: candidate[key] - baseline[key] for key in sorted(baseline)}


def pareto_frontier(measurements: list[ExperimentMeasurement]) -> list[ExperimentMeasurement]:
    frontier: list[ExperimentMeasurement] = []
    for candidate in measurements:
        candidate_cost = float("inf") if candidate.cost_usd is None else candidate.cost_usd
        dominated = False
        for other in measurements:
            if other is candidate or other.cost_usd is None:
                continue
            no_worse = (
                other.quality >= candidate.quality
                and other.safety >= candidate.safety
                and other.latency_ms <= candidate.latency_ms
                and other.cost_usd <= candidate_cost
            )
            strictly_better = (
                other.quality > candidate.quality
                or other.safety > candidate.safety
                or other.latency_ms < candidate.latency_ms
                or other.cost_usd < candidate_cost
            )
            if no_worse and strictly_better:
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    return frontier
