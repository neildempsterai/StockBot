"""Symbol intelligence snapshots and signal link.

Revision ID: 007
Revises: 006
Create Date: 2026-03-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "symbol_intelligence_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("snapshot_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("freshness_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("catalyst_direction", sa.String(32), nullable=False),
        sa.Column("catalyst_strength", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sentiment_label", sa.String(32), nullable=True),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_domains_json", JSONB(), nullable=True),
        sa.Column("thesis_tags_json", JSONB(), nullable=True),
        sa.Column("headline_set_json", JSONB(), nullable=True),
        sa.Column("stale_flag", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("conflict_flag", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("raw_evidence_refs_json", JSONB(), nullable=True),
        sa.Column("scrappy_run_id", sa.String(64), nullable=True),
        sa.Column("scrappy_version", sa.String(32), nullable=False, server_default="0.1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_symbol_intelligence_snapshots_symbol", "symbol_intelligence_snapshots", ["symbol"], unique=False)
    op.create_index("ix_symbol_intelligence_snapshots_snapshot_ts", "symbol_intelligence_snapshots", ["snapshot_ts"], unique=False)
    op.create_index("ix_symbol_intelligence_snapshots_catalyst_direction", "symbol_intelligence_snapshots", ["catalyst_direction"], unique=False)
    op.create_index("ix_symbol_intelligence_snapshots_scrappy_run_id", "symbol_intelligence_snapshots", ["scrappy_run_id"], unique=False)

    op.add_column(
        "signals",
        sa.Column("intelligence_snapshot_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_signals_intelligence_snapshot_id",
        "signals",
        "symbol_intelligence_snapshots",
        ["intelligence_snapshot_id"],
        ["id"],
    )
    op.create_index("ix_signals_intelligence_snapshot_id", "signals", ["intelligence_snapshot_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_signals_intelligence_snapshot_id", table_name="signals")
    op.drop_constraint("fk_signals_intelligence_snapshot_id", "signals", type_="foreignkey")
    op.drop_column("signals", "intelligence_snapshot_id")
    op.drop_index("ix_symbol_intelligence_snapshots_scrappy_run_id", table_name="symbol_intelligence_snapshots")
    op.drop_index("ix_symbol_intelligence_snapshots_catalyst_direction", table_name="symbol_intelligence_snapshots")
    op.drop_index("ix_symbol_intelligence_snapshots_snapshot_ts", table_name="symbol_intelligence_snapshots")
    op.drop_index("ix_symbol_intelligence_snapshots_symbol", table_name="symbol_intelligence_snapshots")
    op.drop_table("symbol_intelligence_snapshots")
