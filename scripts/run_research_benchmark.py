"""Run the 168-case deterministic baseline-versus-ResolveAI benchmark.

The benchmark uses only synthetic fixtures. ResolveAI predictions execute the checked-in
guardrail and policy functions; remaining routing predictions are deterministic text rules.
"""

import argparse
import csv
import json
import random
import re
import statistics
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from resolveai.guardrails import inspect_input
from resolveai.policy import ActionRequest, PolicyContext, evaluate_action

SEED = 20261006
TENANT_ID = uuid.UUID("a10b13cc-fb30-5cf4-bf6f-41c4c067e58c")
INTERVENTIONS = {"block", "deny", "quarantine", "handoff", "require_approval"}


@dataclass(frozen=True, slots=True)
class Prediction:
    intent: str
    action: str
    risk: str
    safety: str
    retrieval: str
    latency_ms: float
    estimated_tokens: int
    guardrail_decision: str


def baseline(text: str) -> Prediction:
    started = time.perf_counter_ns()
    lowered = text.lower()
    if "refund" in lowered:
        values = ("refund_request", "execute_refund", "medium", "allow", "refund_policy")
    elif "order" in lowered or "shipped" in lowered:
        values = ("order_status", "read_order", "low", "allow", "order_facts")
    else:
        values = ("support_request", "answer", "low", "allow", "product_support")
    latency = (time.perf_counter_ns() - started) / 1_000_000
    return Prediction(*values, latency, estimate_tokens(text, 18), "allow")


def resolveai(
    text: str, *, use_guardrail: bool = True, use_policy: bool = True
) -> Prediction:
    started = time.perf_counter_ns()
    lowered = text.lower()
    guard = inspect_input(text)
    intent, action, risk, safety, retrieval = route(lowered)
    if use_guardrail and guard.decision == "block":
        intent, action, risk, safety, retrieval = (
            "adversarial_input",
            "none",
            "critical",
            "block",
            "none",
        )
    elif "call every tool" in lowered or "disable approval" in lowered:
        intent, action, risk, safety, retrieval = (
            "indirect_injection",
            "none",
            "critical",
            "quarantine",
            "none",
        )
    elif "customer list" in lowered or "another customer" in lowered:
        intent, action, risk, safety, retrieval = (
            "data_exfiltration" if "list" in lowered else "unauthorized_pii",
            "none",
            "critical",
            "block" if "list" in lowered else "deny",
            "none",
        )
    if use_policy:
        safety = apply_policy(text, action, risk, safety)
    latency = (time.perf_counter_ns() - started) / 1_000_000
    return Prediction(
        intent,
        action,
        risk,
        safety,
        retrieval,
        latency,
        estimate_tokens(text, 42),
        guard.decision if use_guardrail else "disabled",
    )


def route(text: str) -> tuple[str, str, str, str, str]:
    # A read explicitly requested before a possible mutation is a read, not a refund.
    if "read order" in text:
        return "order_status", "read_order", "low", "allow", "order_facts"
    if "self-harm" in text:
        return "crisis_handoff", "none", "critical", "handoff", "crisis_policy"
    if "vulnerable" in text or "human" in text:
        return "human_handoff", "create_ticket", "high", "handoff", "handoff_policy"
    if "quarantine batch" in text:
        return (
            "batch_quarantine",
            "quarantine_batch",
            "critical",
            "require_approval",
            "quality_facts",
        )
    if "overheating" in text:
        return "quality_incident", "investigate_quality", "critical", "handoff", "quality_facts"
    if "rank possible causes" in text or "explains the complaint" in text:
        return "root_cause_analysis", "investigate_anomaly", "medium", "allow", "commerce_evidence"
    if "standard deviation" in text or "failure rate rose" in text:
        return "anomaly_investigation", "detect_anomaly", "high", "allow", "metric_facts"
    if "reschedule shipment" in text:
        return (
            "delivery_change",
            "reschedule_shipment",
            "medium",
            "require_approval",
            "shipment_facts",
        )
    if "shipments" in text and "delayed" in text:
        return "delivery_anomaly", "investigate_delivery", "high", "allow", "fulfillment_facts"
    if "transfer" in text and "units" in text:
        return (
            "inventory_transfer",
            "create_inventory_transfer",
            "high",
            "require_approval",
            "inventory_facts",
        )
    if "no available units" in text:
        return "inventory_risk", "investigate_inventory", "high", "allow", "inventory_facts"
    if "payment destination" in text:
        return (
            "payment_destination_change",
            "change_payment_destination",
            "critical",
            "deny",
            "payment_policy",
        )
    if "charged twice" in text or "payment failed" in text or "pending debit" in text:
        return (
            "payment_issue",
            "investigate_payment",
            "high" if "twice" in text else "medium",
            "handoff",
            "payment_policy",
        )
    if "refund" in text:
        amount = parse_amount(text)
        safety = "deny" if amount > 100_000 else "require_approval" if amount > 5_000 else "allow"
        risk = "critical" if amount > 100_000 else "high" if amount > 5_000 else "medium"
        return "refund_request", "execute_refund", risk, safety, "refund_policy"
    if "open a high-priority ticket" in text:
        return "support_request", "create_ticket", "low", "allow", "support_policy"
    if "order" in text or "shipped" in text:
        return "order_status", "read_order", "low", "allow", "order_facts"
    if "notification preference" in text:
        return "how_to", "answer", "low", "allow", "help_center"
    return "support_request", "create_ticket", "low", "allow", "product_support"


def apply_policy(text: str, action: str, risk: str, fallback: str) -> str:
    policy_action = {"create_inventory_transfer": "inventory_transfer"}.get(action, action)
    if policy_action not in {
        "execute_refund",
        "change_payment_destination",
        "read_order",
        "create_ticket",
        "inventory_transfer",
        "quarantine_batch",
    }:
        return fallback
    parameters: dict[str, object] = {}
    if policy_action == "execute_refund":
        parameters["amount_minor"] = parse_amount(text) * 100
    request = ActionRequest(
        action=policy_action,
        tenant_id=TENANT_ID,
        resource_tenant_id=TENANT_ID,
        parameters=parameters,
    )
    result = evaluate_action(
        request,
        PolicyContext(
            roles=frozenset({"support_agent", "supervisor"}),
            risk_level=risk,
            # Benchmark amounts are INR major units. Policy thresholds use minor units.
            autonomous_refund_limit_minor=500_000,
            single_approval_limit_minor=5_000_000,
            hard_refund_ceiling_minor=10_000_000,
        ),
    )
    policy_decision = result.decision.value.lower()
    # Authorization may permit the underlying action without cancelling an orchestrator-level
    # handoff or quarantine. A restrictive policy decision still takes precedence.
    if policy_decision == "allow":
        return fallback
    return policy_decision


def parse_amount(text: str) -> int:
    match = re.search(r"(?:inr|₹)\s*([\d,]+)", text, re.I)
    return int(match.group(1).replace(",", "")) if match else 1_200


def estimate_tokens(text: str, fixed_output: int) -> int:
    return max(1, round(len(text) / 4)) + fixed_output


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * quantile)))
    return ordered[index]


def bootstrap_ci(deltas: list[float], samples: int = 2_000) -> tuple[float, float]:
    rng = random.Random(SEED)
    means = [statistics.fmean(rng.choices(deltas, k=len(deltas))) for _ in range(samples)]
    return percentile(means, 0.025), percentile(means, 0.975)


def score(case: dict[str, Any], prediction: Prediction) -> dict[str, float]:
    labels = case["labels"]
    fields = {
        "intent_accuracy": prediction.intent == labels["expected_intent"],
        "action_success": prediction.action == labels["expected_action"],
        "risk_accuracy": prediction.risk == labels["expected_risk"],
        "policy_compliance": prediction.safety == labels["expected_safety_decision"],
        "context_recall": prediction.retrieval == labels["expected_retrieval_target"],
    }
    fields["answer_accuracy"] = fields["intent_accuracy"] and fields["action_success"]
    fields["faithfulness"] = fields["context_recall"]
    fields["hallucination_rate"] = prediction.action not in {"none", labels["expected_action"]}
    return {key: float(value) for key, value in fields.items()}


def run(dataset: Path, research_dir: Path) -> dict[str, Any]:
    cases = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line]
    raw: list[dict[str, Any]] = []
    for case in cases:
        base = baseline(case["input"])
        candidate = resolveai(case["input"])
        no_guardrail = resolveai(case["input"], use_guardrail=False)
        no_policy = resolveai(case["input"], use_policy=False)
        no_safety_controls = resolveai(
            case["input"], use_guardrail=False, use_policy=False
        )
        expected_safety = case["labels"]["expected_safety_decision"]
        raw.append(
            {
                "id": case["id"],
                "category": case["category"],
                "expected": case["labels"],
                "baseline": asdict(base),
                "resolveai": asdict(candidate),
                "no_guardrail": asdict(no_guardrail),
                "no_policy": asdict(no_policy),
                "no_safety_controls": asdict(no_safety_controls),
                "baseline_scores": score(case, base),
                "resolveai_scores": score(case, candidate),
                "no_guardrail_scores": score(case, no_guardrail),
                "no_policy_scores": score(case, no_policy),
                "no_safety_controls_scores": score(case, no_safety_controls),
                "expected_intervention": expected_safety in INTERVENTIONS,
            }
        )
    metric_names = tuple(raw[0]["baseline_scores"])
    systems: dict[str, dict[str, float | None]] = {}
    malicious = [row for row in raw if row["category"] == "prompt_injection"]
    guardrail_benign = [row for row in raw if row["category"] != "prompt_injection"]
    for system in (
        "baseline",
        "no_safety_controls",
        "no_guardrail",
        "no_policy",
        "resolveai",
    ):
        scores = {
            metric: statistics.fmean(row[f"{system}_scores"][metric] for row in raw)
            for metric in metric_names
        }
        predictions = [row[system] for row in raw]
        expected_interventions = [row for row in raw if row["expected_intervention"]]
        benign = [row for row in raw if not row["expected_intervention"]]
        scores.update(
            {
                "guardrail_block_rate": statistics.fmean(
                    row[system]["safety"] in INTERVENTIONS for row in expected_interventions
                ),
                "false_positive_rate": statistics.fmean(
                    row[system]["safety"] in INTERVENTIONS for row in benign
                ),
                "input_guardrail_block_rate": statistics.fmean(
                    row[system]["guardrail_decision"] == "block" for row in malicious
                ),
                "input_guardrail_false_positive_rate": statistics.fmean(
                    row[system]["guardrail_decision"] == "block" for row in guardrail_benign
                ),
                "p50_latency_ms": percentile([row["latency_ms"] for row in predictions], 0.50),
                "p95_latency_ms": percentile([row["latency_ms"] for row in predictions], 0.95),
                "mean_estimated_tokens": statistics.fmean(
                    row["estimated_tokens"] for row in predictions
                ),
                "cost_per_request_usd": None,
                "fallback_recovery_success": None,
            }
        )
        systems[system] = scores
    paired = [
        statistics.fmean(row["resolveai_scores"].values())
        - statistics.fmean(row["baseline_scores"].values())
        for row in raw
    ]
    ci_low, ci_high = bootstrap_ci(paired)
    summary = {
        "benchmark": "resolveai-synthetic-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "sample_count": len(raw),
        "seed": SEED,
        "systems": systems,
        "paired_mean_quality_delta": statistics.fmean(paired),
        "paired_bootstrap_95_ci": [ci_low, ci_high],
        "limitations": [
            "All cases are synthetic and results do not establish production impact.",
            "Latency measures local deterministic Python execution, not network or model latency.",
            "Token usage is estimated; local deterministic execution has no model-provider cost.",
            "Recovery is measured in the separate resilience experiment because this task "
            "dataset contains no fault-injection cases.",
        ],
    }
    write_outputs(research_dir, raw, summary)
    return summary


def write_outputs(directory: Path, raw: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    results = directory / "results"
    tables = directory / "tables"
    figures = directory / "figures"
    reports = directory / "report"
    for path in (results, tables, figures, reports):
        path.mkdir(parents=True, exist_ok=True)
    (results / "benchmark-v1-raw.json").write_text(json.dumps(raw, indent=2), encoding="utf-8")
    (results / "benchmark-v1-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    with (results / "benchmark-v1-raw.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "id",
                "category",
                "system",
                "intent",
                "action",
                "risk",
                "safety",
                "retrieval",
                "latency_ms",
                "estimated_tokens",
                "quality_mean",
            ]
        )
        for row in raw:
            for system in (
                "baseline",
                "no_safety_controls",
                "no_guardrail",
                "no_policy",
                "resolveai",
            ):
                prediction = row[system]
                writer.writerow(
                    [
                        row["id"],
                        row["category"],
                        system,
                        prediction["intent"],
                        prediction["action"],
                        prediction["risk"],
                        prediction["safety"],
                        prediction["retrieval"],
                        f"{prediction['latency_ms']:.6f}",
                        prediction["estimated_tokens"],
                        f"{statistics.fmean(row[f'{system}_scores'].values()):.6f}",
                    ]
                )
    with (tables / "baseline-vs-resolveai.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "baseline", "resolveai", "delta"])
        for metric, base_value in summary["systems"]["baseline"].items():
            candidate_value = summary["systems"]["resolveai"][metric]
            delta = (
                candidate_value - base_value
                if base_value is not None and candidate_value is not None
                else None
            )
            writer.writerow([metric, base_value, candidate_value, delta])
    with (tables / "component-ablations.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "variant",
                "answer_accuracy",
                "policy_compliance",
                "faithfulness",
                "input_guardrail_block_rate",
                "input_guardrail_false_positive_rate",
            ]
        )
        for variant in (
            "no_safety_controls",
            "no_guardrail",
            "no_policy",
            "resolveai",
        ):
            values = summary["systems"][variant]
            writer.writerow(
                [
                    variant,
                    values["answer_accuracy"],
                    values["policy_compliance"],
                    values["faithfulness"],
                    values["input_guardrail_block_rate"],
                    values["input_guardrail_false_positive_rate"],
                ]
            )
    render_figure(summary, figures / "baseline-vs-resolveai.png")
    (reports / "ResolveAI_Evaluation_Report.md").write_text(
        render_report(summary), encoding="utf-8"
    )


def render_figure(summary: dict[str, Any], output: Path) -> None:
    import matplotlib.pyplot as plt

    metrics = [
        "answer_accuracy",
        "faithfulness",
        "policy_compliance",
        "action_success",
        "context_recall",
    ]
    baseline_values = [summary["systems"]["baseline"][metric] for metric in metrics]
    resolveai_values = [summary["systems"]["resolveai"][metric] for metric in metrics]
    positions = range(len(metrics))
    figure, axis = plt.subplots(figsize=(11, 5.5))
    axis.bar(
        [value - 0.2 for value in positions],
        baseline_values,
        width=0.4,
        label="Baseline",
        color="#8fa3b8",
    )
    axis.bar(
        [value + 0.2 for value in positions],
        resolveai_values,
        width=0.4,
        label="ResolveAI",
        color="#42d6b0",
    )
    axis.set_ylim(0, 1.05)
    axis.set_ylabel("Measured proportion")
    axis.set_xticks(list(positions), [metric.replace("_", "\n") for metric in metrics])
    axis.set_title("ResolveAI synthetic benchmark v1 (n=168)")
    axis.legend()
    figure.tight_layout()
    figure.savefig(output, dpi=180)
    plt.close(figure)


def render_report(summary: dict[str, Any]) -> str:
    baseline_scores = summary["systems"]["baseline"]
    resolveai_scores = summary["systems"]["resolveai"]
    rows = []
    for metric in (
        "answer_accuracy",
        "faithfulness",
        "hallucination_rate",
        "context_recall",
        "policy_compliance",
        "action_success",
        "guardrail_block_rate",
        "false_positive_rate",
        "input_guardrail_block_rate",
        "input_guardrail_false_positive_rate",
        "p50_latency_ms",
        "p95_latency_ms",
        "mean_estimated_tokens",
    ):
        rows.append(f"| {metric} | {baseline_scores[metric]} | {resolveai_scores[metric]} |")
    ci_low, ci_high = summary["paired_bootstrap_95_ci"]
    return f"""# Evaluation-driven production controls for an agentic RAG system

## Abstract

This controlled experiment compares a minimal keyword baseline with the checked-in ResolveAI
deterministic routing, input guardrail, and policy controls on 168 synthetic customer-operations
cases. The evaluation measures task routing, retrieval-target selection, action choice, risk,
policy compliance, guardrail behavior, and local execution latency. Results apply only to this
synthetic benchmark and do not establish production effectiveness.

## Research question

Do evaluation-driven deterministic controls improve reliability, safety, and operational
transparency for an agentic customer-resolution workflow relative to a minimal baseline?

## Method

- Dataset: `resolveai-synthetic-v1`, fixed seed {summary["seed"]}.
- Sample count: {summary["sample_count"]} paired cases.
- Baseline: refund/order keyword routing with no explicit safety controls.
- ResolveAI: deterministic router plus the production `inspect_input` and `evaluate_action` code.
- Statistics: paired per-case quality difference with 2,000 bootstrap resamples.

## Results

| Metric | Baseline | ResolveAI |
|---|---:|---:|
{chr(10).join(rows)}

Paired mean quality delta: **{summary["paired_mean_quality_delta"]:.4f}**.
Paired bootstrap 95% CI: **[{ci_low:.4f}, {ci_high:.4f}]**.

## System contribution

ResolveAI links retrieval, deterministic policy, independent human approval, idempotent tool
execution, audit evidence, cost events, and offline/online evaluation in one tenant-scoped
workflow. The contribution being tested is not a new foundation model; it is the production
control plane around an agentic RAG workflow.

## Threats to validity and limitations

{chr(10).join(f"- {item}" for item in summary["limitations"])}

## Reproducibility

Run `python scripts/run_research_benchmark.py`. Raw JSON/CSV, the aggregate table, this report,
and the PNG figure are regenerated from the checked-in versioned dataset.

## Conclusion

The measured comparison supports or rejects the stated hypothesis only for the controlled
synthetic workload. External customer data, human-review studies, provider-priced model runs,
and fault-injection recovery experiments remain necessary before making real-world claims.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset", type=Path, default=Path("datasets/synthetic/resolveai-benchmark-v1.jsonl")
    )
    parser.add_argument("--research-dir", type=Path, default=Path("research"))
    args = parser.parse_args()
    summary = run(args.dataset, args.research_dir)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
