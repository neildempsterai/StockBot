"""Immutable event types for internal canonical ledger."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass
class SignalEvent:
    signal_uuid: UUID
    symbol: str
    side: str
    qty: Decimal
    strategy_id: str
    strategy_version: str
    feed: str
    quote_ts: datetime | None
    ingest_ts: datetime | None
    bid: Decimal | None
    ask: Decimal | None
    last: Decimal | None
    spread_bps: int | None
    latency_ms: int | None
    reason_codes: list[str] | None = None
    feature_snapshot_json: dict | None = None
    quote_snapshot_json: dict | None = None
    news_snapshot_json: dict | None = None


@dataclass
class FillEvent:
    signal_uuid: UUID
    client_order_id: str
    alpaca_order_id: str | None
    symbol: str
    side: str
    qty: Decimal
    avg_fill_price: Decimal
    alpaca_avg_entry_price: Decimal | None
    feed: str
    quote_ts: datetime | None
    ingest_ts: datetime | None
    bid: Decimal | None
    ask: Decimal | None
    last: Decimal | None
    spread_bps: int | None
    latency_ms: int | None
    strategy_id: str
    strategy_version: str
