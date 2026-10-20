"""Add complete cost dimensions and durable online evaluation jobs.

Revision ID: 0004_cost_eval_jobs
Revises: 0003_approval_edit_cycles
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_cost_eval_jobs"
down_revision: str | None = "0003_approval_edit_cycles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name, type_ in (
        ("agent", sa.String(100)),
        ("prompt_version", sa.String(80)),
        ("rag_version", sa.String(80)),
        ("endpoint", sa.String(160)),
    ):
        op.add_column("cost_events", sa.Column(name, type_, nullable=True))
    op.add_column(
        "cost_events",
        sa.Column("operation_type", sa.String(40), nullable=False, server_default="llm"),
    )
    op.add_column(
        "cost_events", sa.Column("quantity", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "cost_events",
        sa.Column("unit", sa.String(40), nullable=False, server_default="tokens"),
    )
    op.create_table(
        "evaluation_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("request_key", sa.String(160), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_category", sa.String(80), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "request_key", name="uq_evaluation_job_request"),
        sa.CheckConstraint(
            "attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts",
            name="ck_evaluation_job_attempts",
        ),
    )
    op.create_index(
        "ix_evaluation_job_status_available",
        "evaluation_jobs",
        ["tenant_id", "status", "available_at"],
    )
    op.create_index("ix_evaluation_jobs_tenant_id", "evaluation_jobs", ["tenant_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute('ALTER TABLE "evaluation_jobs" ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "evaluation_jobs" FORCE ROW LEVEL SECURITY')
        op.execute(
            'CREATE POLICY "evaluation_jobs_tenant_isolation" ON "evaluation_jobs" '
            "USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) "
            "WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)"
        )


def downgrade() -> None:
    op.drop_table("evaluation_jobs")
    for name in (
        "unit",
        "quantity",
        "operation_type",
        "endpoint",
        "rag_version",
        "prompt_version",
        "agent",
    ):
        op.drop_column("cost_events", name)
