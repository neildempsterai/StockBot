"""Strategy signals (reason_codes, snapshots) and shadow_trades.

Revision ID: 004
Revises: 003
Create Date: 2026-03-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("signals", sa.Column("reason_codes", JSONB(), nullable=True))
    op.add_column("signals", sa.Column("feature_snapshot_json", JSONB(), nullable=True))
    op.add_column("signals", sa.Column("quote_snapshot_json", JSONB(), nullable=True))
    op.add_column("signals", sa.Column("news_snapshot_json", JSONB(), nullable=True))

    op.create_table(
        "shadow_trades",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("signal_uuid", UUID(as_uuid=True), nullable=False),
        sa.Column("execution_mode", sa.String(16), nullable=False),
        sa.Column("entry_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Numeric(20, 6), nullable=False),
        sa.Column("exit_price", sa.Numeric(20, 6), nullable=False),
        sa.Column("stop_price", sa.Numeric(20, 6), nullable=False),
        sa.Column("target_price", sa.Numeric(20, 6), nullable=False),
        sa.Column("exit_reason", sa.String(32), nullable=False),
        sa.Column("qty", sa.Numeric(20, 6), nullable=False),
        sa.Column("gross_pnl", sa.Numeric(20, 6), nullable=False),
        sa.Column("net_pnl", sa.Numeric(20, 6), nullable=False),
        sa.Column("slippage_bps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fee_per_share", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shadow_trades_signal_uuid", "shadow_trades", ["signal_uuid"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_shadow_trades_signal_uuid", table_name="shadow_trades")
    op.drop_table("shadow_trades")
    op.drop_column("signals", "news_snapshot_json")
    op.drop_column("signals", "quote_snapshot_json")
    op.drop_column("signals", "feature_snapshot_json")
    op.drop_column("signals", "reason_codes")
