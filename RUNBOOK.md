# Operations runbook

## Triage

1. Capture the `X-Trace-Id`, UTC time, endpoint, status, and deployment version—never the raw customer prompt.
2. Check `/health/live`, then `/health/ready`, PostgreSQL, Redis, and provider status.
3. Inspect the durable run/step, retrieval, policy, tool, approval, audit, and cost records for that tenant through authorized tooling.
4. If correctness or authorization is uncertain, disable writes and escalate; do not bypass policy.

## Failure modes

- Model/provider: bounded retry/fallback; malformed fallback is rejected; escalate safely when exhausted.
- Retrieval: return abstention, inspect failure category and pinned RAG version; do not force an answer.
- PostgreSQL: API readiness fails; stop writes, restore service, verify migrations and tenant context.
- Redis: durable PostgreSQL state remains authoritative; pause asynchronous dispatch and replay idempotently.
- Tool unknown outcome: query provider by idempotency/reference before retrying.
- Telemetry exporter: customer path continues; record the visibility gap and repair exporter.
- Approval backlog: verify expiry and reviewer capacity; never auto-approve.
- OIDC/JWKS: fail closed when issuer, audience, signature, tenant, roles, or scopes are invalid; never switch production to local signing as an outage workaround.
- Object storage: keep database metadata and checksums authoritative for discovery; do not expose an object key without tenant-prefix authorization.

## Break-glass operations

Ordinary support/admin identities never bypass tenant isolation. Any future platform-operator path
must require a separate role, reason, ticket reference, MFA evidence, short expiry, read-only
default, and immutable audit plus alert. Write access requires a second explicit elevation.
The repository currently exposes only the validated request contract; no cross-tenant endpoint is
enabled by default.

## Retention and legal hold

`config/retention-policy.json` contains development/demo defaults. Production owners must review
them for jurisdiction and company policy. Retention workers must skip legal-hold records and delete
derived embedding/index objects together with their source class. Raw model content should not be
stored when redacted metadata is sufficient.

## Local identity and artifact profiles

Use `docker compose --profile identity up -d keycloak` for the imported Keycloak demo realm and
`docker compose --profile storage up -d seaweedfs` for development-only S3-compatible local
artifact storage. SeaweedFS is bound to localhost and production should use a reviewed managed
S3-compatible service. The local Keycloak and object-store credentials are demo values. Their
checked-in credentials are development-only. Production uses secret-managed credentials,
encryption at rest, reviewed issuer/client settings, and tenant-scoped bucket policy.

## Backup/restore rehearsal

Use `pg_dump --format=custom` with the owner role, restore into an isolated database, run `alembic check`, compare table counts/checksums, and exercise a tenant-scoped read. Record command versions, start/end timestamps, artifact checksum, and result. Redis is not authoritative for approvals or executions; rebuild ephemeral data from PostgreSQL/outbox state.

No backup/restore or outage drill is claimed until its dated artifact exists.
