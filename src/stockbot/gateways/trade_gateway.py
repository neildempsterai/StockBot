"""
Alpaca trade gateway: owns paper trade_updates stream; normalizes to canonical ledger.
Stores fill events with feed provenance. client_order_id = signal_uuid.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from stockbot.alpaca.trading_stream import TradingStreamClient
from stockbot.config import get_settings
from stockbot.db.session import get_session_factory
from stockbot.ledger.events import FillEvent
from stockbot.ledger.store import LedgerStore


async def handle_trade_update(update) -> None:  # noqa: ANN001
    """Persist fill to canonical ledger (only on fill event)."""
    if update.event not in ("fill", "partial_fill"):
        return
    factory = get_session_factory()
    async with factory() as session:
        store = LedgerStore(session)
        existing = await store.get_fill_by_client_order_id(update.client_order_id)
        if existing and update.event == "fill":
            # Idempotent: already have a full fill row; optionally update alpaca_avg_entry_price
            return
        now = datetime.now(timezone.utc)
        try:
            signal_uuid = UUID(update.client_order_id)
        except (ValueError, TypeError):
            signal_uuid = UUID(int=0)
        fill_event = FillEvent(
            signal_uuid=signal_uuid,
            client_order_id=update.client_order_id,
            alpaca_order_id=update.order_id or None,
            symbol=update.symbol,
            side=update.side,
            qty=update.filled_qty if update.event == "fill" else update.qty,
            avg_fill_price=update.filled_avg_price or Decimal("0"),
            alpaca_avg_entry_price=update.filled_avg_price,
            feed="iex",
            quote_ts=now,
            ingest_ts=now,
            bid=None,
            ask=None,
            last=None,
            spread_bps=None,
            latency_ms=None,
            strategy_id="",
            strategy_version="",
        )
        await store.insert_fill(fill_event)


async def run_trade_gateway() -> None:
    stream = TradingStreamClient()
    stream.add_handler(handle_trade_update)
    while True:
        try:
            await stream.run()
        except Exception:
            await asyncio.sleep(5)
        else:
            break


def main() -> None:
    asyncio.run(run_trade_gateway())


if __name__ == "__main__":
    main()
