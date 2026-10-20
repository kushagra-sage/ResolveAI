# ResolveAI Research Plan

## Research questions

**RQ1.** Can evaluation-driven production controls improve the reliability, safety,
observability, and cost efficiency of agentic RAG workflows for customer resolution?

**RQ2.** Can minimized customer-support signals support explainable anomaly detection,
evidence-grounded root-cause ranking, and policy-compliant corrective actions on a versioned
synthetic CommerceOps benchmark?

## Contribution discipline

- **Engineering contribution:** an integrated, multi-tenant reference implementation combining
  hybrid RAG, LangGraph orchestration, deterministic guardrails and policy, digest-bound HITL,
  verified tools, evaluation, telemetry, and cost accounting.
- **Experimental contribution:** controlled, paired comparisons on versioned synthetic datasets
  with raw results, uncertainty, negative results, and reproducible manifests.
- **Potential academic contribution:** evidence about the trade-offs of external production
  controls and the transformation of support interactions into closed-loop operational signals.
  No individual component is claimed as novel.

## Current measurable evidence

Already implemented and measurable:

- deterministic answer-term/context recall, citation/action correctness, and safety pass;
- paired experiment deltas and Pareto helpers;
- approval outcomes, reviewer separation, approval latency, edit invalidation, and hard ceilings;
- request/retrieval/agent-node/tool/guardrail/evaluation Prometheus metrics;
- cost events with known-vs-unknown price semantics;
- trace/run/step coverage in PostgreSQL;
- load-smoke latency and errors;
- RBAC, tenant isolation, RLS, idempotency, recovery, and security regression tests.

Instrumentation or implementation still required:

- faithfulness, answer relevance, context precision, retrieval Recall@K and MRR;
- complete trace-span coverage and required-metadata completeness reports;
- LLM/retrieval/tool latency separation in persisted experiment output;
- retry, fallback, recovery, and routing comparison endpoints;
- human-review study instrumentation;
- signal/anomaly/root-cause/action-outcome schemas and metrics;
- provider-backed token/cost experiments if external models are introduced.

## Dataset programme

All generated inputs are labeled **synthetic** and versioned with a content hash.

1. `resolution-core`: 200–500 normal, hard, ambiguous, multi-document, stale/conflicting,
   out-of-domain, and retrieval-failure cases.
2. `security-redteam`: prompt injection, jailbreak, PII extraction, privilege escalation,
   cross-tenant and tool-manipulation cases.
3. `agent-tools`: expected tools, typed arguments, forbidden actions, recovery expectations.
4. `commerce-signals`: support interactions mapped to controlled operational categories.
5. `commerce-timeseries`: normal operations plus seeded stockout, staffing, delivery, supplier
   batch, and payment incidents with ground-truth windows and causes.

Each case records expected behavior rather than a single prose answer wherever possible.

## Reproducibility manifest

Every run records: git commit (or `uncommitted` plus worktree digest), timestamp, dataset name,
version and SHA-256, random seed, code/runtime versions, RAG/prompt/model/embedding versions,
temperature, retrieval and reranking configuration, guardrail/policy versions, environment, and
completed sample count.

## Paper plan (maximum ten pages)

1. Abstract and introduction — 1 page
2. Related work and contribution boundary — 1 page
3. Architecture and threat model — 1.5 pages
4. Methodology and datasets — 1.5 pages
5. Experimental setup — 1 page
6. Results — 2 pages
7. Discussion and limitations — 1 page
8. Conclusion and reproducibility — 0.5 page

Figures and tables are generated from result files only. The paper draft starts after the
experiment pipeline and datasets are stable.

## Threats to validity

- Synthetic cases may not represent real organizational language or base rates.
- Hand-authored expected answers and rules can encode author bias.
- LLM-as-judge, if added, has model, prompt, position, and self-preference bias.
- Small samples exaggerate variance and hide rare safety failures.
- External providers introduce nondeterminism, version drift, outages, and cost constraints.
- Local Docker latency does not estimate production capacity.
- Reusing cases during development risks benchmark overfitting.
- Multiple comparisons can create false discoveries without preregistered primary metrics.

Mitigations include held-out splits, paired evaluation, deterministic metrics where possible,
bootstrap confidence intervals, blinded human review subsets, repeated provider runs, manifest
capture, and explicit separation of exploratory from confirmatory experiments.

