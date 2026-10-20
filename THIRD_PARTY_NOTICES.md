# Third-Party Notices

ResolveAI is independently implemented and distributed under Apache-2.0. Dependencies and
container images retain their own licenses; Apache-2.0 does not relicense them.

Material runtime components include FastAPI, SQLAlchemy, Alembic, LangGraph, PostgreSQL/pgvector,
Redis, OpenTelemetry, Prometheus, Grafana, Next.js/React, Keycloak, and an S3-compatible local
object-store image. Consult the installed package/container metadata for the exact version and
license included in a build.

The optional local object-store profile uses SeaweedFS 4.48, licensed separately under
Apache-2.0. Its source and license are available from https://github.com/seaweedfs/seaweedfs.
The image is a local development convenience and is not the production object-store selection.

Reference repositories listed in `docs/DECISIONS.md` were reviewed for architectural ideas only.
No source was copied from those repositories. Before any future source adaptation, record its
license, compatibility conclusion, copyright notice, and modified-file obligations here.
