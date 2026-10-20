# ResolveAI

ResolveAI is a multi-tenant AI customer-resolution and CommerceOps platform. It implements a governed path from authenticated customer context through RAG, deterministic policy, human approval, idempotent action execution, verification, trace/audit evidence, cost recording, and evaluation. The local product uses FastAPI, React 19/Vite, PostgreSQL/pgvector, LangGraph, Keycloak, Redis, SeaweedFS, OpenTelemetry, Prometheus, Grafana, and Docker Compose.

No production AI quality, latency, cost, safety, or business metric is claimed. The included smoke evaluation uses deterministic synthetic fixtures and labels its sample count.

## Local Python quick start

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
copy .env.example .env
.venv/Scripts/python -m alembic -c apps/api/alembic.ini upgrade head
.venv/Scripts/python -m resolveai.seed
.venv/Scripts/python -m uvicorn resolveai.main:app --reload
```

On macOS/Linux, use `.venv/bin/python` and `cp .env.example .env`.

## Run the complete local product

```bash
cp .env.example .env
docker compose --profile identity --profile storage up -d --build
```

Open `http://localhost:3000` and sign in with one of the local identities `customer`, `agent`, `supervisor`, or `admin`; the development password is `resolveai-local`. These credentials are intentionally local-only.

Optional owner-approved local infrastructure profiles:

```bash
docker compose --profile identity up -d keycloak
docker compose --profile storage up -d seaweedfs
```

Keycloak is available at `http://localhost:8080` and imports the `resolveai` demo realm.
The realm also contains a least-privilege `resolveai-service` client-credentials client; its
checked-in secret is for local development only.
The development-only SeaweedFS profile exposes its S3 endpoint at `http://localhost:9000`.
The Compose and realm credentials are local-demo values only.

Production and staging must set `RESOLVEAI_AUTH_MODE=oidc`, a reviewed issuer/audience, and a
JWKS URL. The API refuses the local HS256 mode outside `local`/`test`. Token roles/scopes are
required profile data but authorization continues to load from PostgreSQL.

Endpoints:

- `GET /health/live`
- `GET /health/ready`
- `GET /v1/me`
- `GET /v1/customers/{customer_id}`
- `GET /v1/customers/{customer_id}/orders`
- `POST /v1/knowledge/documents`
- `POST /v1/knowledge/search`
- `POST /v1/resolutions`
- `GET /v1/approvals`
- `POST /v1/approvals/{approval_id}/decision`
- `GET /v1/operations/cost-summary`
- `GET /v1/integrations/status`
- `GET /v1/integrations/erp/inventory/{store_ref}/{sku_ref}`
- `GET /v1/integrations/wms/fulfillments/{order_ref}`
- `GET /v1/integrations/shipments/{shipment_ref}`
- `POST /v1/integrations/sandbox/*` (local/test tenant-admin diagnostics only)
- `GET /metrics`

Authenticated endpoints require a signed JWT whose `sub` and `tenant_id` match an active database user. Roles and permissions are loaded from PostgreSQL and are not trusted from token claims.

For local seeded identities, create a one-hour token:

```bash
.venv/Scripts/python -m resolveai.dev_token customer
.venv/Scripts/python -m resolveai.dev_token agent
.venv/Scripts/python -m resolveai.dev_token supervisor
.venv/Scripts/python -m resolveai.dev_token admin
```

The command refuses to run outside `local` or `test` environments. Approval demo defaults are
configuration-driven: refunds through 5,000 minor units are autonomous, through 50,000 require
one supervisor, above 50,000 require two distinct approvers, and above 100,000 are denied inside
the AI flow. The default approval TTL is 30 minutes; these are not production company policy.

External-service and model defaults are deterministic and require no paid credentials. See
[`docs/ADAPTERS.md`](docs/ADAPTERS.md) for mock/REST/Ollama/OpenAI-compatible configuration and
[`docs/PRODUCTION_READINESS.md`](docs/PRODUCTION_READINESS.md) for the exact local, simulated,
unexercised, excluded, and externally blocked scope.

Run the deterministic evaluation smoke suite with:

```bash
.venv/Scripts/python scripts/run_eval.py datasets/eval/smoke-v1.json
.venv/Scripts/python scripts/check_gates.py artifacts/evaluations/<run-id>.json
.venv/Scripts/python scripts/run_experiment.py datasets/eval/smoke-v1.json
```

Verify live PostgreSQL isolation and the HNSW plan after Compose is healthy:

```bash
.venv/Scripts/python scripts/verify_postgres.py --synthetic-rows 5000
```

The verification corpus is inserted inside a rollback-only transaction. `make ingest`
loads `docs/PROJECT_SPEC.md`; pass another path directly to `scripts/ingest_docs.py`.

The web workspace is under `apps/web` (`npm install && npm run build`). Architecture and operational documents are under [`docs/`](docs/PROJECT_SPEC.md).

## Verified local evidence

- Backend: **71 tests passed**.
- Chromium workflows/accessibility/demo capture: **13 tests passed**.
- Synthetic research benchmark: **168 paired cases**, fixed seed 20261006.
- Paired mean quality delta: **+0.5089**, bootstrap 95% CI **[0.4628, 0.5528]**.
- Answer accuracy: **0.1786 baseline vs 0.9643 ResolveAI**.
- Hallucination rate: **0.7857 baseline vs 0.0357 ResolveAI**.
- Known weakness: benign guardrail false-positive rate **0.1538**.

Regenerate the research artifacts with:

```powershell
.\.venv\Scripts\python.exe scripts\run_research_benchmark.py
```

See the [faculty demo script](docs/DEMO_SCRIPT.md), [implemented architecture](docs/CURRENT_ARCHITECTURE.md), [paper draft](research/report/ResolveAI_Paper_Draft.md), and [resume bullets](docs/RESUME_BULLETS.md). The benchmark is synthetic; these metrics are not claims of production customer or financial impact.

Retention, provider-data eligibility, and approval defaults are versioned under `config/`.
Large artifacts use the S3-compatible port and tenant-prefixed object keys; PostgreSQL stores
artifact metadata only. ResolveAI source is licensed under [Apache-2.0](LICENSE), with dependency
and external-service notes in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
