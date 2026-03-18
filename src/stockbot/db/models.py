"""Ledger and feed-provenance models. Internal ledger is canonical."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
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
