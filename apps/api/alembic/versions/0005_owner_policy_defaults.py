"""Apply owner policy defaults and artifact metadata.

Revision ID: 0005_owner_defaults
Revises: 0004_cost_eval_jobs
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_owner_defaults"
down_revision: str | None = "0004_cost_eval_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "policy_decisions",
        sa.Column("approvals_required", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "approval_requests",
        sa.Column("approvals_required", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "approval_requests",
        sa.Column("approvals_completed", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_approval_required_positive", "approval_requests", "approvals_required >= 1"
    )
    op.create_check_constraint(
        "ck_approval_completed_range",
        "approval_requests",
        "approvals_completed >= 0 AND approvals_completed <= approvals_required",
    )
    op.create_check_constraint(
        "ck_refund_status",
        "refunds",
        "status IN ('pending','approved','processing','succeeded','failed','cancelled')",
    )
    op.create_check_constraint("ck_refund_currency_iso_length", "refunds", "length(currency) = 3")
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("artifact_type", sa.String(80), nullable=False),
        sa.Column("object_key", sa.String(500), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("content_type", sa.String(160), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("retention_policy", sa.String(80), nullable=False),
        sa.Column("access_classification", sa.String(40), nullable=False),
        sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "object_key", name="uq_artifact_tenant_object_key"),
        sa.CheckConstraint("size_bytes >= 0", name="ck_artifact_size_nonnegative"),
    )
    op.create_index(
        "ix_artifact_tenant_type_created",
        "artifacts",
        ["tenant_id", "artifact_type", "created_at"],
    )
    op.create_index("ix_artifacts_tenant_id", "artifacts", ["tenant_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute('ALTER TABLE "artifacts" ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "artifacts" FORCE ROW LEVEL SECURITY')
        op.execute(
            'CREATE POLICY "artifacts_tenant_isolation" ON "artifacts" '
            "USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) "
            "WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)"
        )


def downgrade() -> None:
    op.drop_table("artifacts")
    op.drop_constraint("ck_refund_currency_iso_length", "refunds", type_="check")
    op.drop_constraint("ck_refund_status", "refunds", type_="check")
    op.drop_constraint("ck_approval_completed_range", "approval_requests", type_="check")
    op.drop_constraint("ck_approval_required_positive", "approval_requests", type_="check")
    op.drop_column("approval_requests", "approvals_completed")
    op.drop_column("approval_requests", "approvals_required")
    op.drop_column("policy_decisions", "approvals_required")
