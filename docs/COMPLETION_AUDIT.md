# ResolveAI Completion Audit

**Audit date:** 2026-10-07  
**Rule:** “Implemented” requires a runtime contract and focused test. “Verified” requires evidence at the scope claimed. External production results are never inferred from deterministic fixtures.

| Area | Delivered and verified | Remaining external prerequisite |
|---|---|---|
| Phase 1 database/RLS | PostgreSQL 16 migration head, restricted-role RLS checks, cross-tenant composite-FK rejection, two seeded tenants, production-guarded OIDC/JWKS verifier, live Keycloak end-user flow, and least-privilege client credentials | Production issuer/client registration and managed PostgreSQL/IAM selection |
| Phase 2 ingestion | Immutable versions, five chunkers, deterministic embeddings, citations, audience isolation, 5,000-row rollback-only HNSW `EXPLAIN ANALYZE` | Production embedding provider and corpus |
| Phase 3 retrieval | Query rewrite, dense/lexical RRF, deterministic reranker, persisted retrieval/failure events, abstention | Calibrated production-domain evaluation set |
| Phase 4 workflow | Seventeen instrumented LangGraph nodes, real knowledge/order context, persisted state/steps, resource-authorized reads, separate-request resume | Production model/tool providers |
| Phase 5 actions | Configurable 5k/50k/100k demo thresholds, one/two-person approval chains, 30-minute TTL, immutable edited snapshots, idempotency payload conflicts, partial-refund ceiling, reconciliation, verified sandbox refunds, and a live distinct-reviewer/ceiling check | Real payment provider adapter/webhook credentials only if selected for production |
| Phase 6 safety | Input/output/external-content guards, persisted guardrail events, adversarial fixture | Independent red-team exercise |
| Phase 7 observability | Live API→OTLP collector spans, Prometheus scrape targets, Grafana provisioning, bounded-label service/RAG/node/tool/approval/eval/business instruments | Hosted telemetry/Langfuse destination and retention policy |
| Phase 8 cost/resilience | Complete cost dimensions, embedding/tool events, tenant-admin summary API, exponential backoff/jitter/circuit/fallback | Provider price feed and invoice reconciliation |
| Phase 9 evaluation | JSON/Markdown/HTML reports, deterministic sampling, durable online queue/worker/retry/DLQ, versioned datasets | Optional paid/judge evaluators (DeepEval/RAGAS/provider judge) |
| Phase 10 evolution | Real paired two-configuration local run with stored per-case deltas; candidate performed worse on one fixture and is not promoted | Larger representative dataset |
| Phase 11 release | Versioned gate config/CLI, CI gate, sanitized write-disabled shadow contract, sticky canary allocation and rollback tests | Target deployment platform |
| Phase 12 web | Keycloak Authorization Code + PKCE login/logout/refresh, role-aware navigation, functional admin and knowledge workspaces, backend-driven evidence pages, Customer 360, production TypeScript build, approval workflows, and a passing 13-test Chromium workflow/accessibility/screenshot suite | Production IdP registration and broader device/browser acceptance on target infrastructure |
| Phase 13 readiness | Default seven-service Compose deployment plus verified Keycloak and SeaweedFS profiles; 200-request load artifact; backup/restore; Redis/OTel/PostgreSQL outage drills; static, dependency, and container-image scans. The API and local object-store images have zero fixed High/Critical Trivy findings. | Target deployment platform and managed production object-store selection |
| CommerceOps extension | Customer signals, operational facts, three explainable detectors, persisted precision/recall evaluation, scheduled Docker worker, three risk APIs, evidence-grounded root causes, policy/HITL action execution, outcomes, and live React surfaces are locally verified. | Production ERP/WMS/quality connectors and domain-labeled evaluation corpus |

Local evidence is reproducible with `scripts/verify_postgres.py`, `scripts/run_eval.py`,
`scripts/run_experiment.py`, and `scripts/load_smoke.py`. Results under `artifacts/` are
local and intentionally ignored by Git. They are not production claims.
