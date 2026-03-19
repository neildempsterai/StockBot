"""Persist fills/signals with feed provenance. Internal ledger is canonical."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stockbot.db.models import Fill, OpportunityCandidateRow, Signal, ShadowTrade
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
            scrappy_mode=event.scrappy_mode,
            ai_referee_assessment_id=event.ai_referee_assessment_id,
        )
        self._session.add(row)
        await self._session.flush()
        # Opportunity attribution: link to latest opportunity run/candidate for this symbol
        try:
            oc = await self._session.execute(
                select(OpportunityCandidateRow)
                .where(OpportunityCandidateRow.symbol == event.symbol.upper())
                .order_by(OpportunityCandidateRow.run_id.desc())
                .limit(1)
            )
            cand = oc.scalars().first()
            if cand:
                row.opportunity_run_id = cand.run_id
                row.opportunity_candidate_rank = cand.rank
                row.opportunity_candidate_source = cand.candidate_source
                row.opportunity_market_score = Decimal(str(cand.market_score)) if cand.market_score is not None else None
                row.opportunity_semantic_score = Decimal(str(cand.semantic_score)) if cand.semantic_score is not None else None
        except Exception:
            pass
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
        scrappy_mode: str | None = None,
    ) -> None:
        row = ShadowTrade(
            signal_uuid=signal_uuid,
            execution_mode=execution_mode,
            scrappy_mode=scrappy_mode,
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

    async def update_signal_paper_order(
        self, signal_uuid: UUID, paper_order_id: str, execution_mode: str = "paper"
    ) -> None:
        """Link signal to paper order after order accepted."""
        from sqlalchemy import update
        await self._session.execute(
            update(Signal)
            .where(Signal.signal_uuid == signal_uuid)
            .values(paper_order_id=paper_order_id, execution_mode=execution_mode)
        )
        await self._session.commit()

    async def get_signals(
        self, limit: int = 100, scrappy_mode: str | None = None
    ) -> list[Signal]:
        q = select(Signal).order_by(Signal.created_at.desc()).limit(limit)
        if scrappy_mode is not None:
            q = q.where(Signal.scrappy_mode == scrappy_mode)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def list_shadow_trades(
        self, limit: int = 100, scrappy_mode: str | None = None
    ) -> list[ShadowTrade]:
        q = select(ShadowTrade).order_by(ShadowTrade.created_at.desc()).limit(limit)
        if scrappy_mode is not None:
            q = q.where(ShadowTrade.scrappy_mode == scrappy_mode)
        result = await self._session.execute(q)
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
