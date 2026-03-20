"""Ledger and feed-provenance models. Internal ledger is canonical."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Signal(Base):
    """Immutable signal row. client_order_id = signal_uuid for idempotency."""
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    signal_uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), unique=True, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    strategy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    feed: Mapped[str] = mapped_column(String(16), nullable=False, default="iex")
    quote_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingest_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bid: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    ask: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    last: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    spread_bps: Mapped[int | None] = mapped_column(nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Strategy audit: reason_codes, feature_snapshot, quote_snapshot, news_snapshot
    reason_codes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    feature_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    quote_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    news_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    intelligence_snapshot_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("symbol_intelligence_snapshots.id"), nullable=True, index=True
    )
    scrappy_mode: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    ai_referee_assessment_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ai_referee_assessments.id"), nullable=True, index=True
    )
    paper_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    execution_mode: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    # Opportunity attribution (from latest opportunity run when signal created)
    opportunity_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    opportunity_candidate_rank: Mapped[int | None] = mapped_column(nullable=True)
    opportunity_candidate_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    opportunity_market_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    opportunity_semantic_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)


class SymbolIntelligenceSnapshot(Base):
    """Symbol-scoped intelligence snapshot from Scrappy; used as gate/filter/tag only."""
    __tablename__ = "symbol_intelligence_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    snapshot_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    freshness_minutes: Mapped[int] = mapped_column(nullable=False, default=0)
    catalyst_direction: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    catalyst_strength: Mapped[int] = mapped_column(nullable=False, default=0)
    sentiment_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    evidence_count: Mapped[int] = mapped_column(nullable=False, default=0)
    source_count: Mapped[int] = mapped_column(nullable=False, default=0)
    source_domains_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    thesis_tags_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    headline_set_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    stale_flag: Mapped[bool] = mapped_column(nullable=False, default=False)
    conflict_flag: Mapped[bool] = mapped_column(nullable=False, default=False)
    raw_evidence_refs_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    scrappy_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    scrappy_version: Mapped[str] = mapped_column(String(32), nullable=False, default="0.1.0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScrappyGateRejection(Base):
    """Scrappy gating rejections for attribution (scrappy_conflict, scrappy_stale, scrappy_missing, etc.)."""
    __tablename__ = "scrappy_gate_rejections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scrappy_mode: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)


class Fill(Base):
    """Canonical fill ledger. Alpaca avg_entry_price is informational only."""
    __tablename__ = "fills"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    signal_uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    client_order_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    alpaca_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    avg_fill_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    alpaca_avg_entry_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    feed: Mapped[str] = mapped_column(String(16), nullable=False, default="iex")
    quote_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingest_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bid: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    ask: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    last: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    spread_bps: Mapped[int | None] = mapped_column(nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_event: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShadowTrade(Base):
    """Shadow fill record: ideal or realistic; no live order."""
    __tablename__ = "shadow_trades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    signal_uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    execution_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    entry_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    exit_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    stop_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    target_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    exit_reason: Mapped[str] = mapped_column(String(32), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    gross_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    net_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    slippage_bps: Mapped[int] = mapped_column(nullable=False, default=0)
    fee_per_share: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, default=0)
    scrappy_mode: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AiRefereeAssessment(Base):
    """AI referee structured assessment; no order authority. Linked from signals."""
    __tablename__ = "ai_referee_assessments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    assessment_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    assessment_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    scrappy_snapshot_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scrappy_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    referee_version: Mapped[str] = mapped_column(String(32), nullable=False)
    setup_quality_score: Mapped[int] = mapped_column(nullable=False)
    catalyst_strength: Mapped[str] = mapped_column(String(32), nullable=False)
    regime_label: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_sufficiency: Mapped[str] = mapped_column(String(32), nullable=False)
    contradiction_flag: Mapped[bool] = mapped_column(nullable=False)
    stale_flag: Mapped[bool] = mapped_column(nullable=False)
    decision_class: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_codes_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    plain_english_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_response_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReconciliationLog(Base):
    """Reconciler run log; Alpaca vs internal ledger."""
    __tablename__ = "reconciliation_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    orders_matched: Mapped[int] = mapped_column(nullable=False, default=0)
    orders_mismatch: Mapped[int] = mapped_column(nullable=False, default=0)
    positions_matched: Mapped[int] = mapped_column(nullable=False, default=0)
    positions_mismatch: Mapped[int] = mapped_column(nullable=False, default=0)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------- Paper account truth (reconciler / trade gateway) ----------


class PaperAccountSnapshot(Base):
    __tablename__ = "paper_account_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    snapshot_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    account_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    equity: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    last_equity: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    cash: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    buying_power: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    regt_buying_power: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    daytrading_buying_power: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    multiplier: Mapped[str | None] = mapped_column(String(16), nullable=True)
    initial_margin: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    maintenance_margin: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    long_market_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    short_market_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    pattern_day_trader: Mapped[bool | None] = mapped_column(nullable=True)
    trading_blocked: Mapped[bool | None] = mapped_column(nullable=True)
    transfers_blocked: Mapped[bool | None] = mapped_column(nullable=True)
    account_blocked: Mapped[bool | None] = mapped_column(nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class PaperPosition(Base):
    __tablename__ = "paper_positions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    snapshot_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str | None] = mapped_column(String(8), nullable=True)
    qty: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    avg_entry_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    market_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    market_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    cost_basis: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    unrealized_pl: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    unrealized_plpc: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    lastday_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    change_today: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class PaperOrder(Base):
    __tablename__ = "paper_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    client_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    signal_uuid: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    notional: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    order_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    time_in_force: Mapped[str | None] = mapped_column(String(16), nullable=True)
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    stop_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    filled_qty: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    filled_avg_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    order_origin: Mapped[str] = mapped_column(String(32), nullable=False, default="strategy", index=True)
    order_intent: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class PaperOrderEvent(Base):
    __tablename__ = "paper_order_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    client_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    event_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    qty: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class PaperLifecycle(Base):
    """Complete lifecycle record for strategy paper trades: entry plan, sizing, exit plan, protection mode."""
    __tablename__ = "paper_lifecycles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    signal_uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    entry_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    exit_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    client_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    strategy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    entry_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    stop_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    target_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    force_flat_time: Mapped[str | None] = mapped_column(String(16), nullable=True)
    protection_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="worker_mirrored")
    intelligence_snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("symbol_intelligence_snapshots.id"), nullable=True, index=True)
    ai_referee_assessment_id: Mapped[int | None] = mapped_column(ForeignKey("ai_referee_assessments.id"), nullable=True, index=True)
    # Sizing at entry
    sizing_equity: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    sizing_buying_power: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    sizing_stop_distance: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    sizing_risk_per_trade_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    sizing_max_position_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    sizing_max_gross_exposure_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    sizing_max_symbol_exposure_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    sizing_max_concurrent_positions: Mapped[int | None] = mapped_column(nullable=True)
    sizing_qty_proposed: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    sizing_qty_approved: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    sizing_notional_approved: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    sizing_rejection_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Universe and arming state at entry
    universe_source: Mapped[str] = mapped_column(String(16), nullable=False, default="dynamic")
    paper_armed: Mapped[bool] = mapped_column(nullable=False, default=False)
    paper_armed_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Holding period and swing lifecycle
    holding_period_type: Mapped[str] = mapped_column(String(16), nullable=False, default="intraday")  # intraday | swing
    max_hold_days: Mapped[int] = mapped_column(nullable=False, default=0)  # 0 = intraday
    entry_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD
    scheduled_exit_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # max hold date
    days_held: Mapped[int] = mapped_column(nullable=False, default=0)
    overnight_carry: Mapped[bool] = mapped_column(nullable=False, default=False)
    overnight_carry_count: Mapped[int] = mapped_column(nullable=False, default=0)
    # Lifecycle status
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned", index=True)
    exit_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PaperPortfolioHistoryPoint(Base):
    __tablename__ = "paper_portfolio_history_points"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    series_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    equity: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    profit_loss: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    profit_loss_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    base_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    timeframe: Mapped[str | None] = mapped_column(String(16), nullable=True)
    period: Mapped[str | None] = mapped_column(String(16), nullable=True)


class AccountActivity(Base):
    __tablename__ = "account_activities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    activity_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    activity_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    transaction_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    symbol: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    qty: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    strategy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    symbols_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    start_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    feed: Mapped[str | None] = mapped_column(String(16), nullable=True)
    scrappy_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ai_referee_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    assumptions_profile: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    entry_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    qty: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    gross_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    net_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    scrappy_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ai_referee_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class BacktestSummary(Base):
    __tablename__ = "backtest_summaries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    signal_count: Mapped[int | None] = mapped_column(nullable=True)
    trade_count: Mapped[int | None] = mapped_column(nullable=True)
    win_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    avg_return_per_trade: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    expectancy: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    gross_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    net_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    max_drawdown: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    rejection_counts_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    regime_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


# ----- Scrappy (market-intel sidecar) -----


class WatchlistSymbol(Base):
    """Symbols for Scrappy watchlist runs; POST /scrappy/run/watchlist uses these."""
    __tablename__ = "watchlist_symbols"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ScrappySourceHealth(Base):
    """Per-source health: fetch success vs note yield; attempt/success/failure counts."""
    __tablename__ = "scrappy_source_health"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(nullable=False, default=0)
    fetch_success_count: Mapped[int] = mapped_column(nullable=False, default=0)
    fetch_failure_count: Mapped[int] = mapped_column(nullable=False, default=0)
    candidate_count: Mapped[int] = mapped_column(nullable=False, default=0)
    post_dedup_count: Mapped[int] = mapped_column(nullable=False, default=0)
    notes_inserted_count: Mapped[int] = mapped_column(nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)


class ScrappyUrl(Base):
    """Dedup and recrawl state per normalized URL."""
    __tablename__ = "scrappy_urls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    normalized_url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    relevant: Mapped[bool | None] = mapped_column(nullable=True)
    last_drop_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    symbol_tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    theme_tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)


class ScrappyRun(Base):
    """Audit record for each Scrappy run; outcome from actual counters."""
    __tablename__ = "scrappy_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    run_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    candidate_url_count: Mapped[int] = mapped_column(nullable=False, default=0)
    post_dedup_count: Mapped[int] = mapped_column(nullable=False, default=0)
    notes_created: Mapped[int] = mapped_column(nullable=False, default=0)
    policy_blocked_count: Mapped[int] = mapped_column(nullable=False, default=0)
    metadata_only_count: Mapped[int] = mapped_column(nullable=False, default=0)
    open_text_count: Mapped[int] = mapped_column(nullable=False, default=0)
    notes_attempted_count: Mapped[int] = mapped_column(nullable=False, default=0)
    notes_rejected_count: Mapped[int] = mapped_column(nullable=False, default=0)
    drop_reason_counts: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    model_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    selected_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    actual_model_used: Mapped[str | None] = mapped_column(String(128), nullable=True)
    selection_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    run_scope: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    errors: Mapped[str | None] = mapped_column(Text, nullable=True)


class MarketIntelNote(Base):
    """Structured market-intel note; explainability and catalyst/sentiment."""
    __tablename__ = "market_intel_notes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    note_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_snippets: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    detected_symbols: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    primary_symbol: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    sector_tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    theme_tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    catalyst_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    sentiment_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sentiment_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    scrappy_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    content_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dedup_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    why_this_matters: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact_horizon: Mapped[str | None] = mapped_column(String(32), nullable=True)


# ---------- Scanner / opportunity discovery ----------


class ScannerRun(Base):
    """One scanner run: universe size, candidates scored, top count, status."""
    __tablename__ = "scanner_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    run_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    universe_mode: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    universe_size: Mapped[int] = mapped_column(nullable=False, default=0)
    candidates_scored: Mapped[int] = mapped_column(nullable=False, default=0)
    top_candidates_count: Mapped[int] = mapped_column(nullable=False, default=0)
    market_session: Mapped[str] = mapped_column(String(32), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScannerCandidateRow(Base):
    """Per-symbol candidate result for a scanner run."""
    __tablename__ = "scanner_candidates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(nullable=False, default=0, index=True)
    total_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    component_scores_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reason_codes_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    filter_reasons_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    candidate_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    gap_pct: Mapped[float | None] = mapped_column(nullable=True)
    spread_bps: Mapped[int | None] = mapped_column(nullable=True)
    dollar_volume_1m: Mapped[float | None] = mapped_column(nullable=True)
    rvol_5m: Mapped[float | None] = mapped_column(nullable=True)
    vwap_distance_pct: Mapped[float | None] = mapped_column(nullable=True)
    news_count: Mapped[int] = mapped_column(nullable=False, default=0)
    scrappy_present: Mapped[bool] = mapped_column(nullable=False, default=False)
    scrappy_catalyst_direction: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScannerToplistSnapshot(Base):
    """Latest top-candidate list snapshot for worker/API."""
    __tablename__ = "scanner_toplist_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    snapshot_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    symbols_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------- Opportunity engine (blended market + semantic) ----------


class OpportunityRun(Base):
    """One opportunity-engine run: blended market + semantic candidate counts and status."""
    __tablename__ = "opportunity_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    run_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    session: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    market_candidates_count: Mapped[int] = mapped_column(nullable=False, default=0)
    semantic_candidates_count: Mapped[int] = mapped_column(nullable=False, default=0)
    blended_candidates_count: Mapped[int] = mapped_column(nullable=False, default=0)
    top_candidates_count: Mapped[int] = mapped_column(nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OpportunityCandidateRow(Base):
    """Per-symbol opportunity candidate for a blended run."""
    __tablename__ = "opportunity_candidates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(nullable=False, default=0, index=True)
    total_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    market_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    semantic_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    candidate_source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    inclusion_reasons_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    filter_reasons_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    session: Mapped[str | None] = mapped_column(String(32), nullable=True)
    news_count: Mapped[int] = mapped_column(nullable=False, default=0)
    scrappy_present: Mapped[bool] = mapped_column(nullable=False, default=False)
    freshness_minutes: Mapped[int | None] = mapped_column(nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScrappyAutoRun(Base):
    """Audit record for each Scrappy auto-run (scanner-driven watchlist)."""
    __tablename__ = "scrappy_auto_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    run_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbols_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    notes_created: Mapped[int] = mapped_column(nullable=False, default=0)
    snapshots_updated: Mapped[int] = mapped_column(nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
