"""Scrappy gate rejections for attribution metrics.

Revision ID: 008
Revises: 007
Create Date: 2026-03-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scrappy_gate_rejections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scrappy_gate_rejections_symbol", "scrappy_gate_rejections", ["symbol"], unique=False)
    op.create_index("ix_scrappy_gate_rejections_reason_code", "scrappy_gate_rejections", ["reason_code"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scrappy_gate_rejections_reason_code", table_name="scrappy_gate_rejections")
    op.drop_index("ix_scrappy_gate_rejections_symbol", table_name="scrappy_gate_rejections")
    op.drop_table("scrappy_gate_rejections")
