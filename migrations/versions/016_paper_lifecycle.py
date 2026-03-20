"""Paper lifecycle: entry plan, sizing, exit plan, protection mode.

Revision ID: 016
Revises: 015
Create Date: 2026-03-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "paper_lifecycles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("signal_uuid", UUID(as_uuid=True), nullable=False),
        sa.Column("entry_order_id", sa.String(64), nullable=True),
        sa.Column("exit_order_id", sa.String(64), nullable=True),
        sa.Column("client_order_id", sa.String(64), nullable=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("qty", sa.Numeric(20, 6), nullable=False),
        sa.Column("strategy_id", sa.String(64), nullable=False),
        sa.Column("strategy_version", sa.String(32), nullable=False),
        sa.Column("entry_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Numeric(20, 6), nullable=False),
        sa.Column("stop_price", sa.Numeric(20, 6), nullable=False),
        sa.Column("target_price", sa.Numeric(20, 6), nullable=False),
        sa.Column("force_flat_time", sa.String(16), nullable=True),
        sa.Column("protection_mode", sa.String(32), nullable=False, server_default="worker_mirrored"),
        sa.Column("intelligence_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("ai_referee_assessment_id", sa.Integer(), nullable=True),
        sa.Column("sizing_equity", sa.Numeric(20, 4), nullable=True),
        sa.Column("sizing_buying_power", sa.Numeric(20, 4), nullable=True),
        sa.Column("sizing_stop_distance", sa.Numeric(20, 6), nullable=True),
        sa.Column("sizing_risk_per_trade_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("sizing_max_position_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("sizing_max_gross_exposure_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("sizing_max_symbol_exposure_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("sizing_max_concurrent_positions", sa.Integer(), nullable=True),
        sa.Column("sizing_qty_proposed", sa.Numeric(20, 6), nullable=True),
        sa.Column("sizing_qty_approved", sa.Numeric(20, 6), nullable=False),
        sa.Column("sizing_notional_approved", sa.Numeric(20, 4), nullable=True),
        sa.Column("sizing_rejection_reason", sa.String(128), nullable=True),
        sa.Column("universe_source", sa.String(16), nullable=False, server_default="dynamic"),
        sa.Column("paper_armed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("paper_armed_reason", sa.String(64), nullable=True),
        sa.Column("lifecycle_status", sa.String(32), nullable=False, server_default="planned"),
        sa.Column("exit_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_reason", sa.String(32), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["intelligence_snapshot_id"], ["symbol_intelligence_snapshots.id"]),
        sa.ForeignKeyConstraint(["ai_referee_assessment_id"], ["ai_referee_assessments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_paper_lifecycles_signal_uuid"), "paper_lifecycles", ["signal_uuid"], unique=False)
    op.create_index(op.f("ix_paper_lifecycles_entry_order_id"), "paper_lifecycles", ["entry_order_id"], unique=False)
    op.create_index(op.f("ix_paper_lifecycles_exit_order_id"), "paper_lifecycles", ["exit_order_id"], unique=False)
    op.create_index(op.f("ix_paper_lifecycles_client_order_id"), "paper_lifecycles", ["client_order_id"], unique=False)
    op.create_index(op.f("ix_paper_lifecycles_symbol"), "paper_lifecycles", ["symbol"], unique=False)
    op.create_index(op.f("ix_paper_lifecycles_strategy_id"), "paper_lifecycles", ["strategy_id"], unique=False)
    op.create_index(op.f("ix_paper_lifecycles_entry_ts"), "paper_lifecycles", ["entry_ts"], unique=False)
    op.create_index(op.f("ix_paper_lifecycles_intelligence_snapshot_id"), "paper_lifecycles", ["intelligence_snapshot_id"], unique=False)
    op.create_index(op.f("ix_paper_lifecycles_ai_referee_assessment_id"), "paper_lifecycles", ["ai_referee_assessment_id"], unique=False)
    op.create_index(op.f("ix_paper_lifecycles_lifecycle_status"), "paper_lifecycles", ["lifecycle_status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_paper_lifecycles_lifecycle_status"), table_name="paper_lifecycles")
    op.drop_index(op.f("ix_paper_lifecycles_ai_referee_assessment_id"), table_name="paper_lifecycles")
    op.drop_index(op.f("ix_paper_lifecycles_intelligence_snapshot_id"), table_name="paper_lifecycles")
    op.drop_index(op.f("ix_paper_lifecycles_entry_ts"), table_name="paper_lifecycles")
    op.drop_index(op.f("ix_paper_lifecycles_strategy_id"), table_name="paper_lifecycles")
    op.drop_index(op.f("ix_paper_lifecycles_symbol"), table_name="paper_lifecycles")
    op.drop_index(op.f("ix_paper_lifecycles_client_order_id"), table_name="paper_lifecycles")
    op.drop_index(op.f("ix_paper_lifecycles_exit_order_id"), table_name="paper_lifecycles")
    op.drop_index(op.f("ix_paper_lifecycles_entry_order_id"), table_name="paper_lifecycles")
    op.drop_index(op.f("ix_paper_lifecycles_signal_uuid"), table_name="paper_lifecycles")
    op.drop_table("paper_lifecycles")
