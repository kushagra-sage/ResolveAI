"""CommerceOps signal, anomaly, investigation, action, and outcome foundation.

Revision ID: c7f2a91e0b1d
Revises: 0005_owner_defaults
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7f2a91e0b1d"
down_revision: str | None = "0005_owner_defaults"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps_and_tenant() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "customer_signals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid()),
        sa.Column("customer_id", sa.Uuid()),
        sa.Column("order_id", sa.Uuid()),
        sa.Column("store_id", sa.String(120)),
        sa.Column("sku_id", sa.String(120)),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("model_version", sa.String(80)),
        sa.Column("rule_version", sa.String(80)),
        *_timestamps_and_tenant(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "category IN ('REFUND_DELAY','DELIVERY_DELAY','PAYMENT_FAILURE','INVENTORY_SHORTAGE',"
            "'PRODUCT_QUALITY','SUPPORT_ESCALATION')",
            name="ck_customer_signal_category",
        ),
        sa.CheckConstraint(
            "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')", name="ck_customer_signal_severity"
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_customer_signal_confidence"
        ),
    )
    op.create_index("ix_customer_signals_tenant_id", "customer_signals", ["tenant_id"])
    op.create_index(
        "ix_customer_signal_tenant_category_occurred",
        "customer_signals",
        ["tenant_id", "category", "occurred_at"],
    )

    op.create_table(
        "operational_metric_points",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(120), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dimensions_json", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        *_timestamps_and_tenant(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_operational_metric_points_tenant_id", "operational_metric_points", ["tenant_id"]
    )
    op.create_index(
        "ix_metric_point_tenant_metric_entity_observed",
        "operational_metric_points",
        ["tenant_id", "metric_name", "entity_type", "entity_id", "observed_at"],
    )

    op.create_table(
        "commerce_anomalies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(120), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("baseline_value", sa.Float(), nullable=False),
        sa.Column("observed_value", sa.Float(), nullable=False),
        sa.Column("deviation_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("detector_name", sa.String(80), nullable=False),
        sa.Column("detector_version", sa.String(40), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("explanation_json", sa.JSON(), nullable=False),
        *_timestamps_and_tenant(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "status IN ('OPEN','ACKNOWLEDGED','RESOLVED')", name="ck_anomaly_status"
        ),
        sa.CheckConstraint("sample_count >= 0", name="ck_anomaly_sample_count"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_anomaly_confidence"),
        sa.CheckConstraint("window_end > window_start", name="ck_anomaly_window"),
    )
    op.create_index("ix_commerce_anomalies_tenant_id", "commerce_anomalies", ["tenant_id"])
    op.create_index(
        "ix_anomaly_tenant_status_category_window",
        "commerce_anomalies",
        ["tenant_id", "status", "category", "window_end"],
    )

    op.create_table(
        "root_cause_hypotheses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("anomaly_id", sa.Uuid(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("cause_code", sa.String(80), nullable=False),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("supporting_evidence_json", sa.JSON(), nullable=False),
        sa.Column("contradicting_evidence_json", sa.JSON(), nullable=False),
        sa.Column("affected_entities_json", sa.JSON(), nullable=False),
        sa.Column("time_alignment_json", sa.JSON(), nullable=False),
        *_timestamps_and_tenant(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["anomaly_id"], ["commerce_anomalies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("tenant_id", "anomaly_id", "rank", name="uq_hypothesis_anomaly_rank"),
        sa.CheckConstraint(
            "status IN ('SUPPORTED','INSUFFICIENT_EVIDENCE','REJECTED')",
            name="ck_hypothesis_status",
        ),
        sa.CheckConstraint("rank > 0", name="ck_hypothesis_rank"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_hypothesis_confidence"),
    )
    op.create_index("ix_root_cause_hypotheses_tenant_id", "root_cause_hypotheses", ["tenant_id"])

    op.create_table(
        "recommended_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("anomaly_id", sa.Uuid()),
        sa.Column("hypothesis_id", sa.Uuid()),
        sa.Column("action_type", sa.String(80), nullable=False),
        sa.Column("parameters_json", sa.JSON(), nullable=False),
        sa.Column("expected_impact_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("policy_decision", sa.String(30), nullable=False),
        sa.Column("approval_request_id", sa.Uuid()),
        sa.Column("action_digest", sa.String(64), nullable=False),
        *_timestamps_and_tenant(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["anomaly_id"], ["commerce_anomalies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["hypothesis_id"], ["root_cause_hypotheses.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "status IN ('PROPOSED','APPROVAL_REQUIRED','APPROVED','REJECTED','EXECUTED')",
            name="ck_recommended_action_status",
        ),
        sa.CheckConstraint(
            "policy_decision IN ('ALLOW','REQUIRE_APPROVAL','DENY','NOT_EVALUATED')",
            name="ck_recommended_action_policy",
        ),
    )
    op.create_index("ix_recommended_actions_tenant_id", "recommended_actions", ["tenant_id"])
    op.create_index(
        "ix_recommended_action_tenant_status",
        "recommended_actions",
        ["tenant_id", "status", "created_at"],
    )

    op.create_table(
        "action_outcomes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recommended_action_id", sa.Uuid(), nullable=False),
        sa.Column("target_metric", sa.String(100), nullable=False),
        sa.Column("before_window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("before_window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("before_value", sa.Float(), nullable=False),
        sa.Column("after_window_start", sa.DateTime(timezone=True)),
        sa.Column("after_window_end", sa.DateTime(timezone=True)),
        sa.Column("after_value", sa.Float()),
        sa.Column("effect_estimate", sa.Float()),
        sa.Column("confidence", sa.Float()),
        sa.Column("limitations_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        *_timestamps_and_tenant(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["recommended_action_id"], ["recommended_actions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "tenant_id", "recommended_action_id", "target_metric", name="uq_action_outcome_metric"
        ),
        sa.CheckConstraint(
            "status IN ('NOT_MEASURED','MEASURED','INCONCLUSIVE')", name="ck_action_outcome_status"
        ),
        sa.CheckConstraint(
            "before_window_end > before_window_start", name="ck_outcome_before_window"
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_action_outcome_confidence",
        ),
    )
    op.create_index("ix_action_outcomes_tenant_id", "action_outcomes", ["tenant_id"])
    op.create_index(
        "ix_action_outcome_tenant_status",
        "action_outcomes",
        ["tenant_id", "status", "created_at"],
    )

    if op.get_bind().dialect.name == "postgresql":
        for table in (
            "customer_signals",
            "operational_metric_points",
            "commerce_anomalies",
            "root_cause_hypotheses",
            "recommended_actions",
            "action_outcomes",
        ):
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
            op.execute(
                sa.text(
                    f'CREATE POLICY "{table}_tenant_isolation" ON "{table}" '
                    "USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) "
                    "WITH CHECK (tenant_id = "
                    "nullif(current_setting('app.tenant_id', true), '')::uuid)"
                )
            )


def downgrade() -> None:
    for table in (
        "action_outcomes",
        "recommended_actions",
        "root_cause_hypotheses",
        "commerce_anomalies",
        "operational_metric_points",
        "customer_signals",
    ):
        op.drop_table(table)
