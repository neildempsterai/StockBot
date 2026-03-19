"""Paper account snapshots, positions, orders, fills, portfolio history, activities; backtest runs/trades/summaries; signal paper_order_id.

Revision ID: 011
Revises: 010
Create Date: 2026-03-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Link signal to paper order when placed
    op.add_column("signals", sa.Column("paper_order_id", sa.String(64), nullable=True, index=True))
    op.add_column("signals", sa.Column("execution_mode", sa.String(16), nullable=True, index=True))

    op.create_table(
        "paper_account_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("snapshot_ts", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("account_number", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("equity", sa.Numeric(20, 4), nullable=True),
        sa.Column("last_equity", sa.Numeric(20, 4), nullable=True),
        sa.Column("cash", sa.Numeric(20, 4), nullable=True),
        sa.Column("buying_power", sa.Numeric(20, 4), nullable=True),
        sa.Column("regt_buying_power", sa.Numeric(20, 4), nullable=True),
        sa.Column("daytrading_buying_power", sa.Numeric(20, 4), nullable=True),
        sa.Column("multiplier", sa.String(16), nullable=True),
        sa.Column("initial_margin", sa.Numeric(20, 4), nullable=True),
        sa.Column("maintenance_margin", sa.Numeric(20, 4), nullable=True),
        sa.Column("long_market_value", sa.Numeric(20, 4), nullable=True),
        sa.Column("short_market_value", sa.Numeric(20, 4), nullable=True),
        sa.Column("pattern_day_trader", sa.Boolean(), nullable=True),
        sa.Column("trading_blocked", sa.Boolean(), nullable=True),
        sa.Column("transfers_blocked", sa.Boolean(), nullable=True),
        sa.Column("account_blocked", sa.Boolean(), nullable=True),
        sa.Column("raw_json", JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "paper_positions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("snapshot_ts", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("symbol", sa.String(32), nullable=False, index=True),
        sa.Column("side", sa.String(8), nullable=True),
        sa.Column("qty", sa.Numeric(20, 6), nullable=True),
        sa.Column("avg_entry_price", sa.Numeric(20, 6), nullable=True),
        sa.Column("market_price", sa.Numeric(20, 6), nullable=True),
        sa.Column("market_value", sa.Numeric(20, 4), nullable=True),
        sa.Column("cost_basis", sa.Numeric(20, 4), nullable=True),
        sa.Column("unrealized_pl", sa.Numeric(20, 4), nullable=True),
        sa.Column("unrealized_plpc", sa.Numeric(12, 6), nullable=True),
        sa.Column("current_price", sa.Numeric(20, 6), nullable=True),
        sa.Column("lastday_price", sa.Numeric(20, 6), nullable=True),
        sa.Column("change_today", sa.Numeric(12, 6), nullable=True),
        sa.Column("raw_json", JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "paper_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("client_order_id", sa.String(64), nullable=True, index=True),
        sa.Column("signal_uuid", sa.UUID(), nullable=True, index=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("symbol", sa.String(32), nullable=False, index=True),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("qty", sa.Numeric(20, 6), nullable=False),
        sa.Column("notional", sa.Numeric(20, 4), nullable=True),
        sa.Column("order_type", sa.String(16), nullable=True),
        sa.Column("time_in_force", sa.String(16), nullable=True),
        sa.Column("limit_price", sa.Numeric(20, 6), nullable=True),
        sa.Column("stop_price", sa.Numeric(20, 6), nullable=True),
        sa.Column("status", sa.String(32), nullable=True, index=True),
        sa.Column("filled_qty", sa.Numeric(20, 6), nullable=True),
        sa.Column("filled_avg_price", sa.Numeric(20, 6), nullable=True),
        sa.Column("raw_json", JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "paper_order_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.String(64), nullable=False, index=True),
        sa.Column("client_order_id", sa.String(64), nullable=True, index=True),
        sa.Column("event_ts", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("qty", sa.Numeric(20, 6), nullable=True),
        sa.Column("price", sa.Numeric(20, 6), nullable=True),
        sa.Column("raw_json", JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "paper_portfolio_history_points",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("series_ts", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("equity", sa.Numeric(20, 4), nullable=True),
        sa.Column("profit_loss", sa.Numeric(20, 4), nullable=True),
        sa.Column("profit_loss_pct", sa.Numeric(12, 6), nullable=True),
        sa.Column("base_value", sa.Numeric(20, 4), nullable=True),
        sa.Column("timeframe", sa.String(16), nullable=True),
        sa.Column("period", sa.String(16), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "account_activities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("activity_id", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("activity_type", sa.String(64), nullable=True, index=True),
        sa.Column("transaction_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("symbol", sa.String(32), nullable=True, index=True),
        sa.Column("qty", sa.Numeric(20, 6), nullable=True),
        sa.Column("price", sa.Numeric(20, 6), nullable=True),
        sa.Column("net_amount", sa.Numeric(20, 4), nullable=True),
        sa.Column("raw_json", JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("strategy_id", sa.String(64), nullable=False, index=True),
        sa.Column("strategy_version", sa.String(32), nullable=False),
        sa.Column("symbols_json", JSONB(), nullable=True),
        sa.Column("start_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("feed", sa.String(16), nullable=True),
        sa.Column("scrappy_mode", sa.String(16), nullable=True),
        sa.Column("ai_referee_mode", sa.String(16), nullable=True),
        sa.Column("assumptions_profile", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=True, index=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "backtest_trades",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False, index=True),
        sa.Column("symbol", sa.String(32), nullable=False, index=True),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("entry_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entry_price", sa.Numeric(20, 6), nullable=True),
        sa.Column("exit_price", sa.Numeric(20, 6), nullable=True),
        sa.Column("qty", sa.Numeric(20, 6), nullable=True),
        sa.Column("gross_pnl", sa.Numeric(20, 6), nullable=True),
        sa.Column("net_pnl", sa.Numeric(20, 6), nullable=True),
        sa.Column("exit_reason", sa.String(32), nullable=True),
        sa.Column("scrappy_mode", sa.String(16), nullable=True),
        sa.Column("ai_referee_mode", sa.String(16), nullable=True),
        sa.Column("raw_json", JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "backtest_summaries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("signal_count", sa.Integer(), nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.Column("win_rate", sa.Numeric(8, 4), nullable=True),
        sa.Column("avg_return_per_trade", sa.Numeric(12, 6), nullable=True),
        sa.Column("expectancy", sa.Numeric(20, 6), nullable=True),
        sa.Column("gross_pnl", sa.Numeric(20, 6), nullable=True),
        sa.Column("net_pnl", sa.Numeric(20, 6), nullable=True),
        sa.Column("max_drawdown", sa.Numeric(12, 4), nullable=True),
        sa.Column("rejection_counts_json", JSONB(), nullable=True),
        sa.Column("regime_label", sa.String(32), nullable=True),
        sa.Column("raw_json", JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("backtest_summaries")
    op.drop_table("backtest_trades")
    op.drop_table("backtest_runs")
    op.drop_table("account_activities")
    op.drop_table("paper_portfolio_history_points")
    op.drop_table("paper_order_events")
    op.drop_table("paper_orders")
    op.drop_table("paper_positions")
    op.drop_table("paper_account_snapshots")
    op.drop_column("signals", "execution_mode")
    op.drop_column("signals", "paper_order_id")
