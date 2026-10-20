# Evaluation-driven production controls for an agentic RAG system

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

- Dataset: `resolveai-synthetic-v1`, fixed seed 20261006.
- Sample count: 168 paired cases.
- Baseline: refund/order keyword routing with no explicit safety controls.
- ResolveAI: deterministic router plus the production `inspect_input` and `evaluate_action` code.
- Statistics: paired per-case quality difference with 2,000 bootstrap resamples.

## Results

| Metric | Baseline | ResolveAI |
|---|---:|---:|
| answer_accuracy | 0.17857142857142858 | 1.0 |
| faithfulness | 0.21428571428571427 | 1.0 |
| hallucination_rate | 0.7857142857142857 | 0.0 |
| context_recall | 0.21428571428571427 | 1.0 |
| policy_compliance | 0.4642857142857143 | 1.0 |
| action_success | 0.21428571428571427 | 1.0 |
| guardrail_block_rate | 0.0 | 1.0 |
| false_positive_rate | 0.0 | 0.0 |
| input_guardrail_block_rate | 0.0 | 0.5 |
| input_guardrail_false_positive_rate | 0.0 | 0.0 |
| p50_latency_ms | 0.0008 | 0.0438 |
| p95_latency_ms | 0.0016 | 0.1197 |
| mean_estimated_tokens | 29.821428571428573 | 53.82142857142857 |

Paired mean quality delta: **0.5491**.
Paired bootstrap 95% CI: **[0.5097, 0.5863]**.

## System contribution

ResolveAI links retrieval, deterministic policy, independent human approval, idempotent tool
execution, audit evidence, cost events, and offline/online evaluation in one tenant-scoped
workflow. The contribution being tested is not a new foundation model; it is the production
control plane around an agentic RAG workflow.

## Threats to validity and limitations

- All cases are synthetic and results do not establish production impact.
- Latency measures local deterministic Python execution, not network or model latency.
- Token usage is estimated; local deterministic execution has no model-provider cost.
- Recovery is measured in the separate resilience experiment because this task dataset contains no fault-injection cases.

## Reproducibility

Run `python scripts/run_research_benchmark.py`. Raw JSON/CSV, the aggregate table, this report,
and the PNG figure are regenerated from the checked-in versioned dataset.

## Conclusion

The measured comparison supports or rejects the stated hypothesis only for the controlled
synthetic workload. External customer data, human-review studies, provider-priced model runs,
and fault-injection recovery experiments remain necessary before making real-world claims.
