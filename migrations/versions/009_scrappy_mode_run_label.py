"""Add scrappy_mode to signals, shadow_trades, scrappy_gate_rejections for run labeling.

Revision ID: 009
Revises: 008
Create Date: 2026-03-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("signals", sa.Column("scrappy_mode", sa.String(16), nullable=True))
    op.add_column("shadow_trades", sa.Column("scrappy_mode", sa.String(16), nullable=True))
    op.add_column("scrappy_gate_rejections", sa.Column("scrappy_mode", sa.String(16), nullable=True))
    op.create_index("ix_signals_scrappy_mode", "signals", ["scrappy_mode"], unique=False)
    op.create_index("ix_shadow_trades_scrappy_mode", "shadow_trades", ["scrappy_mode"], unique=False)
    op.create_index("ix_scrappy_gate_rejections_scrappy_mode", "scrappy_gate_rejections", ["scrappy_mode"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scrappy_gate_rejections_scrappy_mode", table_name="scrappy_gate_rejections")
    op.drop_index("ix_shadow_trades_scrappy_mode", table_name="shadow_trades")
    op.drop_index("ix_signals_scrappy_mode", table_name="signals")
    op.drop_column("scrappy_gate_rejections", "scrappy_mode")
    op.drop_column("shadow_trades", "scrappy_mode")
    op.drop_column("signals", "scrappy_mode")
