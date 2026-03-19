"""Add content_mode, dedup_hash, why_this_matters, impact_horizon to market_intel_notes.

Revision ID: 003
Revises: 002
Create Date: 2026-03-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("scrappy_runs", sa.Column("run_scope", JSONB(), nullable=True))
    op.add_column("scrappy_runs", sa.Column("errors", sa.Text(), nullable=True))
    op.add_column("market_intel_notes", sa.Column("content_mode", sa.String(32), nullable=True))
    op.add_column("market_intel_notes", sa.Column("dedup_hash", sa.String(64), nullable=True))
    op.add_column("market_intel_notes", sa.Column("why_this_matters", sa.Text(), nullable=True))
    op.add_column("market_intel_notes", sa.Column("impact_horizon", sa.String(32), nullable=True))
    op.create_index("ix_market_intel_notes_dedup_hash", "market_intel_notes", ["dedup_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_market_intel_notes_dedup_hash", table_name="market_intel_notes")
    op.drop_column("market_intel_notes", "impact_horizon")
    op.drop_column("market_intel_notes", "why_this_matters")
    op.drop_column("market_intel_notes", "dedup_hash")
    op.drop_column("market_intel_notes", "content_mode")
    op.drop_column("scrappy_runs", "errors")
    op.drop_column("scrappy_runs", "run_scope")
