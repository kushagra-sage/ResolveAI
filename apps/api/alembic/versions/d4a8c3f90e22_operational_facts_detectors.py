"""Operational facts, detector evaluation, and schedules.

Revision ID: d4a8c3f90e22
Revises: c7f2a91e0b1d
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4a8c3f90e22"
down_revision: str | None = "c7f2a91e0b1d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _common() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
    ]


def _tenant_constraints() -> tuple[sa.ForeignKeyConstraint]:
    return (sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),)


def upgrade() -> None:
    op.create_table(
        "commerce_stores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_ref", sa.String(120), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("region", sa.String(100), nullable=False),
        sa.Column("capacity_units", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        *_common(),
        sa.PrimaryKeyConstraint("id"),
        *_tenant_constraints(),
        sa.UniqueConstraint("tenant_id", "external_ref", name="uq_commerce_store_external_ref"),
        sa.CheckConstraint("capacity_units >= 0", name="ck_commerce_store_capacity"),
        sa.CheckConstraint(
            "status IN ('ACTIVE','PAUSED','CLOSED')", name="ck_commerce_store_status"
        ),
    )
    op.create_index("ix_commerce_stores_tenant_id", "commerce_stores", ["tenant_id"])

    op.create_table(
        "commerce_skus",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_ref", sa.String(120), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        *_common(),
        sa.PrimaryKeyConstraint("id"),
        *_tenant_constraints(),
        sa.UniqueConstraint("tenant_id", "external_ref", name="uq_commerce_sku_external_ref"),
        sa.CheckConstraint(
            "status IN ('ACTIVE','DISABLED','RETIRED')", name="ck_commerce_sku_status"
        ),
    )
    op.create_index("ix_commerce_skus_tenant_id", "commerce_skus", ["tenant_id"])

    op.create_table(
        "inventory_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("store_ref", sa.String(120), nullable=False),
        sa.Column("sku_ref", sa.String(120), nullable=False),
        sa.Column("on_hand_units", sa.Integer(), nullable=False),
        sa.Column("reserved_units", sa.Integer(), nullable=False),
        sa.Column("reorder_point_units", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        *_common(),
        sa.PrimaryKeyConstraint("id"),
        *_tenant_constraints(),
        sa.CheckConstraint(
            "on_hand_units >= 0 AND reserved_units >= 0 AND reorder_point_units >= 0",
            name="ck_inventory_snapshot_units",
        ),
    )
    op.create_index("ix_inventory_snapshots_tenant_id", "inventory_snapshots", ["tenant_id"])
    op.create_index(
        "ix_inventory_tenant_store_sku_observed",
        "inventory_snapshots",
        ["tenant_id", "store_ref", "sku_ref", "observed_at"],
    )

    op.create_table(
        "fulfillment_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_ref", sa.String(120), nullable=False),
        sa.Column("store_ref", sa.String(120)),
        sa.Column("sku_ref", sa.String(120)),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_common(),
        sa.PrimaryKeyConstraint("id"),
        *_tenant_constraints(),
        sa.CheckConstraint(
            "event_type IN ('PLACED','PICKING','PACKED','ASSIGNED','DISPATCHED','DELIVERED',"
            "'DELAYED','FAILED','RETURNED')",
            name="ck_fulfillment_event_type",
        ),
    )
    op.create_index("ix_fulfillment_events_tenant_id", "fulfillment_events", ["tenant_id"])
    op.create_index(
        "ix_fulfillment_tenant_type_occurred",
        "fulfillment_events",
        ["tenant_id", "event_type", "occurred_at"],
    )

    op.create_table(
        "product_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_ref", sa.String(120), nullable=False),
        sa.Column("sku_ref", sa.String(120), nullable=False),
        sa.Column("produced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("units_produced", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        *_common(),
        sa.PrimaryKeyConstraint("id"),
        *_tenant_constraints(),
        sa.UniqueConstraint("tenant_id", "batch_ref", name="uq_product_batch_ref"),
        sa.CheckConstraint("units_produced >= 0", name="ck_product_batch_units"),
        sa.CheckConstraint(
            "status IN ('ACTIVE','QUARANTINED','RECALLED','EXPIRED')",
            name="ck_product_batch_status",
        ),
    )
    op.create_index("ix_product_batches_tenant_id", "product_batches", ["tenant_id"])

    op.create_table(
        "quality_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_ref", sa.String(120)),
        sa.Column("sku_ref", sa.String(120), nullable=False),
        sa.Column("defect_type", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("affected_units", sa.Integer(), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        *_common(),
        sa.PrimaryKeyConstraint("id"),
        *_tenant_constraints(),
        sa.CheckConstraint(
            "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')", name="ck_quality_severity"
        ),
        sa.CheckConstraint("affected_units >= 0", name="ck_quality_affected_units"),
    )
    op.create_index("ix_quality_reports_tenant_id", "quality_reports", ["tenant_id"])
    op.create_index(
        "ix_quality_tenant_sku_reported",
        "quality_reports",
        ["tenant_id", "sku_ref", "reported_at"],
    )

    op.create_table(
        "detector_evaluation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("detector_name", sa.String(80), nullable=False),
        sa.Column("detector_version", sa.String(40), nullable=False),
        sa.Column("dataset_sha256", sa.String(64), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("cases_json", sa.JSON(), nullable=False),
        *_common(),
        sa.PrimaryKeyConstraint("id"),
        *_tenant_constraints(),
        sa.CheckConstraint("sample_count > 0", name="ck_detector_evaluation_samples"),
    )
    op.create_index(
        "ix_detector_evaluation_runs_tenant_id", "detector_evaluation_runs", ["tenant_id"]
    )
    op.create_index(
        "ix_detector_eval_tenant_detector_created",
        "detector_evaluation_runs",
        ["tenant_id", "detector_name", "created_at"],
    )

    op.create_table(
        "detector_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("detector_name", sa.String(80), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(120), nullable=False),
        sa.Column("configuration_json", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("interval_minutes", sa.Integer(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        *_common(),
        sa.PrimaryKeyConstraint("id"),
        *_tenant_constraints(),
        sa.UniqueConstraint("tenant_id", "name", name="uq_detector_schedule_name"),
        sa.CheckConstraint("interval_minutes >= 15", name="ck_detector_schedule_interval"),
    )
    op.create_index("ix_detector_schedules_tenant_id", "detector_schedules", ["tenant_id"])
    op.create_index(
        "ix_detector_schedule_tenant_due",
        "detector_schedules",
        ["tenant_id", "enabled", "next_run_at"],
    )

    if op.get_bind().dialect.name == "postgresql":
        for table in (
            "commerce_stores",
            "commerce_skus",
            "inventory_snapshots",
            "fulfillment_events",
            "product_batches",
            "quality_reports",
            "detector_evaluation_runs",
            "detector_schedules",
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
        "detector_schedules",
        "detector_evaluation_runs",
        "quality_reports",
        "product_batches",
        "fulfillment_events",
        "inventory_snapshots",
        "commerce_skus",
        "commerce_stores",
    ):
        op.drop_table(table)
