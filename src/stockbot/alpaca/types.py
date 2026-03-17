"""Alpaca API types. feed=iex for v0.1."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass
class Trade:
    symbol: str
    price: Decimal
    size: Decimal
    timestamp: datetime
    feed: str = "iex"


@dataclass
class Quote:
    symbol: str
    bid_price: Decimal
    ask_price: Decimal
    bid_size: Decimal
    ask_size: Decimal
    timestamp: datetime
    feed: str = "iex"


@dataclass
class Bar:
    symbol: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    timestamp: datetime
    feed: str = "iex"


@dataclass
class Snapshot:
    symbol: str
    latest_trade: Trade | None
    latest_quote: Quote | None
    minute_bar: Bar | None
    daily_bar: Bar | None
    prev_daily_bar: Bar | None
    feed: str = "iex"


@dataclass
class TradeUpdate:
    """Normalized trade update from paper trade_updates stream."""
    event: str  # accepted, partial_fill, fill, canceled, etc.
    order_id: str
    client_order_id: str
    symbol: str
    side: str
    qty: Decimal
    filled_qty: Decimal
    filled_avg_price: Decimal | None
    raw: dict[str, Any]
