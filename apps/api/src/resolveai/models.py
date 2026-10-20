import uuid
from datetime import datetime
from typing import ClassVar

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    literal_column,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from resolveai.vector_types import EmbeddingVector


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TenantScoped:
    """Marker and common tenant column for ORM-level isolation."""

    __abstract__: ClassVar[bool] = True

    @declared_attr
    def tenant_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            Uuid(as_uuid=True),
            ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        )


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    __table_args__ = (CheckConstraint("status IN ('active','suspended')", name="ck_tenant_status"),)


class User(Base, TimestampMixin, TenantScoped):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_users_tenant_id_id"),
        UniqueConstraint("tenant_id", "external_subject", name="uq_users_tenant_subject"),
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        CheckConstraint("status IN ('active','disabled')", name="ck_user_status"),
    )


class Role(Base, TimestampMixin, TenantScoped):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_roles_tenant_id_id"),
        UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),
    )


class Permission(Base, TimestampMixin):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    resource: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")


class RolePermission(Base, TenantScoped):
    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    permission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "role_id"],
            ["roles.tenant_id", "roles.id"],
            ondelete="CASCADE",
            name="fk_role_permissions_role_tenant",
        ),
    )


class UserRole(Base, TenantScoped):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    role_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
            ondelete="CASCADE",
            name="fk_user_roles_user_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "role_id"],
            ["roles.tenant_id", "roles.id"],
            ondelete="CASCADE",
            name="fk_user_roles_role_tenant",
        ),
    )


class Customer(Base, TimestampMixin, TenantScoped):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    locale: Mapped[str] = mapped_column(String(20), nullable=False, default="en-IN")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_customers_tenant_id_id"),
        UniqueConstraint("tenant_id", "external_ref", name="uq_customers_tenant_external"),
        UniqueConstraint("tenant_id", "user_id", name="uq_customers_tenant_user"),
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
            ondelete="RESTRICT",
            name="fk_customers_user_tenant",
        ),
        CheckConstraint("status IN ('active','restricted','closed')", name="ck_customer_status"),
        Index("ix_customers_tenant_email", "tenant_id", "email"),
    )


class SupportAgent(Base, TimestampMixin, TenantScoped):
    __tablename__ = "support_agents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    team: Mapped[str] = mapped_column(String(100), nullable=False, default="general")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_agents_tenant_id_id"),
        UniqueConstraint("tenant_id", "user_id", name="uq_agents_tenant_user"),
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
            ondelete="CASCADE",
            name="fk_agents_user_tenant",
        ),
        CheckConstraint("status IN ('active','disabled')", name="ck_agent_status"),
    )


class Order(Base, TimestampMixin, TenantScoped):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    external_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    subtotal_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shipping_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_orders_tenant_id_id"),
        UniqueConstraint("tenant_id", "external_ref", name="uq_orders_tenant_external"),
        ForeignKeyConstraint(
            ["tenant_id", "customer_id"],
            ["customers.tenant_id", "customers.id"],
            ondelete="RESTRICT",
            name="fk_orders_customer_tenant",
        ),
        CheckConstraint(
            "subtotal_minor >= 0 AND tax_minor >= 0 AND shipping_minor >= 0 AND total_minor >= 0",
            name="ck_order_amounts_nonnegative",
        ),
        Index("ix_orders_tenant_customer_placed", "tenant_id", "customer_id", "placed_at"),
    )


class OrderItem(Base, TimestampMixin, TenantScoped):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    total_minor: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["orders.tenant_id", "orders.id"],
            ondelete="CASCADE",
            name="fk_items_order_tenant",
        ),
        CheckConstraint(
            "quantity > 0 AND unit_price_minor >= 0 AND total_minor >= 0",
            name="ck_item_amounts",
        ),
        Index("ix_items_tenant_order", "tenant_id", "order_id"),
    )


class Shipment(Base, TimestampMixin, TenantScoped):
    __tablename__ = "shipments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    carrier: Mapped[str] = mapped_column(String(80), nullable=False)
    tracking_number: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    estimated_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        UniqueConstraint("tenant_id", "carrier", "tracking_number", name="uq_shipments_tracking"),
        ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["orders.tenant_id", "orders.id"],
            ondelete="CASCADE",
            name="fk_shipments_order_tenant",
        ),
        Index("ix_shipments_tenant_order", "tenant_id", "order_id"),
    )


class Payment(Base, TimestampMixin, TenantScoped):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_payment_ref: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    method_type: Mapped[str] = mapped_column(String(40), nullable=False)
    method_fingerprint: Mapped[str | None] = mapped_column(String(160))

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_payments_tenant_id_id"),
        UniqueConstraint(
            "tenant_id", "provider", "provider_payment_ref", name="uq_payments_provider_ref"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["orders.tenant_id", "orders.id"],
            ondelete="RESTRICT",
            name="fk_payments_order_tenant",
        ),
        CheckConstraint("amount_minor >= 0", name="ck_payment_amount"),
    )


class Refund(Base, TimestampMixin, TenantScoped):
    __tablename__ = "refunds"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_refunds_idempotency"),
        ForeignKeyConstraint(
            ["tenant_id", "payment_id"],
            ["payments.tenant_id", "payments.id"],
            ondelete="RESTRICT",
            name="fk_refunds_payment_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["orders.tenant_id", "orders.id"],
            ondelete="RESTRICT",
            name="fk_refunds_order_tenant",
        ),
        CheckConstraint("amount_minor > 0", name="ck_refund_amount"),
        CheckConstraint(
            "status IN ('pending','approved','processing','succeeded','failed','cancelled')",
            name="ck_refund_status",
        ),
        CheckConstraint("length(currency) = 3", name="ck_refund_currency_iso_length"),
    )


class SupportTicket(Base, TimestampMixin, TenantScoped):
    __tablename__ = "support_tickets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    external_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_tickets_tenant_id_id"),
        UniqueConstraint("tenant_id", "external_ref", name="uq_tickets_tenant_external"),
        ForeignKeyConstraint(
            ["tenant_id", "customer_id"],
            ["customers.tenant_id", "customers.id"],
            ondelete="RESTRICT",
            name="fk_tickets_customer_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "assigned_agent_id"],
            ["support_agents.tenant_id", "support_agents.id"],
            ondelete="RESTRICT",
            name="fk_tickets_agent_tenant",
        ),
        Index("ix_tickets_tenant_status_priority", "tenant_id", "status", "priority"),
    )


class TicketMessage(Base, TimestampMixin, TenantScoped):
    __tablename__ = "ticket_messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    author_type: Mapped[str] = mapped_column(String(30), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    body_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "ticket_id"],
            ["support_tickets.tenant_id", "support_tickets.id"],
            ondelete="CASCADE",
            name="fk_messages_ticket_tenant",
        ),
        Index("ix_messages_tenant_ticket_created", "tenant_id", "ticket_id", "created_at"),
    )


class RagVersion(Base, TimestampMixin, TenantScoped):
    __tablename__ = "rag_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    chunker: Mapped[str] = mapped_column(String(40), nullable=False)
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_overlap: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding_model: Mapped[str] = mapped_column(String(160), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_relevance: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    config_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_rag_versions_tenant_id_id"),
        UniqueConstraint("tenant_id", "name", name="uq_rag_versions_tenant_name"),
        CheckConstraint("chunk_size > 0", name="ck_rag_chunk_size"),
        CheckConstraint(
            "chunk_overlap >= 0 AND chunk_overlap < chunk_size", name="ck_rag_chunk_overlap"
        ),
        CheckConstraint(
            "minimum_relevance >= -1 AND minimum_relevance <= 1",
            name="ck_rag_minimum_relevance",
        ),
    )


class KnowledgeDocument(Base, TimestampMixin, TenantScoped):
    __tablename__ = "knowledge_documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    document_type: Mapped[str] = mapped_column(String(80), nullable=False)
    policy_category: Mapped[str | None] = mapped_column(String(100))
    audience: Mapped[str] = mapped_column(String(40), nullable=False, default="internal")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_knowledge_documents_tenant_id_id"),
        UniqueConstraint("tenant_id", "source_uri", name="uq_knowledge_documents_tenant_source"),
        CheckConstraint("status IN ('active','archived')", name="ck_knowledge_document_status"),
        Index(
            "ix_knowledge_documents_tenant_category",
            "tenant_id",
            "status",
            "policy_category",
        ),
    )


class KnowledgeDocumentVersion(Base, TimestampMixin, TenantScoped):
    __tablename__ = "knowledge_document_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False, default="text/plain")
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="en")
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ingestion_status: Mapped[str] = mapped_column(String(30), nullable=False, default="indexed")
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "document_id", "id", name="uq_document_versions_tenant_doc_id"
        ),
        UniqueConstraint(
            "tenant_id",
            "document_id",
            "version_number",
            name="uq_document_versions_number",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["knowledge_documents.tenant_id", "knowledge_documents.id"],
            ondelete="CASCADE",
            name="fk_document_versions_document_tenant",
        ),
        CheckConstraint("version_number > 0", name="ck_document_version_number"),
    )


class KnowledgeChunk(Base, TimestampMixin, TenantScoped):
    __tablename__ = "knowledge_chunks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    rag_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    heading_path: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    embedding: Mapped[list[float]] = mapped_column(EmbeddingVector(384), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "document_version_id",
            "rag_version_id",
            "ordinal",
            name="uq_knowledge_chunks_version_rag_ordinal",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "document_id", "document_version_id"],
            [
                "knowledge_document_versions.tenant_id",
                "knowledge_document_versions.document_id",
                "knowledge_document_versions.id",
            ],
            ondelete="CASCADE",
            name="fk_knowledge_chunks_document_version_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "rag_version_id"],
            ["rag_versions.tenant_id", "rag_versions.id"],
            ondelete="RESTRICT",
            name="fk_knowledge_chunks_rag_version_tenant",
        ),
        CheckConstraint("ordinal >= 0 AND token_count > 0", name="ck_knowledge_chunk_counts"),
        Index(
            "ix_knowledge_chunks_tenant_document_version",
            "tenant_id",
            "document_version_id",
        ),
        Index(
            "ix_knowledge_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ).ddl_if(dialect="postgresql"),
        Index(
            "ix_knowledge_chunks_fts",
            func.to_tsvector(literal_column("'english'"), content),
            postgresql_using="gin",
        ).ddl_if(dialect="postgresql"),
    )


class RetrievalEvent(Base, TimestampMixin, TenantScoped):
    __tablename__ = "retrieval_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    rag_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    stage: Mapped[str] = mapped_column(String(40), nullable=False, default="dense")
    result_count: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    top_scores_json: Mapped[list[float]] = mapped_column(JSON, nullable=False, default=list)
    failure_category: Mapped[str | None] = mapped_column(String(80))
    details_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "rag_version_id"],
            ["rag_versions.tenant_id", "rag_versions.id"],
            ondelete="RESTRICT",
            name="fk_retrieval_events_rag_version_tenant",
        ),
        CheckConstraint("result_count >= 0 AND latency_ms >= 0", name="ck_retrieval_event_counts"),
        Index(
            "ix_retrieval_events_tenant_failure_created",
            "tenant_id",
            "failure_category",
            "created_at",
        ),
    )


class PromptVersion(Base, TimestampMixin, TenantScoped):
    __tablename__ = "prompt_versions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    template_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", "version", name="uq_prompt_version"),
        CheckConstraint("version > 0", name="ck_prompt_version_positive"),
    )


class ModelVersion(Base, TimestampMixin, TenantScoped):
    __tablename__ = "model_versions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    config_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_model_version_name"),)


class AgentRun(Base, TimestampMixin, TenantScoped):
    __tablename__ = "agent_runs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    intent: Mapped[str | None] = mapped_column(String(80))
    risk_level: Mapped[str | None] = mapped_column(String(30))
    current_node: Mapped[str] = mapped_column(String(80), nullable=False)
    step_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (
        CheckConstraint("step_count >= 0", name="ck_agent_run_steps"),
        Index("ix_agent_runs_tenant_status", "tenant_id", "status", "updated_at"),
    )


class AgentStep(Base, TimestampMixin, TenantScoped):
    __tablename__ = "agent_steps"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    node: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    input_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    output_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    error_category: Mapped[str | None] = mapped_column(String(80))
    __table_args__ = (
        UniqueConstraint("tenant_id", "run_id", "sequence", name="uq_agent_step_sequence"),
        CheckConstraint("sequence >= 0", name="ck_agent_step_sequence"),
    )


class ToolCall(Base, TimestampMixin, TenantScoped):
    __tablename__ = "tool_calls"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    arguments_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    result_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    provider_reference: Mapped[str | None] = mapped_column(String(200))
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_tool_call_idempotency"),
        Index("ix_tool_calls_tenant_run", "tenant_id", "run_id"),
    )


class PolicyDecisionRecord(Base, TimestampMixin, TenantScoped):
    __tablename__ = "policy_decisions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(120), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(30), nullable=False)
    required_approver_role: Mapped[str | None] = mapped_column(String(80))
    approvals_required: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    action_digest: Mapped[str] = mapped_column(String(64), nullable=False)


class ApprovalRequest(Base, TimestampMixin, TenantScoped):
    __tablename__ = "approval_requests"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    requester_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    action_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    action_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    evidence_json: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    required_role: Mapped[str] = mapped_column(String(80), nullable=False)
    approvals_required: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    approvals_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        CheckConstraint("approvals_required >= 1", name="ck_approval_required_positive"),
        CheckConstraint(
            "approvals_completed >= 0 AND approvals_completed <= approvals_required",
            name="ck_approval_completed_range",
        ),
        Index("ix_approval_tenant_status", "tenant_id", "status", "created_at"),
    )


class ApprovalDecision(Base, TimestampMixin, TenantScoped):
    __tablename__ = "approval_decisions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    approval_request_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    modified_action_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    action_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (
        Index(
            "ix_approval_decision_request_created",
            "tenant_id",
            "approval_request_id",
            "created_at",
        ),
    )


class Artifact(Base, TimestampMixin, TenantScoped):
    __tablename__ = "artifacts"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_type: Mapped[str] = mapped_column(String(80), nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(160), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    retention_policy: Mapped[str] = mapped_column(String(80), nullable=False)
    access_classification: Mapped[str] = mapped_column(String(40), nullable=False)
    legal_hold: Mapped[bool] = mapped_column(nullable=False, default=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "object_key", name="uq_artifact_tenant_object_key"),
        CheckConstraint("size_bytes >= 0", name="ck_artifact_size_nonnegative"),
        Index("ix_artifact_tenant_type_created", "tenant_id", "artifact_type", "created_at"),
    )


class AuditEvent(Base, TimestampMixin, TenantScoped):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    details_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    __table_args__ = (Index("ix_audit_tenant_created", "tenant_id", "created_at"),)


class GuardrailEvent(Base, TimestampMixin, TenantScoped):
    __tablename__ = "guardrail_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    guardrail: Mapped[str] = mapped_column(String(100), nullable=False)
    stage: Mapped[str] = mapped_column(String(30), nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(160))


class CostEvent(Base, TimestampMixin, TenantScoped):
    __tablename__ = "cost_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    feature: Mapped[str] = mapped_column(String(80), nullable=False)
    agent: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(80))
    rag_version: Mapped[str | None] = mapped_column(String(80))
    endpoint: Mapped[str | None] = mapped_column(String(160))
    operation_type: Mapped[str] = mapped_column(String(40), nullable=False, default="llm")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit: Mapped[str] = mapped_column(String(40), nullable=False, default="tokens")
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd_micros: Mapped[int | None] = mapped_column(Integer)
    pricing_version: Mapped[str | None] = mapped_column(String(80))
    __table_args__ = (
        CheckConstraint(
            "input_tokens >= 0 AND output_tokens >= 0 AND cached_tokens >= 0",
            name="ck_cost_tokens",
        ),
    )


class EvaluationDataset(Base, TimestampMixin, TenantScoped):
    __tablename__ = "evaluation_datasets"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", "version", name="uq_evaluation_dataset_version"),
    )


class EvaluationCase(Base, TimestampMixin, TenantScoped):
    __tablename__ = "evaluation_cases"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    case_key: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(30), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(30), nullable=False)
    input_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    expected_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "dataset_id", "case_key", name="uq_evaluation_case_key"),
    )


class EvaluationRun(Base, TimestampMixin, TenantScoped):
    __tablename__ = "evaluation_runs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    git_commit: Mapped[str] = mapped_column(String(64), nullable=False)
    rag_version: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    model_version: Mapped[str] = mapped_column(String(160), nullable=False)
    configuration_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class EvaluationResult(Base, TimestampMixin, TenantScoped):
    __tablename__ = "evaluation_results"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    evaluator: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    details_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "run_id", "case_id", "evaluator", name="uq_evaluation_result"
        ),
    )


class EvaluationJob(Base, TimestampMixin, TenantScoped):
    __tablename__ = "evaluation_jobs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    request_key: Mapped[str] = mapped_column(String(160), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    error_category: Mapped[str | None] = mapped_column(String(80))
    result_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    __table_args__ = (
        UniqueConstraint("tenant_id", "request_key", name="uq_evaluation_job_request"),
        CheckConstraint(
            "attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts",
            name="ck_evaluation_job_attempts",
        ),
        Index("ix_evaluation_job_status_available", "tenant_id", "status", "available_at"),
    )


class ExecutionRecord(Base, TimestampMixin, TenantScoped):
    __tablename__ = "execution_records"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    tool_call_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    verification_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_execution_idempotency"),
    )


class OutboxEvent(Base, TimestampMixin, TenantScoped):
    __tablename__ = "outbox_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic: Mapped[str] = mapped_column(String(120), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        CheckConstraint("attempts >= 0", name="ck_outbox_attempts"),
        Index("ix_outbox_tenant_status_available", "tenant_id", "status", "available_at"),
    )


class DeploymentRecord(Base, TimestampMixin, TenantScoped):
    __tablename__ = "deployment_records"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    environment: Mapped[str] = mapped_column(String(80), nullable=False)
    git_commit: Mapped[str] = mapped_column(String(64), nullable=False)
    stable_version_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    candidate_version_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    candidate_allocation_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rollback_version_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    __table_args__ = (
        CheckConstraint(
            "candidate_allocation_percent >= 0 AND candidate_allocation_percent <= 100",
            name="ck_deployment_allocation",
        ),
    )


class CustomerSignal(Base, TimestampMixin, TenantScoped):
    __tablename__ = "customer_signals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    customer_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    order_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    store_id: Mapped[str | None] = mapped_column(String(120))
    sku_id: Mapped[str | None] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    model_version: Mapped[str | None] = mapped_column(String(80))
    rule_version: Mapped[str | None] = mapped_column(String(80))

    __table_args__ = (
        CheckConstraint(
            "category IN ('REFUND_DELAY','DELIVERY_DELAY','PAYMENT_FAILURE',"
            "'INVENTORY_SHORTAGE','PRODUCT_QUALITY','SUPPORT_ESCALATION')",
            name="ck_customer_signal_category",
        ),
        CheckConstraint(
            "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')",
            name="ck_customer_signal_severity",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_customer_signal_confidence",
        ),
        Index(
            "ix_customer_signal_tenant_category_occurred",
            "tenant_id",
            "category",
            "occurred_at",
        ),
    )


class OperationalMetricPoint(Base, TimestampMixin, TenantScoped):
    __tablename__ = "operational_metric_points"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dimensions_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    source: Mapped[str] = mapped_column(String(80), nullable=False)

    __table_args__ = (
        Index(
            "ix_metric_point_tenant_metric_entity_observed",
            "tenant_id",
            "metric_name",
            "entity_type",
            "entity_id",
            "observed_at",
        ),
    )


class CommerceAnomaly(Base, TimestampMixin, TenantScoped):
    __tablename__ = "commerce_anomalies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_value: Mapped[float] = mapped_column(Float, nullable=False)
    observed_value: Mapped[float] = mapped_column(Float, nullable=False)
    deviation_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    detector_name: Mapped[str] = mapped_column(String(80), nullable=False)
    detector_version: Mapped[str] = mapped_column(String(40), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    explanation_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        CheckConstraint("status IN ('OPEN','ACKNOWLEDGED','RESOLVED')", name="ck_anomaly_status"),
        CheckConstraint("sample_count >= 0", name="ck_anomaly_sample_count"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_anomaly_confidence"),
        CheckConstraint("window_end > window_start", name="ck_anomaly_window"),
        Index(
            "ix_anomaly_tenant_status_category_window",
            "tenant_id",
            "status",
            "category",
            "window_end",
        ),
    )


class RootCauseHypothesis(Base, TimestampMixin, TenantScoped):
    __tablename__ = "root_cause_hypotheses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    anomaly_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("commerce_anomalies.id", ondelete="CASCADE"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    cause_code: Mapped[str] = mapped_column(String(80), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    supporting_evidence_json: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    contradicting_evidence_json: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    affected_entities_json: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    time_alignment_json: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "anomaly_id", "rank", name="uq_hypothesis_anomaly_rank"),
        CheckConstraint(
            "status IN ('SUPPORTED','INSUFFICIENT_EVIDENCE','REJECTED')",
            name="ck_hypothesis_status",
        ),
        CheckConstraint("rank > 0", name="ck_hypothesis_rank"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_hypothesis_confidence"),
    )


class RecommendedAction(Base, TimestampMixin, TenantScoped):
    __tablename__ = "recommended_actions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    anomaly_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("commerce_anomalies.id", ondelete="SET NULL")
    )
    hypothesis_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("root_cause_hypotheses.id", ondelete="SET NULL")
    )
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    parameters_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    expected_impact_json: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PROPOSED")
    policy_decision: Mapped[str] = mapped_column(String(30), nullable=False)
    approval_request_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    action_digest: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('PROPOSED','APPROVAL_REQUIRED','APPROVED','REJECTED','EXECUTED')",
            name="ck_recommended_action_status",
        ),
        CheckConstraint(
            "policy_decision IN ('ALLOW','REQUIRE_APPROVAL','DENY','NOT_EVALUATED')",
            name="ck_recommended_action_policy",
        ),
        Index("ix_recommended_action_tenant_status", "tenant_id", "status", "created_at"),
    )


class ActionOutcome(Base, TimestampMixin, TenantScoped):
    __tablename__ = "action_outcomes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommended_action_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("recommended_actions.id", ondelete="CASCADE"), nullable=False
    )
    target_metric: Mapped[str] = mapped_column(String(100), nullable=False)
    before_window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    before_window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    before_value: Mapped[float] = mapped_column(Float, nullable=False)
    after_window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    after_window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    after_value: Mapped[float | None] = mapped_column(Float)
    effect_estimate: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    limitations_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "recommended_action_id",
            "target_metric",
            name="uq_action_outcome_metric",
        ),
        CheckConstraint(
            "status IN ('NOT_MEASURED','MEASURED','INCONCLUSIVE')",
            name="ck_action_outcome_status",
        ),
        CheckConstraint("before_window_end > before_window_start", name="ck_outcome_before_window"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_action_outcome_confidence",
        ),
        Index("ix_action_outcome_tenant_status", "tenant_id", "status", "created_at"),
    )


class CommerceStore(Base, TimestampMixin, TenantScoped):
    __tablename__ = "commerce_stores"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    capacity_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")

    __table_args__ = (
        UniqueConstraint("tenant_id", "external_ref", name="uq_commerce_store_external_ref"),
        CheckConstraint("capacity_units >= 0", name="ck_commerce_store_capacity"),
        CheckConstraint("status IN ('ACTIVE','PAUSED','CLOSED')", name="ck_commerce_store_status"),
    )


class CommerceSku(Base, TimestampMixin, TenantScoped):
    __tablename__ = "commerce_skus"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")

    __table_args__ = (
        UniqueConstraint("tenant_id", "external_ref", name="uq_commerce_sku_external_ref"),
        CheckConstraint("status IN ('ACTIVE','DISABLED','RETIRED')", name="ck_commerce_sku_status"),
    )


class InventorySnapshot(Base, TimestampMixin, TenantScoped):
    __tablename__ = "inventory_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    sku_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    on_hand_units: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_units: Mapped[int] = mapped_column(Integer, nullable=False)
    reorder_point_units: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "on_hand_units >= 0 AND reserved_units >= 0 AND reorder_point_units >= 0",
            name="ck_inventory_snapshot_units",
        ),
        Index(
            "ix_inventory_tenant_store_sku_observed",
            "tenant_id",
            "store_ref",
            "sku_ref",
            "observed_at",
        ),
    )


class FulfillmentEvent(Base, TimestampMixin, TenantScoped):
    __tablename__ = "fulfillment_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    store_ref: Mapped[str | None] = mapped_column(String(120))
    sku_ref: Mapped[str | None] = mapped_column(String(120))
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('PLACED','PICKING','PACKED','ASSIGNED','DISPATCHED','DELIVERED',"
            "'DELAYED','FAILED','RETURNED')",
            name="ck_fulfillment_event_type",
        ),
        Index(
            "ix_fulfillment_tenant_type_occurred",
            "tenant_id",
            "event_type",
            "occurred_at",
        ),
    )


class ProductBatch(Base, TimestampMixin, TenantScoped):
    __tablename__ = "product_batches"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    sku_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    produced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    units_produced: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")

    __table_args__ = (
        UniqueConstraint("tenant_id", "batch_ref", name="uq_product_batch_ref"),
        CheckConstraint("units_produced >= 0", name="ck_product_batch_units"),
        CheckConstraint(
            "status IN ('ACTIVE','QUARANTINED','RECALLED','EXPIRED')",
            name="ck_product_batch_status",
        ),
    )


class QualityReport(Base, TimestampMixin, TenantScoped):
    __tablename__ = "quality_reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_ref: Mapped[str | None] = mapped_column(String(120))
    sku_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    defect_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    affected_units: Mapped[int] = mapped_column(Integer, nullable=False)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        CheckConstraint(
            "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')", name="ck_quality_severity"
        ),
        CheckConstraint("affected_units >= 0", name="ck_quality_affected_units"),
        Index("ix_quality_tenant_sku_reported", "tenant_id", "sku_ref", "reported_at"),
    )


class DetectorEvaluationRun(Base, TimestampMixin, TenantScoped):
    __tablename__ = "detector_evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    detector_name: Mapped[str] = mapped_column(String(80), nullable=False)
    detector_version: Mapped[str] = mapped_column(String(40), nullable=False)
    dataset_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    cases_json: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        CheckConstraint("sample_count > 0", name="ck_detector_evaluation_samples"),
        Index(
            "ix_detector_eval_tenant_detector_created",
            "tenant_id",
            "detector_name",
            "created_at",
        ),
    )


class DetectorSchedule(Base, TimestampMixin, TenantScoped):
    __tablename__ = "detector_schedules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    detector_name: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False)
    configuration_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_detector_schedule_name"),
        CheckConstraint("interval_minutes >= 15", name="ck_detector_schedule_interval"),
        Index(
            "ix_detector_schedule_tenant_due",
            "tenant_id",
            "enabled",
            "next_run_at",
        ),
    )
