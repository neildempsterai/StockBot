"""Signal opportunity attribution columns.

Revision ID: 014
Revises: 013
Create Date: 2026-03-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("signals", sa.Column("opportunity_run_id", sa.String(64), nullable=True))
    op.add_column("signals", sa.Column("opportunity_candidate_rank", sa.Integer(), nullable=True))
    op.add_column("signals", sa.Column("opportunity_candidate_source", sa.String(32), nullable=True))
    op.add_column("signals", sa.Column("opportunity_market_score", sa.Numeric(12, 6), nullable=True))
    op.add_column("signals", sa.Column("opportunity_semantic_score", sa.Numeric(12, 6), nullable=True))
    op.create_index("ix_signals_opportunity_run_id", "signals", ["opportunity_run_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_signals_opportunity_run_id", table_name="signals")
    op.drop_column("signals", "opportunity_semantic_score")
    op.drop_column("signals", "opportunity_market_score")
    op.drop_column("signals", "opportunity_candidate_source")
    op.drop_column("signals", "opportunity_candidate_rank")
    op.drop_column("signals", "opportunity_run_id")
