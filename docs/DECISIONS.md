# ResolveAI Architecture Decisions, Reference Review, and Risk Register

**Status:** Owner defaults accepted; living decision log  
**Last updated:** 2026-10-03

## 1. Decision process

Accepted decisions in this file form the Phase 0 baseline. A decision may be superseded by a later ADR; historical text remains for traceability. Proposed choices that need owner/provider input are listed separately and must not silently become implementation defaults.

## 2. ADR index

| ADR | Decision | Status |
|---|---|---|
| ADR-001 | Start as a modular monolith with isolated capability services | Accepted |
| ADR-002 | PostgreSQL is the durable system of record; Redis is ephemeral | Accepted |
| ADR-003 | Authorization/policy/approval are deterministic security boundaries | Accepted |
| ADR-004 | Model output is a proposal, never execution authority | Accepted |
| ADR-005 | Side effects use idempotency, execution records, and verification | Accepted |
| ADR-006 | Version every nondeterministic configuration and evaluation input | Accepted |
| ADR-007 | OpenTelemetry is the vendor-neutral observability foundation | Accepted |
| ADR-008 | Retrieval is evidence-oriented and allowed to abstain | Accepted |
| ADR-009 | Online evaluation is asynchronous and privacy-controlled | Accepted |
| ADR-010 | No measured claim without a recorded run artifact | Accepted |
| ADR-011 | Use PostgreSQL RLS as defense in depth for tenant isolation | Accepted |
| ADR-012 | Shadow candidates are physically write-disabled | Accepted |
| ADR-013 | OIDC/OAuth2 is the production identity profile; local signing is test-only | Accepted |
| ADR-014 | Cross-tenant operator access requires an audited break-glass grant | Accepted |
| ADR-015 | Retention is data-class/tenant/jurisdiction configurable with legal hold | Accepted |
| ADR-016 | Payments begin with an idempotent deterministic sandbox provider | Accepted |
| ADR-017 | Model and embedding providers use normalized, policy-gated ports | Accepted |
| ADR-018 | Artifacts use tenant-scoped S3-compatible object storage | Accepted |
| ADR-019 | LangGraph checkpointing uses a maintained adapter behind a repository port | Accepted |
| ADR-020 | Approval thresholds and multi-principal obligations are configuration | Accepted |
| ADR-021 | Provider eligibility is controlled by explicit data classification | Accepted |
| ADR-022 | ResolveAI is licensed under Apache-2.0 | Accepted |

## 3. Accepted decisions

### ADR-001 — Modular monolith plus isolated capability services

**Context:** The requested scope contains many domains and could lead to premature microservices. It also contains high-risk tools whose credentials and blast radius benefit from process boundaries.

**Decision:** Keep API orchestration, RAG, policy, guardrails, evaluation contracts, cost, and observability as well-factored Python packages deployed initially with the API/worker applications. Isolate CRM/orders/ticketing/payments/account capabilities as narrow services when credentials or side-effect boundaries justify it.

**Consequences:** Local development and transactions remain manageable. Package boundaries must be enforced in tests/import rules. Services can be extracted later from stable ports. Capability services incur network/auth/operations overhead only where the security value is real.

### ADR-002 — PostgreSQL durable truth; Redis ephemeral coordination

**Context:** Workflow checkpoints, approvals, audits, and experiment lineage must survive restarts and queue loss.

**Decision:** Store durable state in PostgreSQL. Use Redis for cache, locks with bounded leases, rate limiting, and at-least-once streams. Publish asynchronous work through a transactional outbox.

**Consequences:** Redis loss does not erase approvals or workflow truth. Consumers must be idempotent. Redis Streams is not represented as exactly-once delivery.

### ADR-003 — Deterministic security boundaries

**Context:** LLMs are nondeterministic and susceptible to adversarial input. They cannot decide whether a caller is authorized or an action is permitted.

**Decision:** Authentication, tenant resolution, RBAC/resource authorization, policy evaluation, approval validity, action digest matching, and execution permission are conventional deterministic code/rules. Model classifiers may add risk signals but can never weaken a deterministic outcome.

**Consequences:** Policy rules require explicit versioning and tests. A model can propose or explain but cannot approve or override.

### ADR-004 — Propose, validate, decide, execute

**Decision:** Separate action proposal from tool execution. Validate model arguments, enrich them with server-derived facts, evaluate authorization/policy, collect approval if needed, then execute through a scoped tool.

**Consequences:** More steps and records, but a small and auditable trusted computing base.

### ADR-005 — Idempotent, verifiable side effects

**Decision:** Every side-effect attempt has a persisted execution record and stable idempotency key. Unknown outcomes trigger reconciliation, not blind retry. “Success” requires an authoritative receipt/read-back.

**Consequences:** Provider adapters must expose idempotency/reconciliation semantics. Some providers without native keys require a local uniqueness guard plus careful status recovery.

### ADR-006 — Immutable version tuple

**Decision:** Each run records graph, prompt, RAG, model, embedding, policy, guardrail, tool, pricing, and relevant dataset/evaluator versions. Mutable aliases resolve once at run start.

**Consequences:** Storage and configuration management are more explicit. Historical evaluation and incident analysis become defensible.

### ADR-007 — OTel first, Langfuse specialized

**Decision:** OpenTelemetry carries cross-service traces and vendor-neutral correlation. Prometheus/Grafana handle operations metrics. Langfuse adds prompt/generation/evaluation detail but is not the sole record.

**Consequences:** Instrumentation needs adapters and duplicate-export discipline. The core remains portable if a specialized platform is replaced.

### ADR-008 — Evidence and abstention over forced answers

**Decision:** Retrieval and grounding return explicit failure signals. A low-evidence response abstains or escalates. Citations bind claims to exact document versions/chunks.

**Consequences:** Resolution rate may be lower than an always-answering bot, but failure is visible and calibratable.

### ADR-009 — Asynchronous online evaluation

**Decision:** The customer response is finalized before sampled expensive evaluation. An outbox queues a redacted, policy-approved evaluation job. Production judge access is separately authorized and retained.

**Consequences:** Evaluation is eventually consistent. Sampling bias, privacy, backlog, and late results must be observable.

### ADR-010 — No fake metrics

**Decision:** A displayed ResolveAI number must link to a persisted run, version tuple, population/sample count, and timestamp. Missing data displays `NOT MEASURED YET`; unknown cost is not zero.

**Consequences:** Early dashboards contain honest no-data states. Example thresholds are configuration examples only and never presented as results.

### ADR-011 — RLS defense in depth

**Decision:** Application repositories require tenant context and PostgreSQL row-level security independently enforces it on tenant-owned tables. Cross-tenant administrative work uses a separate, audited execution path rather than disabling RLS in ordinary requests.

**Consequences:** Connection pooling must set/reset transaction-local tenant context correctly. Migration/admin roles require careful privilege separation and dedicated tests.

### ADR-012 — Write-disabled shadow execution

**Decision:** Shadow candidates do not merely receive a “do not execute” prompt. They run with no production write credentials, a tool registry that exposes dry-run/read-only adapters, and network/service authorization that rejects writes.

**Consequences:** Shadow tool trajectories can be compared safely, though exact provider write behavior must be evaluated in sandbox/staging.

### ADR-013 — OIDC production identity and isolated local signing

**Decision:** Production and staging use OIDC/OAuth2 JWT access tokens verified through an
issuer JWKS. `sub`, `tenant_id`, roles, and permissions/scopes are required, but database
authorization remains authoritative. Local HS256 signing is permitted only in `local` and
`test`; the runtime rejects it in other environments. The local OIDC profile uses Keycloak,
while the verifier remains compatible with other conforming issuers.

### ADR-014 — Explicit break-glass tenant operations

**Decision:** Ordinary identities have strict tenant isolation. Cross-tenant operator work is
disabled unless a separate privileged path records a reason, ticket, MFA evidence, short expiry,
and immutable audit/alert event. Access is read-only by default; writes require a second explicit
elevation. No implicit admin bypass or bulk cross-tenant browser is permitted.

### ADR-015 — Configurable retention and legal hold

**Decision:** Retention is selected by data class and can be overridden by tenant/jurisdiction.
The versioned demo defaults are in `config/retention-policy.json`. Legal hold prevents deletion,
and deletion plans include derived embeddings/index records. Production owners must replace demo
periods with reviewed policy.

### ADR-016 — Deterministic payment sandbox first

**Decision:** Agent/policy code targets a payment-provider port. The initial provider is a local
deterministic sandbox with integer minor units, ISO-4217 currency, immutable refund identifiers,
partial-refund limits, idempotency payload conflict detection, reconciliation, and auditable
states. Real payment rails require a later adapter and webhook-security review.

### ADR-017 — Normalized model and embedding providers

**Decision:** Local deterministic providers keep tests offline; OpenAI-compatible endpoints are
the first hosted integration, with Ollama suitable for local development. Other providers remain
pluggable behind normalized validated contracts. Residency, data use, and fallback eligibility
are deployment configuration, never assumptions in prompts or adapters.

### ADR-018 — S3-compatible artifact storage

**Decision:** Large source documents, reports, evaluation results, experiments, and trace exports
use an S3-compatible port. Local development provides an optional, localhost-bound SeaweedFS
Docker profile. It replaced archived MinIO Community after that image failed the container
security gate. Production must use a reviewed, maintained S3-compatible service.
PostgreSQL stores tenant-scoped metadata, checksums, types, sizes, retention classes, and access
classification; object keys always carry a tenant prefix.

### ADR-019 — Maintained checkpoint adapter behind a port

**Decision:** ResolveAI exposes a `CheckpointRepository` boundary and will adopt a maintained
PostgreSQL LangGraph adapter only after pause/resume, concurrent run, restart, tenant isolation,
pooling, and retry tests pass. A new custom checkpointer is not the default.

### ADR-020 — Configuration-driven approval chains

**Decision:** Demo refund thresholds are 5,000 minor units autonomous, through 50,000 one
supervisor, above 50,000 two distinct approvers, and above 100,000 denied inside the AI flow.
Approval TTL is 30 minutes. Self-approval, reused second approvers, changed digests, tenant
crossing, and credential disclosure are rejected. These values are demo configuration, not
production company policy.

### ADR-021 — Explicit data classification and provider policy

**Decision:** Data is classified PUBLIC, INTERNAL, CONFIDENTIAL, SENSITIVE_PII, or RESTRICTED.
RESTRICTED data never reaches a model provider; SENSITIVE_PII is redacted/tokenized before any
external provider by default. Provider eligibility is versioned in
`config/provider-data-policy.json`, and tools return only authorized minimum fields.

### ADR-022 — Apache-2.0 repository license

**Decision:** ResolveAI is Apache-2.0 licensed. Third-party source is not copied without license
review and required notices. Architectural study is preferred, and `THIRD_PARTY_NOTICES.md`
records material runtime dependencies and external services.

## 4. Reference repository review

Reference code is used for ideas and questions, not copied wholesale. Licenses, maturity, assumptions, and current behavior must be independently verified before adapting any implementation.

The review below inspected repository `HEAD` values resolved on 2026-10-03. These pins make the architectural review auditable; they do not authorize copying. License compatibility must be recorded in a dependency/adoption decision before any source is adapted.

| Repository | Inspected revision |
|---|---|
| Mohamad-Hachem/LLM_Evaluation_System | [`0acaca7`](https://github.com/Mohamad-Hachem/LLM_Evaluation_System/commit/0acaca7af7e59674c58526dd35633a56c0f272c4) |
| VizuaraAI/capstone-production-support-agent | [`f07ce23`](https://github.com/VizuaraAI/capstone-production-support-agent/commit/f07ce238c01356bcde936d419a1d09a12c4dac56) |
| Ranjith36963/hitl-support-agent | [`d970975`](https://github.com/Ranjith36963/hitl-support-agent/commit/d97097528961e205784cd214eab081b026394554) |
| aws-samples/sample-agentic-value-accelerator | [`2b8849c`](https://github.com/aws-samples/sample-agentic-value-accelerator/commit/2b8849c997919b2f46767cb44636718d80e7b833) |
| ntg2208/production-ai-customer-support | [`f201293`](https://github.com/ntg2208/production-ai-customer-support/commit/f2012935c245ad849dc57c6821a06e87d742c496) |
| srtux/sre-agent | [`a051e69`](https://github.com/srtux/sre-agent/commit/a051e69489e9b0ac4d7737327c4facc09e2a6c67) |

### 4.1 Mohamad-Hachem/LLM_Evaluation_System

Source: [LLM_Evaluation_System](https://github.com/Mohamad-Hachem/LLM_Evaluation_System)

**Adopt**

- A simple loop from versioned cases to raw outputs, scored outputs, summaries, and a comparison UI.
- DeepEval metrics separated by purpose, with actual context and expected answer inputs.
- Preserving per-case results in addition to aggregate metrics.

**Avoid or strengthen**

- Do not treat differently named saved folders as independent RAG versions when they import the same active pipeline.
- Avoid hard-coded filenames, in-memory-only retrieval, one small single-document dataset, and manual `k` edits as the experiment registry.
- Do not treat stored LLM-judge snapshots as reproducible ground truth; record judge/version/variance and run metadata.
- Do not store one JSON object in a `.jsonl` file or rely on dashboard labels that can diverge from actual retriever settings.

### 4.2 VizuaraAI/capstone-production-support-agent

Source: [capstone-production-support-agent](https://github.com/VizuaraAI/capstone-production-support-agent)

**Adopt**

- “Measure it yourself” discipline and explicit commands/artifacts instead of shipped benchmark claims.
- Retrieval-to-citation lineage, pgvector/HNSW, injection quarantine, confidence-based handoff, OTel spans, and usage-derived cost accounting.
- A fast deterministic test path that does not require an API key, separate from paid evaluation.

**Avoid or strengthen**

- A scalar model-derived confidence score must not authorize actions; it can only influence abstention/escalation.
- One handoff threshold is insufficient for all intents, risks, tenants, and distributions; calibrate on versioned slices.
- Provider/model names and prices must be effective-dated configuration, not documentation constants.
- A portfolio-sized agent loop is not enough for durable approval, multi-tenant isolation, transactional side effects, or a broad evaluation control plane.

### 4.3 Ranjith36963/hitl-support-agent

Source: [hitl-support-agent](https://github.com/Ranjith36963/hitl-support-agent)

**Adopt**

- Durable LangGraph interrupt/resume, approval surfaces, and restart recovery as first-class behavior.
- Capability-separated read/email-write/Slack-write services as a blast-radius pattern.
- Real I/O integration tests, idempotent send behavior, audit trails, adversarial evaluation, and version-to-version comparisons.
- Layered architecture that separates orchestration, intelligence, policy, HITL, execution, and observability.

**Avoid or strengthen**

- Do not leave production workflow state in SQLite; use PostgreSQL and validate concurrent resume behavior.
- Slack/Gmail are integration options, not the core approval or ticket system of record.
- Approval must be bound to an action digest, expire, enforce reviewer authorization/separation of duty, and be revalidated before execution.
- A zero result on a curated dataset is not proof of universal safety; preserve sample scope and uncertainty.

### 4.4 AWS sample-agentic-value-accelerator

Source: [sample-agentic-value-accelerator](https://github.com/aws-samples/sample-agentic-value-accelerator)

**Adopt**

- Control-plane concepts: typed registries for agents/tools/knowledge/prompts, lifecycle state, approval routing, audit, and reusable deployment metadata.
- Clear Plan/Build/Secure/Operate/Govern separation and multiple deployment paths behind stable contracts.
- Central capability governance rather than every agent independently wiring credentials and policies.

**Avoid or strengthen**

- Do not adopt AWS-specific AgentCore, Bedrock, Terraform, and managed-service coupling in the portable core.
- Avoid the platform breadth, app factory, marketplace, and multi-framework surface until the single ResolveAI product path is reliable.
- Do not assume an enterprise reference accelerator is itself production assurance; its own repository warns adopters to perform security/model/retention/regulatory review.
- Prefer the minimum local control-plane tables/APIs required by actual use cases.

### 4.5 ntg2208/production-ai-customer-support

Source: [production-ai-customer-support](https://github.com/ntg2208/production-ai-customer-support)

**Adopt**

- Combining structured customer/order data with RAG rather than forcing all knowledge into a vector store.
- Intent-specific components, safety callbacks/guardrails, test scenarios, and a user-facing workflow.
- Domain examples that exercise policy, ticket, and operational data paths.

**Avoid or strengthen**

- Reject unverified “enterprise-grade,” ROI, cost-saving, or unlimited-scale claims. ResolveAI reports only its own measured data and labels synthetic results.
- Avoid a model-led master-agent hierarchy for deterministic routing and authorization-sensitive behavior.
- Fifteen scenarios and LLM-as-a-judge alone are not sufficient evidence; use systematic policy, adversarial, integration, regression, and load tests.
- Avoid a flat repository structure that blurs domain, API, policy, and infrastructure boundaries.

### 4.6 srtux/sre-agent

Source: [sre-agent](https://github.com/srtux/sre-agent)

**Adopt**

- Strong typed schemas (`extra="forbid"`), async external I/O, structured tool responses, comprehensive documentation, test discipline, token/cost budgets, and graph/trace visualization.
- Specialized parallel workers only when the task decomposes cleanly, followed by explicit synthesis and confidence/critic gates.
- Operational playbooks, change-aware investigation, correlation across telemetry signals, and post-deployment evaluation gates.

**Avoid or strengthen**

- Do not copy the SRE domain or its very broad tool surface.
- Do not introduce multiple agents/parallel councils where a deterministic node or single workflow is clearer, cheaper, and safer.
- Do not allow remediation-style autonomous writes; ResolveAI side effects remain policy/approval/tool bounded.
- Avoid inheriting provider-specific GCP/Vertex/Firestore assumptions or project complexity before the support workflow justifies them.

## 5. Major architecture risks and specification corrections

| ID | Risk or mistaken assumption | Impact | Mitigation / decision |
|---|---|---|---|
| R-01 | The requested scope is too large for one undifferentiated build | Partially implemented surfaces that look complete but are unsafe | Phase gates plus vertical slices; no empty showcase modules |
| R-02 | A fixed linear “every request follows every step” flow | Unnecessary latency/cost and awkward action/info handling | Conditional graph; shared safety/audit boundaries, optional domain nodes |
| R-03 | Treating MCP as a security boundary | A compromised caller could still invoke overpowered services | Service authentication, scoped credentials, server authorization, network policy, and capability separation; MCP is only an interface |
| R-04 | Model classification determines risk/permission | Prompt injection or model error enables action | Deterministic minimum risk from action/resource facts; model signals may only elevate/escalate |
| R-05 | Human approval is assumed to make an action safe | Rubber-stamping, stale data, parameter substitution, self-approval | Action digest, immutable snapshot, role checks, separation of duty, expiry, edit-as-new-proposal, pre-execution revalidation |
| R-06 | Approval wait is one long trace span | Broken exporters and meaningless duration/span storage | End wait span/event; link the resumed trace and record wait duration as data |
| R-07 | Redis Streams implies durable exactly-once jobs | Lost/duplicate evaluations or side effects | PostgreSQL outbox/inbox, at-least-once semantics, idempotent consumers, DLQ/replay |
| R-08 | Retrying tool timeouts is always safe | Duplicate refund or account operation | Stable idempotency key; reconcile unknown outcome before retry |
| R-09 | HNSW plus tenant metadata filter always performs well | Low recall/slow queries for small tenants or selective filters | Benchmark actual filter patterns; consider partitioning, partial indexes, iterative scans, or per-tenant strategies based on evidence |
| R-10 | One embedding column can store arbitrary models | Dimension mismatch and invalid comparisons | Separate storage/index by embedding dimension/model family; immutable model linkage |
| R-11 | Cosine/relevance thresholds transfer across models/domains | False confidence or excessive abstention | Calibrate per RAG version and dataset slice; store score semantics |
| R-12 | “Citation present” means “claim supported” | Polished but unsupported answers | Claim-level entailment verification and source/version checks |
| R-13 | Retrieved enterprise documents are trusted | Indirect prompt injection or stale/conflicting policy | Quarantine as data, effective-date/category checks, conflict events, allow-listed metadata |
| R-14 | PostgreSQL RLS alone solves tenant isolation | Connection-context leaks, privileged bypass, cache/tool leaks | Application repository constraints, transaction-local context, pool reset tests, tenant-bound cache keys and service auth |
| R-15 | Tenant ID as a Prometheus label is harmless | Cardinality explosion and privacy leakage | Exclude tenant IDs from metrics; query tenant analytics from event tables |
| R-16 | Raw prompts/responses in traces are needed for debugging | PII/secrets leakage and retention exposure | Default redaction/hash/reference storage; restricted opt-in content capture with retention controls |
| R-17 | Provider token counts/prices always exist | Incorrect costs silently shown as zero | Record usage source and pricing version; represent missing cost as unknown |
| R-18 | LLM-as-judge metrics are stable objective truth | Non-reproducible gates and biased comparisons | Deterministic-first tiers, pinned judges/prompts, paired evaluation, repeated samples/uncertainty where warranted |
| R-19 | Synthetic business data demonstrates production ROI | Misleading portfolio/product claims | Clearly label synthetic data and avoid extrapolating savings/resolution claims |
| R-20 | Shadow-mode prompt instructions prevent writes | Candidate could still call a real tool | Remove write credentials/tools at registry, identity, and network layers |
| R-21 | Automatic best-score deployment is desirable | Unsafe/high-cost/slow candidate ships | Human promotion after hard safety gates and Pareto review |
| R-22 | Deleting an account is a single tool call | Conflict with retention, fraud, and audit obligations | Account-closure workflow with identity verification, retention/legal states, approval, and asynchronous completion |
| R-23 | “Raw card number” may exist in CRM/payments | PCI exposure and dangerous data model | Never store or expose PAN/CVV; retain provider token, brand/last4 only if policy permits |
| R-24 | Broad “admin” role can bypass all controls | Insider risk and audit weakness | Explicit permissions, break-glass path, two-person control where required; deny-only rules remain non-overridable |
| R-25 | Creating all services/folders up front proves architecture | Empty scaffolding hides integration risk | Create modules only with the phase that supplies working contracts/tests |

## 6. Owner decision resolution

The ten owner-dependent Phase 0 questions are resolved by ADR-013 through ADR-022. No owner
decision remains open. Production deployments must still supply jurisdiction/company retention,
approved provider contracts, identity issuer details, real infrastructure credentials, and any
company-specific approval thresholds without weakening the recorded security invariants.

## 7. Phase 0 consistency decisions

The document set resolves several ambiguities in the original request:

- The target directory structure is a staged destination, not permission to create empty directories.
- “Actual cost” means usage-derived and pricing-version-linked; it can still be unknown when the provider omits usage or pricing.
- Online evaluation is best-effort asynchronous but backed by durable outbox intent.
- Human approval is one control within a deterministic policy system, not an override for explicit deny rules.
- Model fallback is allowed only when the fallback supports the same validated contract and security controls.
- Business metrics from demo data are labeled synthetic and never presented as customer outcomes.
- Canary support begins as version/allocation/rollback metadata; traffic automation waits for a later deployment platform decision.
