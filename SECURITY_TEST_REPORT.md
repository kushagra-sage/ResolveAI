# ResolveAI internal security test report

**Date:** 2026-10-06  
**Scope:** Local repository, local synthetic database, API/UI, and development containers  
**Classification:** Internal development validation; not an independent penetration test or certification

## Scope and method

The review traced UI/API input through JWT validation, database-backed RBAC, tenant filters/RLS,
policy and approval boundaries, adapter calls, audit events, and storage. Adversarial attention was
given to IDOR/cross-tenant reads, ungoverned side effects, idempotency replay, prompt injection,
PII/secret leakage, SSRF-style provider URLs, dependency risk, and missing browser/API controls.
Testing was non-intrusive and limited to the local synthetic environment.

## Automated evidence

| Check | Result |
|---|---|
| Ruff | Passed; no findings |
| Strict mypy | Passed; 57 source files |
| Bandit SAST | Passed after remediation; 0 High, 0 Medium, 0 Low |
| Python dependency audit | `pip-audit`: no known vulnerabilities |
| Frontend dependency audit | `npm audit`: 0 vulnerabilities |
| High-signal secret scan | 0 AWS key, provider-key, or private-key pattern files |
| OIDC verification | Live Keycloak password grant issued an agent token; backend verified JWKS signature, issuer, audience, tenant, and subject |
| Python regression | 65/65 passed in 522.63 seconds |
| Browser/a11y | Chromium complete; WebKit complete across final runs; Firefox host loader blocked (see browser report) |

Machine-readable Bandit and pip-audit output is stored in `artifacts/bandit.json` and
`artifacts/pip-audit.json`.

## Controls verified by tests and review

- Authentication is required at a shared dependency boundary; production/staging reject local
  HS256 mode and use OIDC/JWKS.
- Roles and permissions are loaded from PostgreSQL rather than trusted from token claims.
- Tenant and ownership checks prevent cross-customer and cross-tenant reads; PostgreSQL RLS is
  defense in depth.
- Refunds and CommerceOps writes are typed, policy evaluated, digest-bound, approval gated when
  required, idempotent, reconciled, and audited.
- Mock adapter diagnostics require tenant admin and are disabled outside local/test; normal reads
  still require commerce permissions.
- Provider URLs allow only absolute HTTP(S) configuration, calls use bounded timeout/retry, and
  adapter audit records exclude payloads and credentials.
- Prompt/document injection quarantine, sensitive-input redaction, write-disabled shadow mode,
  and telemetry attribute allowlists have regression coverage.
- API responses set `nosniff`, frame denial, no-referrer, restricted browser permissions, trace
  correlation, and no-store on authenticated `/v1` responses.

## Findings remediated during this review

1. **Medium — provider URL scheme was not restricted.** The REST adapter now rejects non-HTTP(S)
   and non-absolute base URLs before `urlopen`; the Bandit exception is narrowly documented after
   that validation.
2. **Low — response parsing used assertions.** Assertions were replaced by explicit validation so
   optimized Python cannot remove the checks.
3. **Low — API defense headers were incomplete.** Deterministic security and cache-control headers
   were added and regression tested.
4. **Reliability/security — write diagnostics could be mistaken for production tools.** They are
   now local/test-only, admin-only, namespaced as sandbox operations, idempotent, and audited.

## Residual risk

- No independent penetration test, DAST proxy campaign, production cloud review, or compliance
  assessment was performed.
- Local demo credentials exist in Compose/Keycloak fixtures by design and must never be reused.
- Production still needs TLS/HSTS at the edge, CSP for the built frontend, WAF/rate limiting,
  managed secrets and rotation, network policy, backup/restore ownership, and alert routing.
- Heuristic PII and prompt-injection detection is defense in depth, not complete DLP.
- Real payment/ERP/shipment adapters need provider-specific webhook signature, replay, permission,
  reconciliation, and sandbox tests before activation.
- Firefox browser execution remains blocked by the host Playwright runtime issue documented in
  `docs/BROWSER_TEST_REPORT.md`.

No claim of independent security testing, regulatory compliance, or production safety is made.
