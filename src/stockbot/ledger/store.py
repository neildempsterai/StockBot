"""Persist fills/signals with feed provenance. Internal ledger is canonical."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stockbot.db.models import Fill, OpportunityCandidateRow, PaperLifecycle, Signal, ShadowTrade
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
        self, limit: int = 100, scrappy_mode: str | None = None, strategy_id: str | None = None
    ) -> list[Signal]:
        q = select(Signal).order_by(Signal.created_at.desc()).limit(limit)
        if scrappy_mode is not None:
            q = q.where(Signal.scrappy_mode == scrappy_mode)
        if strategy_id is not None:
            q = q.where(Signal.strategy_id == strategy_id)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def list_shadow_trades(
        self, limit: int = 100, scrappy_mode: str | None = None, strategy_id: str | None = None
    ) -> list[ShadowTrade]:
        if strategy_id is not None:
            # ShadowTrade doesn't have strategy_id directly, need to join with Signal
            q = select(ShadowTrade).join(Signal, ShadowTrade.signal_uuid == Signal.signal_uuid).where(Signal.strategy_id == strategy_id).order_by(ShadowTrade.created_at.desc()).limit(limit)
        else:
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

    async def insert_paper_lifecycle(
        self,
        signal_uuid: UUID,
        symbol: str,
        side: str,
        qty: Decimal,
        strategy_id: str,
        strategy_version: str,
        entry_ts: datetime,
        entry_price: Decimal,
        stop_price: Decimal,
        target_price: Decimal,
        force_flat_time: str | None,
        protection_mode: str,
        intelligence_snapshot_id: int | None,
        ai_referee_assessment_id: int | None,
        sizing_equity: Decimal | None,
        sizing_buying_power: Decimal | None,
        sizing_stop_distance: Decimal | None,
        sizing_risk_per_trade_pct: Decimal | None,
        sizing_max_position_pct: Decimal | None,
        sizing_max_gross_exposure_pct: Decimal | None,
        sizing_max_symbol_exposure_pct: Decimal | None,
        sizing_max_concurrent_positions: int | None,
        sizing_qty_proposed: Decimal | None,
        sizing_qty_approved: Decimal,
        sizing_notional_approved: Decimal | None,
        sizing_rejection_reason: str | None,
        universe_source: str,
        paper_armed: bool,
        paper_armed_reason: str | None,
        lifecycle_status: str = "planned",
        holding_period_type: str = "intraday",
        max_hold_days: int = 0,
        entry_date: str | None = None,
        scheduled_exit_date: str | None = None,
        overnight_carry: bool = False,
    ) -> PaperLifecycle:
        """Create lifecycle record at entry planning time."""
        row = PaperLifecycle(
            signal_uuid=signal_uuid,
            entry_order_id=None,
            exit_order_id=None,
            client_order_id=str(signal_uuid),
            symbol=symbol,
            side=side,
            qty=qty,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            entry_ts=entry_ts,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            force_flat_time=force_flat_time,
            protection_mode=protection_mode,
            intelligence_snapshot_id=intelligence_snapshot_id,
            ai_referee_assessment_id=ai_referee_assessment_id,
            sizing_equity=sizing_equity,
            sizing_buying_power=sizing_buying_power,
            sizing_stop_distance=sizing_stop_distance,
            sizing_risk_per_trade_pct=sizing_risk_per_trade_pct,
            sizing_max_position_pct=sizing_max_position_pct,
            sizing_max_gross_exposure_pct=sizing_max_gross_exposure_pct,
            sizing_max_symbol_exposure_pct=sizing_max_symbol_exposure_pct,
            sizing_max_concurrent_positions=sizing_max_concurrent_positions,
            sizing_qty_proposed=sizing_qty_proposed,
            sizing_qty_approved=sizing_qty_approved,
            sizing_notional_approved=sizing_notional_approved,
            sizing_rejection_reason=sizing_rejection_reason,
            universe_source=universe_source,
            paper_armed=paper_armed,
            paper_armed_reason=paper_armed_reason,
            lifecycle_status=lifecycle_status,
            holding_period_type=holding_period_type,
            max_hold_days=max_hold_days,
            entry_date=entry_date,
            scheduled_exit_date=scheduled_exit_date,
            overnight_carry=overnight_carry,
        )
        self._session.add(row)
        await self._session.commit()
        return row

    async def update_paper_lifecycle_overnight(
        self, signal_uuid: UUID, days_held: int, overnight_carry_count: int
    ) -> None:
        """Update swing lifecycle with overnight carry state."""
        from sqlalchemy import update
        await self._session.execute(
            update(PaperLifecycle)
            .where(PaperLifecycle.signal_uuid == signal_uuid)
            .values(
                days_held=days_held,
                overnight_carry=True,
                overnight_carry_count=overnight_carry_count,
            )
        )
        await self._session.commit()

    async def update_paper_lifecycle_entry_order(
        self, signal_uuid: UUID, entry_order_id: str, lifecycle_status: str = "entry_submitted"
    ) -> None:
        """Update lifecycle when entry order is submitted."""
        from sqlalchemy import update
        await self._session.execute(
            update(PaperLifecycle)
            .where(PaperLifecycle.signal_uuid == signal_uuid)
            .values(entry_order_id=entry_order_id, lifecycle_status=lifecycle_status)
        )
        await self._session.commit()

    async def update_paper_lifecycle_entry_filled(
        self, signal_uuid: UUID, lifecycle_status: str = "entry_filled"
    ) -> None:
        """Update lifecycle when entry order is filled."""
        from sqlalchemy import update
        await self._session.execute(
            update(PaperLifecycle)
            .where(PaperLifecycle.signal_uuid == signal_uuid)
            .values(lifecycle_status=lifecycle_status)
        )
        await self._session.commit()

    async def update_paper_lifecycle_exit_order(
        self, signal_uuid: UUID, exit_order_id: str, exit_reason: str, lifecycle_status: str = "exit_submitted"
    ) -> None:
        """Update lifecycle when exit order is submitted."""
        from sqlalchemy import update
        await self._session.execute(
            update(PaperLifecycle)
            .where(PaperLifecycle.signal_uuid == signal_uuid)
            .values(exit_order_id=exit_order_id, exit_reason=exit_reason, lifecycle_status=lifecycle_status)
        )
        await self._session.commit()

    async def update_paper_lifecycle_exited(
        self, signal_uuid: UUID, exit_ts: datetime, lifecycle_status: str = "exited"
    ) -> None:
        """Update lifecycle when exit is completed."""
        from sqlalchemy import update
        await self._session.execute(
            update(PaperLifecycle)
            .where(PaperLifecycle.signal_uuid == signal_uuid)
            .values(exit_ts=exit_ts, lifecycle_status=lifecycle_status)
        )
        await self._session.commit()

    async def update_paper_lifecycle_error(
        self, signal_uuid: UUID, error: str, lifecycle_status: str | None = None
    ) -> None:
        """Update lifecycle with error state."""
        from sqlalchemy import update
        values = {"last_error": error}
        if lifecycle_status:
            values["lifecycle_status"] = lifecycle_status
        await self._session.execute(
            update(PaperLifecycle)
            .where(PaperLifecycle.signal_uuid == signal_uuid)
            .values(**values)
        )
        await self._session.commit()

    async def get_paper_lifecycle_by_signal_uuid(self, signal_uuid: UUID) -> PaperLifecycle | None:
        """Get lifecycle record by signal UUID."""
        result = await self._session.execute(
            select(PaperLifecycle).where(PaperLifecycle.signal_uuid == signal_uuid).limit(1)
        )
        return result.scalars().first()

    async def get_paper_lifecycle_by_entry_order_id(self, entry_order_id: str) -> PaperLifecycle | None:
        """Get lifecycle record by entry order ID."""
        result = await self._session.execute(
            select(PaperLifecycle).where(PaperLifecycle.entry_order_id == entry_order_id).limit(1)
        )
        return result.scalars().first()

    async def list_paper_lifecycles(
        self, limit: int = 100, lifecycle_status: str | None = None
    ) -> list[PaperLifecycle]:
        """List lifecycle records."""
        q = select(PaperLifecycle).order_by(PaperLifecycle.created_at.desc()).limit(limit)
        if lifecycle_status:
            q = q.where(PaperLifecycle.lifecycle_status == lifecycle_status)
        result = await self._session.execute(q)
        return list(result.scalars().all())
