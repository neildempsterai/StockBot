"""
Alpaca trade gateway: owns paper trade_updates stream; normalizes to canonical ledger.
Stores fill events with feed provenance; persists paper_orders and paper_order_events.
client_order_id = signal_uuid.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from stockbot.alpaca.trading_stream import TradingStreamClient
from stockbot.db.models import PaperOrder, PaperOrderEvent
from stockbot.db.session import get_session_factory
from stockbot.ledger.events import FillEvent
from stockbot.ledger.store import LedgerStore


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


async def handle_trade_update(update) -> None:  # noqa: ANN001
    """Persist paper_orders, paper_order_events, and canonical fill (on fill/partial_fill)."""
    now = datetime.now(UTC)
    raw_order = (update.raw or {}).get("order", update.raw) or {}
    if isinstance(raw_order, dict):
        order_id = str(raw_order.get("id") or update.order_id or "")
        client_order_id = str(raw_order.get("client_order_id") or update.client_order_id or "")
        symbol = str(raw_order.get("symbol") or update.symbol or "")
        side = str(raw_order.get("side") or update.side or "")
        qty = raw_order.get("qty")
        if qty is not None:
            qty = Decimal(str(qty))
        else:
            qty = update.qty
        status = str(raw_order.get("status", ""))
        filled_qty = raw_order.get("filled_qty")
        if filled_qty is not None:
            filled_qty = Decimal(str(filled_qty))
        else:
            filled_qty = update.filled_qty
        filled_avg_price = raw_order.get("filled_avg_price")
        if filled_avg_price is not None:
            filled_avg_price = Decimal(str(filled_avg_price))
        else:
            filled_avg_price = update.filled_avg_price
        submitted_at = _parse_ts(raw_order.get("submitted_at"))
        updated_at = _parse_ts(raw_order.get("updated_at")) or now
        order_type = str(raw_order.get("type", ""))
        time_in_force = str(raw_order.get("time_in_force", ""))
        limit_price = raw_order.get("limit_price")
        limit_price = Decimal(str(limit_price)) if limit_price is not None else None
        stop_price = raw_order.get("stop_price")
        stop_price = Decimal(str(stop_price)) if stop_price is not None else None
        notional = raw_order.get("notional")
        notional = Decimal(str(notional)) if notional is not None else None
    else:
        order_id = str(update.order_id or "")
        client_order_id = str(update.client_order_id or "")
        symbol = update.symbol or ""
        side = update.side or ""
        qty = update.qty
        status = ""
        filled_qty = update.filled_qty
        filled_avg_price = update.filled_avg_price
        submitted_at = now
        updated_at = now
        order_type = ""
        time_in_force = ""
        limit_price = None
        stop_price = None
        notional = None

    factory = get_session_factory()
    async with factory() as session:
        # Upsert paper_orders
        if order_id:
            result = await session.execute(select(PaperOrder).where(PaperOrder.order_id == order_id).limit(1))
            existing_order = result.scalars().first()
            if existing_order:
                existing_order.updated_at = updated_at
                existing_order.status = status or existing_order.status
                existing_order.filled_qty = filled_qty if filled_qty is not None else existing_order.filled_qty
                existing_order.filled_avg_price = filled_avg_price if filled_avg_price is not None else existing_order.filled_avg_price
                existing_order.raw_json = update.raw
                # Preserve order_origin/order_intent set by API for operator_test
            else:
                try:
                    suuid = UUID(client_order_id) if client_order_id else None
                except (ValueError, TypeError):
                    suuid = None
                order_origin = "strategy"
                order_intent = None
                if client_order_id and client_order_id.startswith("paper_test_"):
                    order_origin = "operator_test"
                    for intent in ("buy_open", "sell_close", "short_open", "buy_cover", "flatten"):
                        if f"_{intent}_" in client_order_id:
                            order_intent = intent
                            break
                session.add(PaperOrder(
                    order_id=order_id,
                    client_order_id=client_order_id or None,
                    signal_uuid=suuid,
                    submitted_at=submitted_at,
                    updated_at=updated_at,
                    symbol=symbol,
                    side=side,
                    qty=qty or Decimal("0"),
                    notional=notional,
                    order_type=order_type or None,
                    time_in_force=time_in_force or None,
                    limit_price=limit_price,
                    stop_price=stop_price,
                    status=status or None,
                    filled_qty=filled_qty,
                    filled_avg_price=filled_avg_price,
                    raw_json=update.raw,
                    order_origin=order_origin,
                    order_intent=order_intent,
                    note=None,
                ))
        # Insert paper_order_events
        session.add(PaperOrderEvent(
            order_id=order_id,
            client_order_id=client_order_id or None,
            event_ts=now,
            event_type=update.event or "unknown",
            qty=filled_qty,
            price=filled_avg_price,
            raw_json=update.raw,
        ))
        await session.commit()

    if update.event not in ("fill", "partial_fill"):
        return
    # Operator test orders (paper_test_*) are not strategy fills; do not insert into canonical Fill ledger
    if (getattr(update, "client_order_id", None) or "").startswith("paper_test_"):
        return
    async with factory() as session:
        store = LedgerStore(session)
        existing = await store.get_fill_by_client_order_id(update.client_order_id)
        if existing and update.event == "fill":
            return
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
