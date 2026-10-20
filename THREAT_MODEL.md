# Threat model

Protected assets include customer/order/payment data, tenant boundaries, model/tool credentials, approval authority, side effects, audit integrity, and evaluation artifacts.

Primary threats are forged identity, cross-tenant object access, prompt/document injection, unauthorized or repeated tools, approval replay/edit, payment-secret disclosure, telemetry leakage, provider compromise, stale policy, queue replay, and denial of service.

Controls include signed-token validation, database-backed RBAC, PostgreSQL RLS, composite tenant constraints, strict Pydantic tool schemas, deterministic policy, action digests, separation of duty, expiring approvals, idempotency, output checks, bounded graph steps/fallbacks, content hashing, and audit persistence.

Residual risks include incomplete heuristic PII/injection detection, unavailable external providers, local development secrets, and infrastructure controls outside this repository. Production requires managed secrets, TLS, network policy, WAF/rate limiting, backups, retention controls, vulnerability scanning, and an independent security review.
