"""Allow reviewed edits followed by a fresh approval decision.

Revision ID: 0003_approval_edit_cycles
Revises: ea2abd269f06
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_approval_edit_cycles"
down_revision: str | None = "ea2abd269f06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_approval_decision_request", "approval_decisions", type_="unique")
    op.create_index(
        "ix_approval_decision_request_created",
        "approval_decisions",
        ["tenant_id", "approval_request_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_approval_decision_request_created", table_name="approval_decisions")
    op.create_unique_constraint(
        "uq_approval_decision_request",
        "approval_decisions",
        ["tenant_id", "approval_request_id"],
    )
