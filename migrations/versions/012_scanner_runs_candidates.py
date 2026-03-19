"""Scanner runs, candidates, toplist snapshots.

Revision ID: 012
Revises: 011
Create Date: 2026-03-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scanner_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("run_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("universe_mode", sa.String(32), nullable=False),
        sa.Column("universe_size", sa.Integer(), nullable=False),
        sa.Column("candidates_scored", sa.Integer(), nullable=False),
        sa.Column("top_candidates_count", sa.Integer(), nullable=False),
        sa.Column("market_session", sa.String(32), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scanner_runs_run_id", "scanner_runs", ["run_id"], unique=True)
    op.create_index("ix_scanner_runs_run_ts", "scanner_runs", ["run_ts"], unique=False)
    op.create_index("ix_scanner_runs_status", "scanner_runs", ["status"], unique=False)

    op.create_table(
        "scanner_candidates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("total_score", sa.Float(), nullable=False),
        sa.Column("component_scores_json", JSONB(), nullable=True),
        sa.Column("reason_codes_json", JSONB(), nullable=True),
        sa.Column("filter_reasons_json", JSONB(), nullable=True),
        sa.Column("candidate_status", sa.String(32), nullable=False),
        sa.Column("price", sa.Numeric(20, 6), nullable=True),
        sa.Column("gap_pct", sa.Float(), nullable=True),
        sa.Column("spread_bps", sa.Integer(), nullable=True),
        sa.Column("dollar_volume_1m", sa.Float(), nullable=True),
        sa.Column("rvol_5m", sa.Float(), nullable=True),
        sa.Column("vwap_distance_pct", sa.Float(), nullable=True),
        sa.Column("news_count", sa.Integer(), nullable=False),
        sa.Column("scrappy_present", sa.Boolean(), nullable=False),
        sa.Column("scrappy_catalyst_direction", sa.String(32), nullable=True),
        sa.Column("raw_snapshot_json", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scanner_candidates_run_id", "scanner_candidates", ["run_id"], unique=False)
    op.create_index("ix_scanner_candidates_symbol", "scanner_candidates", ["symbol"], unique=False)
    op.create_index("ix_scanner_candidates_candidate_status", "scanner_candidates", ["candidate_status"], unique=False)
    op.create_index("ix_scanner_candidates_rank", "scanner_candidates", ["rank"], unique=False)

    op.create_table(
        "scanner_toplist_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("snapshot_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("symbols_json", JSONB(), nullable=True),
        sa.Column("run_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scanner_toplist_snapshots_snapshot_ts", "scanner_toplist_snapshots", ["snapshot_ts"], unique=False)
    op.create_index("ix_scanner_toplist_snapshots_run_id", "scanner_toplist_snapshots", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_table("scanner_toplist_snapshots")
    op.drop_table("scanner_candidates")
    op.drop_table("scanner_runs")
