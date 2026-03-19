"""Feed provenance and canonical ledger.

Revision ID: 001
Revises:
Create Date: 2026-03-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "signals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("signal_uuid", UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("qty", sa.Numeric(20, 6), nullable=False),
        sa.Column("strategy_id", sa.String(64), nullable=False),
        sa.Column("strategy_version", sa.String(32), nullable=False),
        sa.Column("feed", sa.String(16), nullable=False, server_default="iex"),
        sa.Column("quote_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingest_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bid", sa.Numeric(20, 6), nullable=True),
        sa.Column("ask", sa.Numeric(20, 6), nullable=True),
        sa.Column("last", sa.Numeric(20, 6), nullable=True),
        sa.Column("spread_bps", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signals_signal_uuid", "signals", ["signal_uuid"], unique=True)
    op.create_index("ix_signals_symbol", "signals", ["symbol"], unique=False)
    op.create_index("ix_signals_strategy_id", "signals", ["strategy_id"], unique=False)

    op.create_table(
        "fills",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("signal_uuid", UUID(as_uuid=True), nullable=False),
        sa.Column("client_order_id", sa.String(64), nullable=False),
        sa.Column("alpaca_order_id", sa.String(64), nullable=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("qty", sa.Numeric(20, 6), nullable=False),
        sa.Column("avg_fill_price", sa.Numeric(20, 6), nullable=False),
        sa.Column("alpaca_avg_entry_price", sa.Numeric(20, 6), nullable=True),
        sa.Column("feed", sa.String(16), nullable=False, server_default="iex"),
        sa.Column("quote_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingest_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bid", sa.Numeric(20, 6), nullable=True),
        sa.Column("ask", sa.Numeric(20, 6), nullable=True),
        sa.Column("last", sa.Numeric(20, 6), nullable=True),
        sa.Column("spread_bps", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("strategy_id", sa.String(64), nullable=False),
        sa.Column("strategy_version", sa.String(32), nullable=False),
        sa.Column("raw_event", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fills_client_order_id", "fills", ["client_order_id"], unique=True)
    op.create_index("ix_fills_alpaca_order_id", "fills", ["alpaca_order_id"], unique=False)
    op.create_index("ix_fills_signal_uuid", "fills", ["signal_uuid"], unique=False)
    op.create_index("ix_fills_symbol", "fills", ["symbol"], unique=False)

    op.create_table(
        "reconciliation_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("orders_matched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("orders_mismatch", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("positions_matched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("positions_mismatch", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("details", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("reconciliation_logs")
    op.drop_index("ix_fills_symbol", table_name="fills")
    op.drop_index("ix_fills_signal_uuid", table_name="fills")
    op.drop_index("ix_fills_alpaca_order_id", table_name="fills")
    op.drop_index("ix_fills_client_order_id", table_name="fills")
    op.drop_table("fills")
    op.drop_index("ix_signals_strategy_id", table_name="signals")
    op.drop_index("ix_signals_symbol", table_name="signals")
    op.drop_index("ix_signals_signal_uuid", table_name="signals")
    op.drop_table("signals")
