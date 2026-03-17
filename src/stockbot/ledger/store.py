"""Persist fills/signals with feed provenance. Internal ledger is canonical."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stockbot.db.models import Fill, Signal
from stockbot.ledger.events import FillEvent, SignalEvent


class LedgerStore:
    """Canonical ledger: persist and query by signal_uuid / client_order_id."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert_signal(self, event: SignalEvent) -> None:
        row = Signal(
            signal_uuid=event.signal_uuid,
            symbol=event.symbol,
            side=event.side,
            qty=event.qty,
            strategy_id=event.strategy_id,
            strategy_version=event.strategy_version,
            feed=event.feed,
            quote_ts=event.quote_ts,
            ingest_ts=event.ingest_ts,
            bid=event.bid,
            ask=event.ask,
            last=event.last,
            spread_bps=event.spread_bps,
            latency_ms=event.latency_ms,
        )
        self._session.add(row)
        await self._session.commit()

    async def insert_fill(self, event: FillEvent) -> None:
        row = Fill(
            signal_uuid=event.signal_uuid,
            client_order_id=event.client_order_id,
            alpaca_order_id=event.alpaca_order_id,
            symbol=event.symbol,
            side=event.side,
            qty=event.qty,
            avg_fill_price=event.avg_fill_price,
            alpaca_avg_entry_price=event.alpaca_avg_entry_price,
            feed=event.feed,
            quote_ts=event.quote_ts,
            ingest_ts=event.ingest_ts,
            bid=event.bid,
            ask=event.ask,
            last=event.last,
            spread_bps=event.spread_bps,
            latency_ms=event.latency_ms,
            strategy_id=event.strategy_id,
            strategy_version=event.strategy_version,
            raw_event=None,
        )
        self._session.add(row)
        await self._session.commit()

    async def get_fill_by_client_order_id(self, client_order_id: str) -> Fill | None:
        result = await self._session.execute(
            select(Fill).where(Fill.client_order_id == client_order_id).limit(1)
        )
        return result.scalars().first()

    async def list_fills_for_reconciliation(self, limit: int = 500) -> list[Fill]:
        result = await self._session.execute(
            select(Fill).order_by(Fill.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())
