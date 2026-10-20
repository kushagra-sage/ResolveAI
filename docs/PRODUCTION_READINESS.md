# Production readiness

This document separates locally verified capability from simulated behavior and external work.
“Implemented” means present and exercised in this repository; it does not mean independently
certified or ready for an unspecified organization’s production policy.

## Implemented locally

- FastAPI/PostgreSQL/pgvector API, Redis coordination, tenant-scoped ORM/RLS controls, migrations,
  outbox, idempotent tools, approvals, audit, RAG, evaluation, cost, and CommerceOps detectors.
- React/Vite operations workspace for resolution, approvals, traces, evaluation, CommerceOps
  signals/anomalies/root causes/actions/outcomes, and truthful measured/no-data states.
- Keycloak OIDC/OAuth2 local realm with customer, support agent, supervisor, admin, and service
  principal identities. A live token was verified through Keycloak JWKS, issuer, and audience.
- Stable ERP, WMS, payment, shipment, and model ports; deterministic mocks; configurable REST and
  OpenAI-compatible provider adapters; normalized errors; bounded retry/timeout; idempotency; and
  redacted audit.
- PostgreSQL/pgvector, Redis, SeaweedFS S3 compatibility, Keycloak, OpenTelemetry Collector,
  Prometheus, and Grafana in Compose. SeaweedFS is the approved maintained local replacement for
  archived MinIO Community.
- Deterministic 168-case labelled synthetic benchmark spanning the requested 14 support, safety,
  tool, and CommerceOps families.
- Internal SAST/dependency/secret validation and Playwright/axe test projects with retained HTML,
  trace, screenshot, and video evidence.

## Simulated through mocks or sandboxes

- ERP inventory and transfer acknowledgements, WMS fulfillment, payment refunds, and shipment
  status/rescheduling use deterministic local adapters unless REST provider mode is selected.
- The default model is deterministic and keyless. It validates orchestration and contracts, not
  language quality. Synthetic benchmark labels support experiments, not real-world impact claims.
- Demo users, orders, payments, signals, anomalies, actions, and outcomes are fictional.
- Local Compose passwords and client secrets are development fixtures only.

## Available but not exercised

- Ollama or another local OpenAI-compatible endpoint through `RESOLVEAI_MODEL_BASE_URL`.
- Hosted OpenAI-compatible model mode when a reviewed endpoint, model, key, residency policy, and
  data-processing terms are provided.
- Generic REST ERP/WMS/payment/shipment adapters against real sandboxes; no provider account or
  schema was supplied for this run.
- Production OIDC configuration against another conforming identity provider.
- Langfuse can be added as specialized LLM telemetry; vendor-neutral OpenTelemetry remains the
  authoritative baseline and Langfuse was not added merely to increase stack size.

## Not included

- Real provider credentials, production customer data, provider-specific SDK coupling, or paid
  model calls.
- A new custom LangGraph PostgreSQL checkpointer; adoption remains gated by the tests in ADR-019.
- An MCP transport facade for the external adapters. REST is implemented; MCP can wrap the same
  ports but is not itself a security boundary.
- Independent penetration testing, accessibility certification, SOC 2/ISO/PCI certification,
  legal review, or proof of production ROI.
- Production cloud/IaC, autoscaling, multi-region failover, CDN/WAF, company DNS/TLS, pager routing,
  and managed backup/restore services.

## Blocked on external input

1. Organization identity-provider tenant, issuer/client registration, MFA/session policy, and
   production redirect domains.
2. Production hosting/cloud account, domain, TLS certificate ownership, network zones, secret
   manager, database/object-store service, backup objectives, and regional requirements.
3. ERP, WMS, payment, and carrier vendors; approved sandbox accounts; exact schemas; scopes;
   webhook signing/replay rules; rate limits; and reconciliation semantics.
4. Approved production model endpoint/model, credentials, residency/data-use terms, budgets,
   fallback eligibility, and quality/safety acceptance thresholds.
5. Company approval thresholds, retention/legal-hold policy, jurisdictions, data classification,
   deletion SLAs, and incident-notification obligations.
6. Independent security testing vendor/scope and remediation acceptance authority.
7. Accessibility reviewer, assistive-technology/device/browser matrix, and certification scope.
8. Production alert channels, on-call ownership, SLOs/error budgets, escalation paths, and change
   management approvals.

No hard-coded paid key is required. Missing provider configuration is surfaced as unavailable; it
is not silently replaced with fake success.
