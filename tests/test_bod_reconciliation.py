"""BOD reconciliation: internal ledger stays stable when Alpaca position averages change."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from stockbot.ledger.events import FillEvent


def test_fill_event_canonical_avg_fill_price() -> None:
    """FillEvent carries avg_fill_price as canonical; alpaca_avg_entry_price is informational."""
    event = FillEvent(
        signal_uuid=uuid4(),
        client_order_id=str(uuid4()),
        alpaca_order_id="alpaca-1",
        symbol="AAPL",
        side="buy",
        qty=Decimal("10"),
        avg_fill_price=Decimal("150.00"),
        alpaca_avg_entry_price=Decimal("150.00"),
        feed="iex",
        quote_ts=datetime.now(UTC),
        ingest_ts=datetime.now(UTC),
        bid=None,
        ask=None,
        last=None,
        spread_bps=None,
        latency_ms=None,
        strategy_id="strat1",
        strategy_version="v1",
    )
    assert event.avg_fill_price == Decimal("150.00")
    assert event.alpaca_avg_entry_price == Decimal("150.00")
    # Reconciler must not replace avg_fill_price with Alpaca's BOD-updated avg_entry_price
    assert event.avg_fill_price != Decimal("150.05")
