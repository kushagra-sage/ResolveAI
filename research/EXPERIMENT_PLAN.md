# ResolveAI Experiment Plan

## Common protocol

All experiments load a versioned dataset, validate its schema, fix a random seed, execute every
configuration on the same case IDs, save per-case raw output, aggregate metrics, compute 95%
paired-bootstrap confidence intervals where appropriate, and generate CSV tables and PNG figures.

Planned output contract:

```text
research/results/<experiment>/<run-id>/manifest.json
research/results/<experiment>/<run-id>/raw.json
research/results/<experiment>/<run-id>/summary.json
research/tables/<experiment>.csv
research/figures/<experiment>.png
```

## E1 — Basic RAG vs hybrid RAG plus reranking

- **Hypothesis:** hybrid retrieval with reranking improves retrieval recall and grounded answer
  quality, with increased latency.
- **Independent variable:** chunker/retriever/reranker configuration.
- **Primary metrics:** Recall@K, MRR, context recall, citation correctness.
- **Secondary metrics:** faithfulness, answer relevance, P50/P95 latency, cost/query.
- **Dataset:** held-out `resolution-core` multi-document subset.
- **Configurations:** fixed+dense baseline; heading/parent-child+hybrid+reranking candidate.

## E2 — Guardrails and deterministic policy

- **Hypothesis:** guardrails plus external policy reduce attack success and unauthorized actions
  without an unacceptable false-positive rate.
- **Variable:** controls disabled vs input/output guards vs guards+policy.
- **Metrics:** attack success, block rate, false-positive rate, PII leakage, unauthorized action,
  safe-refusal accuracy.
- **Dataset:** `security-redteam` plus matched benign controls.

## E3 — Model routing and cost

- **Hypothesis:** difficulty/risk-aware routing reduces cost per correctly resolved case while
  preserving safety and quality gates.
- **Variable:** one model for all cases vs routing policy.
- **Metrics:** task completion, safety, input/output tokens, cost/request, cost/resolution,
  P95 latency.
- **Constraint:** run only after reviewed provider pricing and model access are configured.

## E4 — Recovery controls

- **Hypothesis:** bounded retry/fallback improves recovery without increasing duplicate actions.
- **Variable:** no recovery vs retry vs retry+fallback+circuit breaker.
- **Metrics:** recovery rate, error rate, retries, fallback rate, latency, duplicate execution.
- **Method:** deterministic fault injection for embeddings, retrieval, model, Redis, and tools.

## E5 — Customer resolution vs closed-loop CommerceOps

- **Hypothesis:** support-derived structured signals improve anomaly detection and root-cause
  ranking over operational facts alone.
- **Variable:** operational facts only vs facts+customer signals.
- **Metrics:** anomaly precision/recall/F1, detection delay, Top-1 root-cause accuracy, Top-3
  recall, evidence grounding, action relevance, policy compliance, unsafe-action rate.
- **Dataset:** versioned synthetic operational time series with seeded incident ground truth.

## Evaluation case schema

Required fields: `case_id`, `category`, `question`, `expected_answer_terms`,
`expected_documents`, `expected_action`, `forbidden_action`, `risk_level`, `expected_policy`,
`expected_tool`, `expected_tool_args`, `expected_behavior`, `split`, and `tags`.

Operational cases additionally include entities, event window, ground-truth anomaly interval,
root cause, acceptable actions, forbidden actions, and expected effect metric.

## Reporting rules

- Report completed `n`, missing metrics, evaluator failures, and excluded cases.
- Never replace missing values with zero.
- Safety gates are non-compensatory.
- Negative and null results remain in the paper.
- Claims use “on the synthetic benchmark” unless external validation exists.
- Exploratory configuration selection and final held-out evaluation use different case splits.

