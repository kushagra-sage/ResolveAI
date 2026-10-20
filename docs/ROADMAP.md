# ResolveAI Delivery Roadmap

**Status:** Phases 0–13 delivered and locally verified; production prerequisites remain  
**Last updated:** 2026-10-03  
**Rule:** A phase is complete only when its acceptance evidence exists. Calendar estimates are intentionally omitted until team capacity and provider constraints are known.

## Current delivery status

| Phase | Status | Evidence / remaining work |
|---|---|---|
| Phase 0 | Locally verified | Toolchains, Compose, Makefile, CI, specifications, architecture, ADRs, and operational documentation execute in the configured workspace. |
| Phase 1 | Locally verified | PostgreSQL migration head, JWT/RBAC, forced RLS, two-tenant seed, cross-tenant FK rejection, and restricted-role checks passed. Managed PostgreSQL/IAM remains a deployment choice. |
| Phase 2 | Locally verified | Versioned ingestion, five chunkers, deterministic embeddings, citations, filters, and a 5,000-row HNSW query-plan check passed. Production embedding provider/corpus remain deployment inputs. |
| Phase 3 | Locally verified | Query rewrite, hybrid RRF, deterministic reranking, retrieval event persistence, and abstention paths are tested. Production-domain calibration remains external. |
| Phase 4 | Locally verified | Seventeen instrumented LangGraph nodes, authorized context loading, durable steps/state, bounded execution, and restart-safe resume are tested. Production provider concurrency remains external. |
| Phase 5 | Locally verified | Deterministic policy, immutable replacement approvals, separation of duty, idempotent tools, unknown-outcome reconciliation, refund verification, audit, and outbox paths passed unit and live PostgreSQL checks. Real payment sandbox credentials remain external. |
| Phase 6 | Locally verified | Input/external/output guards, redaction, persisted guard events, adversarial fixtures, and invariant tests pass. Independent red-team review remains external. |
| Phase 7 | Locally verified | Live API-to-OTLP spans, Prometheus API/collector targets, Grafana provisioning, privacy filtering, and correlation IDs were exercised. Hosted telemetry and retention remain deployment inputs. |
| Phase 8 | Locally verified | Complete cost dimensions, tenant-admin reporting, unknown-cost semantics, bounded retry/backoff/jitter/circuit/fallback, and observed embedding/tool events are present. Provider invoice reconciliation remains external. |
| Phase 9 | Locally verified | Versioned datasets, deterministic evaluators, JSON/Markdown/HTML reports, durable sampled online jobs, retries, and DLQ state pass configured gates. Paid judge runs are not claimed. |
| Phase 10 | Locally verified | A paired two-configuration experiment was stored with per-case deltas; the worse candidate was correctly not promoted. Larger representative datasets remain external. |
| Phase 11 | Locally verified | Versioned release gates, CI enforcement, sanitized write-disabled shadowing, sticky staged canary allocation, and rollback behavior are tested. Target-platform rollout remains external. |
| Phase 12 | Locally verified baseline | The production TypeScript build and API-backed approval list/edit/reject/execute workflow pass, including semantic labels and live status. Cross-browser/a11y automation and production IdP UX remain deployment acceptance work. |
| Phase 13 | Locally verified within available credentials | Seven-service Compose, a 200-request load smoke, backup/restore, Redis/OTel/PostgreSQL outage drills, static analysis, and dependency audits ran successfully. Docker Scout CVE analysis is blocked on registry login; independent penetration testing remains external. |
| CommerceOps extension | Locally verified | Operational facts, robust-z/EWMA/rate-change detection, persisted detector evaluation, scheduled worker execution, risk APIs, evidence-grounded causes, HITL/idempotent actions, outcomes, and live web surfaces pass local verification. Production event connectors and a domain-labeled corpus remain external inputs. |

## 1. Delivery method

Each subsystem follows the same reviewable loop:

1. State the bounded capability and non-goals.
2. Identify upstream contracts and external dependencies.
3. Add or refine acceptance tests before implementation.
4. Implement the smallest end-to-end slice.
5. Run deterministic tests and relevant integration/evaluation checks.
6. Update architecture, security, operations, and decision documents.
7. Commit a coherent change with generated artifacts excluded unless intentionally versioned.

No phase may claim quality, latency, cost, security, or business results without a recorded run. Dashboards use `NOT MEASURED YET` until data exists.

## 2. Cross-phase definition of done

From Phase 1 onward, every completed implementation phase must satisfy the applicable items below. Phase 0 is documentation/tooling only; implementation-only items such as migrations, runtime authorization tests, and telemetry evidence are explicitly not applicable until their owning phase.

- all new public contracts are typed and versioned;
- tenant and authorization behavior is tested for allowed and denied paths;
- failure behavior is explicit, bounded, and observable;
- secrets and sensitive PII are absent from fixtures, logs, traces, and committed artifacts;
- tests run locally through the documented task runner;
- documentation matches implemented behavior;
- migrations are forward-tested and rollback/repair behavior is documented;
- no silent core `TODO` remains in the phase acceptance path;
- any measured result records versions, workload/dataset, sample size, and timestamp.

## 3. Milestones

### Phase 0 — Architecture, repository, and development foundation

**Build**

- Establish the project specification, architecture, roadmap, and ADR log.
- Initialize repository conventions, Python/Node toolchains, formatting/lint/type-check commands, environment template, Makefile, Docker Compose skeleton, and cheap CI skeleton.
- Define architecture contracts before runtime implementation.

**Dependencies**

- Agreement on scope, supported personas, safety invariants, initial provider abstraction, and local platform prerequisites.

**Acceptance evidence**

- `docs/PROJECT_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, and `docs/DECISIONS.md` reviewed for consistency.
- Repository commands and environment variable contract documented.
- CI can install dependencies and run no-op/initial lint/test jobs without paid model calls.
- Docker configuration validates syntactically.
- No metric is shown as measured.
- Review evidence is the dated Phase 0 decision-log entry recording reviewer, outcome, and accepted risks.

**Exit decision**

- Architecture review explicitly authorizes Phase 1. This document set alone does not authorize production deployment.

### Phase 1 — Database, API skeleton, RBAC, and tenant isolation

**Build**

- PostgreSQL extensions, Alembic migrations, tenant/identity/commerce/support/workflow base tables, and synthetic seed data.
- FastAPI application factory; liveness/readiness endpoints; request/trace middleware.
- Token validation, server-derived tenant context, permission service, and PostgreSQL row-level security.

**Dependencies**

- Phase 0 schema/authorization decisions; local PostgreSQL; test identity provider or signed-token fixture.

**Acceptance evidence**

- Fresh database migrates from zero and seeds deterministically.
- Composite tenant/parent foreign-key tests reject cross-tenant references and wrong-parent links; constraints also reject negative money values, duplicate external IDs (including nullable global-key cases), and invalid statuses.
- RBAC tests cover customer, agent, supervisor, admin, expired membership, and unknown permission.
- Tenant isolation tests attempt direct-ID and query-filter bypass at API and database layers.
- Health/readiness endpoints distinguish process health from PostgreSQL readiness.
- API OpenAPI contract and migration repair/rollback notes exist.

### Phase 2 — Knowledge ingestion, chunking, embeddings, and basic retrieval

**Build**

- Document/version ingestion with checksums, effective dates, source metadata, and idempotent re-ingestion.
- Fixed-token, recursive, and heading-aware chunkers first; semantic and parent-child may be added when their experiment phase begins, but their interface is fixed now.
- Embedding provider port, pgvector storage/index, tenant/audience/effective-date filters, dense retrieval, and citation objects.

**Dependencies**

- Phase 1 database; version registry; synthetic KB; embedding provider or deterministic test embedding.

**Acceptance evidence**

- Re-ingesting identical content creates no duplicate current version/chunks.
- Changed content creates a new immutable document version.
- Retrieval cannot return another tenant’s or wrong-audience chunks.
- Citation IDs resolve to the exact document version and chunk checksum used.
- Deterministic retrieval fixture tests run without paid APIs.
- Index plan and query behavior are inspected on representative synthetic volume; no performance claim is made without the run artifact.

### Phase 3 — Hybrid retrieval, reranking, RAG versions, and failure detection

**Build**

- PostgreSQL FTS, dense/keyword retrieval, fusion, optional query rewrite, reranker port, calibrated threshold configuration, and immutable RAG versions.
- Structured retrieval failure detector and events.
- Safe abstention contract.

**Dependencies**

- Phase 2 retrieval/citations; initial golden retrieval dataset; model/reranker test doubles.

**Acceptance evidence**

- The same request records exactly one pinned RAG version.
- Unit/integration tests cover zero result, low relevance, stale policy, conflicting documents, missing category, dense/keyword disagreement, timeout, and vector/embedding failures.
- Hybrid rank fusion is deterministic for identical inputs and configuration.
- Abstention occurs below configured evidence thresholds.
- Retrieval metrics are produced from a real smoke run and labeled with dataset/configuration; otherwise displayed as `NOT MEASURED YET`.

### Phase 4 — LangGraph orchestration and read-only support workflow

**Build**

- Versioned `ResolutionState`, explicit graph nodes, PostgreSQL checkpointer, run/step persistence, graph limits, and error taxonomy.
- Read-only CRM/order/shipment tools behind capability-specific interfaces.
- Informational support workflow with grounded response and escalation.

**Dependencies**

- Phases 1–3; model provider abstraction; tool stubs/sandbox providers.

**Acceptance evidence**

- Node/edge contract tests cover informational success, insufficient evidence, model failure/fallback, retrieval failure, max steps, and loop detection.
- A process-restart test resumes from a persisted non-side-effect checkpoint.
- Read tools enforce tenant and resource access independent of model output.
- Cache keys, checkpoint lookup, and stream envelopes/consumers reject tenant mismatches in integration tests.
- Every node appears as a trace span with the run/trace correlation IDs.
- No write-capable tool is reachable in this phase.

### Phase 5 — Policy engine, authorized tools, approval, and durable execution

**Build**

- Deterministic versioned policy engine and policy decision persistence.
- Ticket writes, refund proposal/execution, and account-closure request tools.
- Approval APIs/UI baseline, graph interrupt/resume, action digest, separation-of-duty controls, execution verification, and transactional outbox.

**Dependencies**

- Phase 4 state/durability; Phase 1 identity/RBAC; provider sandboxes; approved policy matrix.

**Acceptance evidence**

- Decision-table tests cover every declared initial policy rule and each allow/approval/deny branch across role, tenant, resource state, missing facts, and configured threshold boundaries; coverage is traced to rule IDs.
- Side effects cannot be invoked without an execution record and idempotency key.
- Crash tests before call, during unknown outcome, after provider success, and before local persistence reconcile without duplicate effect.
- Approval survives restart; approve/edit/reject are audited; edit changes the digest.
- Authorization and policy are re-evaluated after resume and immediately before execution.
- Cross-tenant, secret-read, payment-destination, expired approval, self-approval (when prohibited), and stale-resource attempts never call providers.

### Phase 6 — Guardrails, PII protection, and adversarial suite

**Build**

- Input, external-content quarantine, and output guardrail pipelines.
- Deterministic PII/secret detectors and redaction; optional model safety classifiers as defense in depth.
- Versioned adversarial dataset and security regression harness.

**Dependencies**

- Tool/RAG/model boundaries from Phases 2–5; threat model and data-classification policy.

**Acceptance evidence**

- Tests cover prompt override, fake admin approval, approval bypass, cross-customer access, system-prompt extraction, document/tool injection, repeat-refund loop, destination change, and environment-secret extraction.
- Retrieved malicious instructions remain data and do not change the tool plan.
- Known PII/secret fixtures are redacted before model/telemetry boundaries.
- Output guard blocks unsupported sensitive data and malformed structured output.
- Adversarial reports show counts and actual measured rates only after execution; fixture expectations are not presented as achieved rates.
- High-risk invariant tests observe no unauthorized provider side effect.

### Phase 7 — OpenTelemetry, Prometheus, Grafana, Langfuse, and failure operations

**Build**

- OTel SDK/collector/exporters, structured logging, Prometheus metrics, Grafana provisioning, and Langfuse adapter.
- Trace propagation through HTTP, graph, tool service, Redis stream, and worker.
- Operational dashboards and initial runbooks tied to the failure taxonomy.

**Dependencies**

- Instrumentable paths from previous phases; local observability stack.

**Acceptance evidence**

- One test request correlates API, graph, retrieval, model, tool, audit, and async worker activity by trace/span links.
- Telemetry privacy tests detect prohibited attributes/content.
- API/backend access tests prevent cross-tenant trace, Langfuse, evaluation-artifact, and dashboard access; platform break-glass access is separately authorized and audited.
- Prometheus label audit confirms bounded label domains and excludes tenant/user/run/query text.
- Dashboards render real local scrape data or explicit no-data panels, never hard-coded values.
- Exporter failure does not break the customer path; loss behavior is documented.
- Runbooks cover model, retrieval, PostgreSQL, Redis, tool, queue, and telemetry failures.

### Phase 8 — Cost accounting, provider routing, and fallback resilience

**Build**

- Provider/model adapter, usage normalization, effective-dated pricing, cost events, retry/backoff/circuit behavior, and bounded fallback routing.
- Cost aggregations by tenant, model, feature, agent path, prompt, RAG version, and endpoint.

**Dependencies**

- Phase 7 traces/metrics; provider usage response contracts; pricing sources.

**Acceptance evidence**

- Golden arithmetic tests cover input/output/cached tokens, embeddings, missing prices, and effective-date boundaries.
- Unknown cost is distinguishable from zero.
- Timeout/rate-limit/provider error tests show bounded retry then allowed fallback or safe escalation.
- Malformed fallback output still fails validation and cannot bypass policy.
- Dashboard values reconcile to underlying cost-event queries for a recorded test run.
- No optimization savings are claimed.

### Phase 9 — Offline evaluation harness and experiment tracking

**Build**

- Dataset/case manifests, deterministic evaluators, DeepEval/RAGAS adapters, optional LLM judges, run/result/score persistence, JSON and Markdown/HTML reports.
- Evaluation Lab APIs and baseline comparison view.

**Dependencies**

- Stable version tuple; representative synthetic golden/adversarial datasets; Phase 8 cost data.

**Acceptance evidence**

- Dataset hashes and all configuration/version IDs are stored with every run.
- Interrupted runs resume or terminate explicitly without fabricating missing scores.
- Deterministic evaluator contract tests cover expected/forbidden action, citations, retrieval, PII, and policy outcomes.
- Judge failures/non-applicability are distinct from score zero.
- Re-running a deterministic fixture yields identical results.
- At least one smoke run produces machine- and human-readable artifacts; any model-based result is labeled with judge/version/sample size.

### Phase 10 — RAG evolution experiments

**Build**

- Semantic and parent-child chunkers, experiment matrix runner, configuration registry, paired comparison, and Pareto visualization.
- Controlled comparisons of chunker, retriever, reranker, top-k/top-n, embeddings, models, and prompts.

**Dependencies**

- Phase 9 harness; sufficient dataset coverage; resource/budget guardrails.

**Acceptance evidence**

- Each comparison changes only declared factors or records the full factorial configuration.
- Baseline and candidate use identical case sets; missing cases are visible.
- Reports include quality, safety, latency, cost, retrieval health, and sample counts.
- Candidate recommendation documents trade-offs and does not auto-deploy.
- Results are stored artifacts from actual runs, not copied example values.

### Phase 11 — Regression gates, shadow architecture, and release metadata

**Build**

- Versioned gate configuration and CI evaluator.
- Explicit paid/full evaluation workflow separate from cheap deterministic CI.
- Shadow-run pipeline with sanitized inputs, write-disabled identity, candidate version metadata, and baseline comparison.
- Deployment records capable of stable/candidate allocation and rollback metadata.

**Dependencies**

- Phases 7–10; approved privacy sampling policy; release process.

**Acceptance evidence**

- CI fails separately for missing metric, evaluator failure, insufficient samples, and threshold breach.
- Safety gates cannot be offset by higher aggregate quality.
- Shadow candidate cannot acquire or invoke side-effect credentials in integration tests.
- Stable/candidate results correlate without affecting customer response.
- Rollback metadata and decision procedure are exercised in staging.

### Phase 12 — Production-style web application

**Build**

- Polished support workspace, approval center, observability dashboard, cost dashboard, evaluation lab, RAG evolution view, and trace explorer.
- Accessible design system, role-aware navigation, error/empty/loading states, and secure API integration.

**Dependencies**

- Stable APIs from Phases 1–11; UI threat model; representative test data.

**Acceptance evidence**

- End-to-end tests cover informational resolution, abstention, approval/edit/reject, execution verification, trace navigation, and experiment comparison.
- Role tests prevent customer/agent access to supervisor/admin surfaces.
- Approval UI displays the immutable action digest/snapshot and warns when revalidation invalidates approval.
- Dashboard no-data states say `NOT MEASURED YET`; synthetic/demo data is visibly labeled.
- Accessibility, responsive layout, browser, and frontend security checks pass at configured thresholds.

### Phase 13 — Load, security, operations, and deployment readiness

**Build**

- Small reproducible load test, security review, dependency/static/container scanning, backup/restore rehearsal, failure drills, complete runbooks, demo dataset, and deployment guide.
- Production-readiness checklist and residual-risk review.

**Dependencies**

- Integrated system; target deployment constraints; approved security and reliability criteria.

**Acceptance evidence**

- Load-test artifact records hardware, configuration, dataset, concurrency, latency/error outcomes, and date; results are not generalized beyond the run.
- Threat model and penetration/security findings have dispositions.
- PostgreSQL backup/restore and Redis/outbox recovery are rehearsed.
- Dependency/provider outage drills demonstrate documented degradation and recovery.
- Fresh-environment deployment follows the guide successfully.
- Final documentation includes `README.md`, `SECURITY.md`, `EVALUATION.md`, `OBSERVABILITY.md`, `COST.md`, `THREAT_MODEL.md`, and `RUNBOOK.md` consistent with evidence.

## 4. Recommended vertical slices

Phases remain governance gates, but implementation should stay demonstrable through vertical slices:

1. Authenticated “where is my order?” using deterministic fixtures.
2. Grounded policy answer with citation and abstention.
3. Low-risk ticket note with idempotent execution and verification.
4. Refund proposal requiring approval, restart, resume, revalidation, and sandbox execution.
5. Adversarial request demonstrating deterministic denial and full trace.
6. Offline evaluation comparing two real RAG configurations.

Each slice should include API, data, policy/security, telemetry, and tests rather than creating large unintegrated horizontal subsystems.

## 5. Change control

- Architecture changes require an ADR before or with implementation.
- Schema changes require a migration and data/backfill/rollback plan.
- Policy changes require versioning, policy tests, and an effective-date plan.
- Prompt/RAG/model changes require a new immutable version and relevant evaluation.
- Pricing changes create a new effective-dated pricing record.
- Dataset case edits create a new dataset version/hash; historical runs remain attached to the old version.
- Gate threshold changes require rationale and cannot rewrite historical pass/fail results.

## 6. Immediate next review

The former Phase 0 owner questions are resolved by ADR-013 through ADR-022 in `DECISIONS.md`. Production-specific issuer, retention, provider-contract, infrastructure, and company-policy values remain deployment inputs rather than open architecture choices.
