"""Opportunity runs, opportunity candidates, scrappy_auto_runs.

Revision ID: 013
Revises: 012
Create Date: 2026-03-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "opportunity_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("run_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("session", sa.String(32), nullable=True),
        sa.Column("market_candidates_count", sa.Integer(), nullable=False),
        sa.Column("semantic_candidates_count", sa.Integer(), nullable=False),
        sa.Column("blended_candidates_count", sa.Integer(), nullable=False),
        sa.Column("top_candidates_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_opportunity_runs_run_id", "opportunity_runs", ["run_id"], unique=True)
    op.create_index("ix_opportunity_runs_run_ts", "opportunity_runs", ["run_ts"], unique=False)
    op.create_index("ix_opportunity_runs_status", "opportunity_runs", ["status"], unique=False)
    op.create_index("ix_opportunity_runs_session", "opportunity_runs", ["session"], unique=False)

    op.create_table(
        "opportunity_candidates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("total_score", sa.Float(), nullable=False),
        sa.Column("market_score", sa.Float(), nullable=False),
        sa.Column("semantic_score", sa.Float(), nullable=False),
        sa.Column("candidate_source", sa.String(32), nullable=False),
        sa.Column("inclusion_reasons_json", JSONB(), nullable=True),
        sa.Column("filter_reasons_json", JSONB(), nullable=True),
        sa.Column("session", sa.String(32), nullable=True),
        sa.Column("news_count", sa.Integer(), nullable=False),
        sa.Column("scrappy_present", sa.Boolean(), nullable=False),
        sa.Column("freshness_minutes", sa.Integer(), nullable=True),
        sa.Column("raw_json", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_opportunity_candidates_run_id", "opportunity_candidates", ["run_id"], unique=False)
    op.create_index("ix_opportunity_candidates_symbol", "opportunity_candidates", ["symbol"], unique=False)
    op.create_index("ix_opportunity_candidates_rank", "opportunity_candidates", ["rank"], unique=False)
    op.create_index("ix_opportunity_candidates_candidate_source", "opportunity_candidates", ["candidate_source"], unique=False)

    op.create_table(
        "scrappy_auto_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("run_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("symbols_json", JSONB(), nullable=True),
        sa.Column("notes_created", sa.Integer(), nullable=False),
        sa.Column("snapshots_updated", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scrappy_auto_runs_run_id", "scrappy_auto_runs", ["run_id"], unique=True)
    op.create_index("ix_scrappy_auto_runs_run_ts", "scrappy_auto_runs", ["run_ts"], unique=False)
    op.create_index("ix_scrappy_auto_runs_status", "scrappy_auto_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("scrappy_auto_runs")
    op.drop_table("opportunity_candidates")
    op.drop_table("opportunity_runs")
