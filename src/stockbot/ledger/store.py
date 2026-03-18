"""Persist fills/signals with feed provenance. Internal ledger is canonical."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stockbot.db.models import Fill, ShadowTrade, Signal
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
            reason_codes=event.reason_codes,
            feature_snapshot_json=event.feature_snapshot_json,
            quote_snapshot_json=event.quote_snapshot_json,
            news_snapshot_json=event.news_snapshot_json,
            intelligence_snapshot_id=event.intelligence_snapshot_id,
        )
        self._session.add(row)
        await self._session.commit()

    async def insert_shadow_trade(
        self,
        signal_uuid: UUID,
        execution_mode: str,
        entry_ts: datetime,
        exit_ts: datetime,
        entry_price: Decimal,
        exit_price: Decimal,
        stop_price: Decimal,
        target_price: Decimal,
        exit_reason: str,
        qty: Decimal,
        gross_pnl: Decimal,
        net_pnl: Decimal,
        slippage_bps: int = 0,
        fee_per_share: Decimal = Decimal("0"),
    ) -> None:
        row = ShadowTrade(
            signal_uuid=signal_uuid,
            execution_mode=execution_mode,
            entry_ts=entry_ts,
            exit_ts=exit_ts,
            entry_price=entry_price,
            exit_price=exit_price,
            stop_price=stop_price,
            target_price=target_price,
            exit_reason=exit_reason,
            qty=qty,
            gross_pnl=gross_pnl,
            net_pnl=net_pnl,
            slippage_bps=slippage_bps,
            fee_per_share=fee_per_share,
        )
        self._session.add(row)
        await self._session.commit()

    async def get_signal_by_uuid(self, signal_uuid: UUID) -> Signal | None:
        result = await self._session.execute(
            select(Signal).where(Signal.signal_uuid == signal_uuid).limit(1)
        )
        return result.scalars().first()

    async def get_signals(self, limit: int = 100) -> list[Signal]:
        result = await self._session.execute(
            select(Signal).order_by(Signal.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def list_shadow_trades(self, limit: int = 100) -> list[ShadowTrade]:
        result = await self._session.execute(
            select(ShadowTrade).order_by(ShadowTrade.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

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
