"""Create the Phase 1 identity, RBAC, commerce, and support schema.

Revision ID: 0001_phase1_core
Revises: None
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_phase1_core"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "users",
    "roles",
    "role_permissions",
    "user_roles",
    "customers",
    "support_agents",
    "orders",
    "order_items",
    "shipments",
    "payments",
    "refunds",
    "support_tickets",
    "ticket_messages",
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
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
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
    op.create_table(
        "tenants",
        _id(),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        *_timestamps(),
        sa.CheckConstraint("status IN ('active','suspended')", name="ck_tenant_status"),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )
    op.create_table(
        "permissions",
        _id(),
        sa.Column("code", sa.String(120), nullable=False),
        sa.Column("resource", sa.String(80), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        *_timestamps(),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
    )
    op.create_table(
        "users",
        _id(),
        sa.Column("external_subject", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        *_timestamps(),
        _tenant_id(),
        sa.CheckConstraint("status IN ('active','disabled')", name="ck_user_status"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_users_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "external_subject", name="uq_users_tenant_subject"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )
    op.create_table(
        "roles",
        _id(),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        *_timestamps(),
        _tenant_id(),
        sa.UniqueConstraint("tenant_id", "id", name="uq_roles_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "permission_id",
            sa.Uuid(),
            sa.ForeignKey("permissions.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        _tenant_id(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "role_id"],
            ["roles.tenant_id", "roles.id"],
            ondelete="CASCADE",
            name="fk_role_permissions_role_tenant",
        ),
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("role_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        _tenant_id(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
            ondelete="CASCADE",
            name="fk_user_roles_user_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "role_id"],
            ["roles.tenant_id", "roles.id"],
            ondelete="CASCADE",
            name="fk_user_roles_role_tenant",
        ),
    )
    op.create_table(
        "customers",
        _id(),
        sa.Column("external_ref", sa.String(120), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("locale", sa.String(20), nullable=False, server_default="en-IN"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        *_timestamps(),
        _tenant_id(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
            ondelete="RESTRICT",
            name="fk_customers_user_tenant",
        ),
        sa.CheckConstraint("status IN ('active','restricted','closed')", name="ck_customer_status"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_customers_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "external_ref", name="uq_customers_tenant_external"),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_customers_tenant_user"),
    )
    op.create_table(
        "support_agents",
        _id(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("team", sa.String(100), nullable=False, server_default="general"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        *_timestamps(),
        _tenant_id(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
            ondelete="CASCADE",
            name="fk_agents_user_tenant",
        ),
        sa.CheckConstraint("status IN ('active','disabled')", name="ck_agent_status"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_agents_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_agents_tenant_user"),
    )
    op.create_table(
        "orders",
        _id(),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("external_ref", sa.String(120), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("subtotal_minor", sa.Integer(), nullable=False),
        sa.Column("tax_minor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shipping_minor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_minor", sa.Integer(), nullable=False),
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        *_timestamps(),
        _tenant_id(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "customer_id"],
            ["customers.tenant_id", "customers.id"],
            ondelete="RESTRICT",
            name="fk_orders_customer_tenant",
        ),
        sa.CheckConstraint(
            "subtotal_minor >= 0 AND tax_minor >= 0 AND shipping_minor >= 0 AND total_minor >= 0",
            name="ck_order_amounts_nonnegative",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_orders_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "external_ref", name="uq_orders_tenant_external"),
    )
    op.create_table(
        "order_items",
        _id(),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("sku", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_minor", sa.Integer(), nullable=False),
        sa.Column("total_minor", sa.Integer(), nullable=False),
        *_timestamps(),
        _tenant_id(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["orders.tenant_id", "orders.id"],
            ondelete="CASCADE",
            name="fk_items_order_tenant",
        ),
        sa.CheckConstraint(
            "quantity > 0 AND unit_price_minor >= 0 AND total_minor >= 0",
            name="ck_item_amounts",
        ),
    )
    op.create_table(
        "shipments",
        _id(),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("carrier", sa.String(80), nullable=False),
        sa.Column("tracking_number", sa.String(160), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("estimated_delivery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        *_timestamps(),
        _tenant_id(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["orders.tenant_id", "orders.id"],
            ondelete="CASCADE",
            name="fk_shipments_order_tenant",
        ),
        sa.UniqueConstraint(
            "tenant_id", "carrier", "tracking_number", name="uq_shipments_tracking"
        ),
    )
    op.create_table(
        "payments",
        _id(),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("provider_payment_ref", sa.String(160), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("method_type", sa.String(40), nullable=False),
        sa.Column("method_fingerprint", sa.String(160), nullable=True),
        *_timestamps(),
        _tenant_id(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["orders.tenant_id", "orders.id"],
            ondelete="RESTRICT",
            name="fk_payments_order_tenant",
        ),
        sa.CheckConstraint("amount_minor >= 0", name="ck_payment_amount"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_payments_tenant_id_id"),
        sa.UniqueConstraint(
            "tenant_id", "provider", "provider_payment_ref", name="uq_payments_provider_ref"
        ),
    )
    op.create_table(
        "refunds",
        _id(),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("reason_code", sa.String(80), nullable=False),
        *_timestamps(),
        _tenant_id(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "payment_id"],
            ["payments.tenant_id", "payments.id"],
            ondelete="RESTRICT",
            name="fk_refunds_payment_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["orders.tenant_id", "orders.id"],
            ondelete="RESTRICT",
            name="fk_refunds_order_tenant",
        ),
        sa.CheckConstraint("amount_minor > 0", name="ck_refund_amount"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_refunds_idempotency"),
    )
    op.create_table(
        "support_tickets",
        _id(),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("external_ref", sa.String(120), nullable=False),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("assigned_agent_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        _tenant_id(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "customer_id"],
            ["customers.tenant_id", "customers.id"],
            ondelete="RESTRICT",
            name="fk_tickets_customer_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assigned_agent_id"],
            ["support_agents.tenant_id", "support_agents.id"],
            ondelete="RESTRICT",
            name="fk_tickets_agent_tenant",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_tickets_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "external_ref", name="uq_tickets_tenant_external"),
    )
    op.create_table(
        "ticket_messages",
        _id(),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("author_type", sa.String(30), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("body_sha256", sa.String(64), nullable=False),
        *_timestamps(),
        _tenant_id(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "ticket_id"],
            ["support_tickets.tenant_id", "support_tickets.id"],
            ondelete="CASCADE",
            name="fk_messages_ticket_tenant",
        ),
    )

    indexes = (
        ("ix_customers_tenant_email", "customers", ["tenant_id", "email"]),
        (
            "ix_orders_tenant_customer_placed",
            "orders",
            ["tenant_id", "customer_id", "placed_at"],
        ),
        ("ix_items_tenant_order", "order_items", ["tenant_id", "order_id"]),
        ("ix_shipments_tenant_order", "shipments", ["tenant_id", "order_id"]),
        (
            "ix_tickets_tenant_status_priority",
            "support_tickets",
            ["tenant_id", "status", "priority"],
        ),
        (
            "ix_messages_tenant_ticket_created",
            "ticket_messages",
            ["tenant_id", "ticket_id", "created_at"],
        ),
    )
    for name, table, columns in indexes:
        op.create_index(name, table, columns, unique=False)
    for table in TENANT_TABLES:
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"], unique=False)
    _enable_rls()


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.drop_table(table)
    op.drop_table("permissions")
    op.drop_table("tenants")
