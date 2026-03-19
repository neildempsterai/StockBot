"""Add ai_referee_assessments and link from signals.

Revision ID: 010
Revises: 009
Create Date: 2026-03-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_referee_assessments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("assessment_id", sa.String(64), nullable=False, unique=True),
        sa.Column("assessment_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False, index=True),
        sa.Column("strategy_id", sa.String(64), nullable=False),
        sa.Column("strategy_version", sa.String(32), nullable=False),
        sa.Column("scrappy_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("scrappy_run_id", sa.String(64), nullable=True),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("referee_version", sa.String(32), nullable=False),
        sa.Column("setup_quality_score", sa.Integer(), nullable=False),
        sa.Column("catalyst_strength", sa.String(32), nullable=False),
        sa.Column("regime_label", sa.String(32), nullable=False),
        sa.Column("evidence_sufficiency", sa.String(32), nullable=False),
        sa.Column("contradiction_flag", sa.Boolean(), nullable=False),
        sa.Column("stale_flag", sa.Boolean(), nullable=False),
        sa.Column("decision_class", sa.String(32), nullable=False),
        sa.Column("reason_codes_json", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("plain_english_rationale", sa.Text(), nullable=True),
        sa.Column("input_snapshot_json", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("raw_response_json", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column(
        "signals",
        sa.Column("ai_referee_assessment_id", sa.Integer(), sa.ForeignKey("ai_referee_assessments.id"), nullable=True),
    )
    op.create_index("ix_signals_ai_referee_assessment_id", "signals", ["ai_referee_assessment_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_signals_ai_referee_assessment_id", table_name="signals")
    op.drop_column("signals", "ai_referee_assessment_id")
    op.drop_table("ai_referee_assessments")
