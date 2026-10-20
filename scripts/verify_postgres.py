import argparse
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.errors import ForeignKeyViolation
from resolveai.config import get_settings
from resolveai.seed import seed_id


def _psycopg_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def _contains_node(plan: dict[str, Any], fragment: str) -> bool:
    if fragment.lower() in str(plan.get("Node Type", "")).lower():
        return True
    return any(_contains_node(child, fragment) for child in plan.get("Plans", []))


def verify(synthetic_rows: int) -> dict[str, object]:
    if synthetic_rows < 1000:
        raise ValueError("synthetic_rows must be at least 1000")
    settings = get_settings()
    app_url = _psycopg_url(settings.database_url)
    owner_url = _psycopg_url(settings.alembic_database_url)
    acme_id = seed_id("tenant:acme")
    other_id = seed_id("tenant:other")

    with psycopg.connect(app_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM users")
            users_without_context = int(cursor.fetchone()[0])
        connection.rollback()
        with connection.transaction(), connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.tenant_id', %s, true)", (str(acme_id),))
            cursor.execute("SELECT count(*) FROM users")
            acme_users = int(cursor.fetchone()[0])
        with connection.transaction(), connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.tenant_id', %s, true)", (str(other_id),))
            cursor.execute("SELECT count(*) FROM users")
            other_users = int(cursor.fetchone()[0])

        composite_fk_rejected = False
        try:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.tenant_id', %s, true)", (str(other_id),))
                cursor.execute(
                    """
                    INSERT INTO orders (
                        id, tenant_id, customer_id, external_ref, status, currency,
                        subtotal_minor, tax_minor, shipping_minor, total_minor,
                        placed_at, version
                    ) VALUES (%s, %s, %s, %s, 'created', 'INR', 1, 0, 0, 1, now(), 1)
                    """,
                    (
                        str(uuid.uuid4()),
                        str(other_id),
                        str(seed_id("customer:acme:demo")),
                        f"CROSS-TENANT-{uuid.uuid4()}",
                    ),
                )
        except ForeignKeyViolation:
            composite_fk_rejected = True

    vector = "[" + ",".join(["1"] + ["0"] * 383) + "]"
    document_id = uuid.uuid4()
    version_id = uuid.uuid4()
    rag_id = seed_id("rag:acme-demo:v001")
    with (
        psycopg.connect(owner_url) as connection,
        connection.transaction(force_rollback=True),
        connection.cursor() as cursor,
    ):
        cursor.execute("SELECT version()")
        database_version = str(cursor.fetchone()[0])
        cursor.execute(
            """
            INSERT INTO knowledge_documents (
                id, tenant_id, source_uri, title, document_type, audience, status
            ) VALUES (
                %s, %s, %s, 'Synthetic plan corpus', 'benchmark', 'internal', 'active'
            )
            """,
            (str(document_id), str(acme_id), f"benchmark://{document_id}"),
        )
        cursor.execute(
            """
            INSERT INTO knowledge_document_versions (
                id, tenant_id, document_id, version_number, checksum_sha256, content,
                mime_type, language, ingestion_status, metadata_json
            ) VALUES (%s, %s, %s, 1, %s, 'synthetic benchmark', 'text/plain',
                      'en', 'indexed', '{}')
            """,
            (str(version_id), str(acme_id), str(document_id), "b" * 64),
        )
        cursor.execute(
            "UPDATE knowledge_documents SET current_version_id=%s WHERE id=%s",
            (str(version_id), str(document_id)),
        )
        cursor.execute(
            """
            INSERT INTO knowledge_chunks (
                id, tenant_id, document_id, document_version_id, rag_version_id,
                ordinal, heading_path, content, content_sha256, token_count,
                metadata_json, embedding
            )
            SELECT gen_random_uuid(), %s, %s, %s, %s, value - 1, '[]',
                   'synthetic benchmark chunk ' || value, repeat('c', 64), 4, '{}',
                   %s::vector
            FROM generate_series(1, %s) AS value
            """,
            (
                str(acme_id),
                str(document_id),
                str(version_id),
                str(rag_id),
                vector,
                synthetic_rows,
            ),
        )
        cursor.execute("ANALYZE knowledge_chunks")
        cursor.execute("SET LOCAL enable_seqscan=off")
        cursor.execute(
            """
            EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
            SELECT id FROM knowledge_chunks
            WHERE tenant_id = %s
            ORDER BY embedding <=> %s::vector
            LIMIT 10
            """,
            (str(acme_id), vector),
        )
        explain = cursor.fetchone()[0][0]
    plan = explain["Plan"]
    return {
        "verified_at": datetime.now(tz=UTC).isoformat(),
        "database_version": database_version,
        "rls": {
            "users_without_context": users_without_context,
            "acme_users": acme_users,
            "other_users": other_users,
            "isolated": users_without_context == 0 and acme_users > 0 and other_users > 0,
        },
        "composite_fk_rejected": composite_fk_rejected,
        "hnsw": {
            "synthetic_rows": synthetic_rows,
            "index_scan_observed": _contains_node(plan, "Index Scan"),
            "plan": explain,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify PostgreSQL RLS, FK, and HNSW contracts")
    parser.add_argument("--synthetic-rows", type=int, default=5000)
    parser.add_argument("--output", type=Path, default=Path("artifacts/postgres-verification.json"))
    args = parser.parse_args()
    result = verify(args.synthetic_rows)
    if not result["rls"]["isolated"] or not result["composite_fk_rejected"]:
        raise SystemExit("PostgreSQL isolation verification failed")
    if not result["hnsw"]["index_scan_observed"]:
        raise SystemExit("HNSW index scan was not observed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
