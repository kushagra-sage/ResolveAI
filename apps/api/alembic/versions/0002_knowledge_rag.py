"""Add versioned knowledge, vectors, and retrieval event storage.

Revision ID: 0002_knowledge_rag
Revises: 0001_phase1_core
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0002_knowledge_rag"
down_revision: str | None = "0001_phase1_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "rag_versions",
    "knowledge_documents",
    "knowledge_document_versions",
    "knowledge_chunks",
    "retrieval_events",
)


def _id() -> sa.Column[object]:
    return sa.Column("id", sa.Uuid(), primary_key=True, nullable=False)


def _tenant_id() -> sa.Column[object]:
    return sa.Column(
        "tenant_id",
        sa.Uuid(),
        sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )


def _timestamps() -> tuple[sa.Column[object], sa.Column[object]]:
    return (
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def _enable_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TENANT_TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(
                f'CREATE POLICY "{table}_tenant_isolation" ON "{table}" '
                "USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) "
                "WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)"
            )
        )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
    vector_type = Vector(384).with_variant(sa.JSON(), "sqlite")

    op.create_table(
        "rag_versions",
        _id(),
        _tenant_id(),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("chunker", sa.String(40), nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("chunk_overlap", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding_model", sa.String(160), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column("minimum_relevance", sa.Float(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("config_json", sa.JSON(), nullable=False, server_default="{}"),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "id", name="uq_rag_versions_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_rag_versions_tenant_name"),
        sa.CheckConstraint("chunk_size > 0", name="ck_rag_chunk_size"),
        sa.CheckConstraint(
            "chunk_overlap >= 0 AND chunk_overlap < chunk_size", name="ck_rag_chunk_overlap"
        ),
        sa.CheckConstraint(
            "minimum_relevance >= -1 AND minimum_relevance <= 1",
            name="ck_rag_minimum_relevance",
        ),
    )
    op.create_table(
        "knowledge_documents",
        _id(),
        _tenant_id(),
        sa.Column("source_uri", sa.String(1000), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("document_type", sa.String(80), nullable=False),
        sa.Column("policy_category", sa.String(100)),
        sa.Column("audience", sa.String(40), nullable=False, server_default="internal"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("current_version_id", sa.Uuid()),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "id", name="uq_knowledge_documents_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "source_uri", name="uq_knowledge_documents_tenant_source"),
        sa.CheckConstraint("status IN ('active','archived')", name="ck_knowledge_document_status"),
    )
    op.create_index(
        "ix_knowledge_documents_tenant_category",
        "knowledge_documents",
        ["tenant_id", "status", "policy_category"],
    )
    op.create_index("ix_knowledge_documents_tenant_id", "knowledge_documents", ["tenant_id"])
    op.create_table(
        "knowledge_document_versions",
        _id(),
        _tenant_id(),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(120), nullable=False, server_default="text/plain"),
        sa.Column("language", sa.String(20), nullable=False, server_default="en"),
        sa.Column("effective_from", sa.DateTime(timezone=True)),
        sa.Column("effective_to", sa.DateTime(timezone=True)),
        sa.Column("ingestion_status", sa.String(30), nullable=False, server_default="indexed"),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        *_timestamps(),
        sa.UniqueConstraint(
            "tenant_id", "document_id", "id", name="uq_document_versions_tenant_doc_id"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "document_id",
            "version_number",
            name="uq_document_versions_number",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["knowledge_documents.tenant_id", "knowledge_documents.id"],
            ondelete="CASCADE",
            name="fk_document_versions_document_tenant",
        ),
        sa.CheckConstraint("version_number > 0", name="ck_document_version_number"),
    )
    op.create_table(
        "knowledge_chunks",
        _id(),
        _tenant_id(),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_version_id", sa.Uuid(), nullable=False),
        sa.Column("rag_version_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("heading_path", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("embedding", vector_type, nullable=False),
        *_timestamps(),
        sa.UniqueConstraint(
            "tenant_id",
            "document_version_id",
            "rag_version_id",
            "ordinal",
            name="uq_knowledge_chunks_version_rag_ordinal",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "document_id", "document_version_id"],
            [
                "knowledge_document_versions.tenant_id",
                "knowledge_document_versions.document_id",
                "knowledge_document_versions.id",
            ],
            ondelete="CASCADE",
            name="fk_knowledge_chunks_document_version_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "rag_version_id"],
            ["rag_versions.tenant_id", "rag_versions.id"],
            ondelete="RESTRICT",
            name="fk_knowledge_chunks_rag_version_tenant",
        ),
        sa.CheckConstraint("ordinal >= 0 AND token_count > 0", name="ck_knowledge_chunk_counts"),
    )
    op.create_index(
        "ix_knowledge_document_versions_tenant_id",
        "knowledge_document_versions",
        ["tenant_id"],
    )
    op.create_index(
        "ix_knowledge_chunks_tenant_document_version",
        "knowledge_chunks",
        ["tenant_id", "document_version_id"],
    )
    op.create_index("ix_knowledge_chunks_tenant_id", "knowledge_chunks", ["tenant_id"])
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                "CREATE INDEX ix_knowledge_chunks_embedding_hnsw ON knowledge_chunks "
                "USING hnsw (embedding vector_cosine_ops)"
            )
        )
    op.create_table(
        "retrieval_events",
        _id(),
        _tenant_id(),
        sa.Column("query_sha256", sa.String(64), nullable=False),
        sa.Column("rag_version_id", sa.Uuid(), nullable=False),
        sa.Column("stage", sa.String(40), nullable=False, server_default="dense"),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("top_scores_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("failure_category", sa.String(80)),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default="{}"),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "rag_version_id"],
            ["rag_versions.tenant_id", "rag_versions.id"],
            ondelete="RESTRICT",
            name="fk_retrieval_events_rag_version_tenant",
        ),
        sa.CheckConstraint(
            "result_count >= 0 AND latency_ms >= 0", name="ck_retrieval_event_counts"
        ),
    )
    op.create_index(
        "ix_retrieval_events_tenant_failure_created",
        "retrieval_events",
        ["tenant_id", "failure_category", "created_at"],
    )
    op.create_index("ix_retrieval_events_tenant_id", "retrieval_events", ["tenant_id"])
    op.create_index("ix_rag_versions_tenant_id", "rag_versions", ["tenant_id"])
    _enable_rls()


def downgrade() -> None:
    op.drop_table("retrieval_events")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_document_versions")
    op.drop_table("knowledge_documents")
    op.drop_table("rag_versions")
