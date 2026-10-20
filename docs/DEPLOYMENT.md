# Deployment guide

1. Provision PostgreSQL 16 with pgvector, Redis 7, TLS, managed secrets, and separate owner/application database credentials.
2. Set all `RESOLVEAI_*` variables; replace every local password/secret and connect the production IdP.
3. Build immutable API/web images, scan them, and record image digests.
4. Run Alembic as the owner role, then seed only approved configuration—not demo identities or synthetic commerce records.
5. Start the API with the restricted application role; verify liveness, readiness, RLS, metrics privacy, and a denied cross-tenant test.
6. Start workers/web/telemetry, run deterministic smoke and security suites, then execute a staged approval workflow using sandbox providers.
7. Record deployment versions, rollback target, database backup identifier, and reviewer sign-off.

Docker Compose is the local reference, not a production topology. Kubernetes/Helm and cloud-specific IAM/network/storage definitions require a target environment decision.
