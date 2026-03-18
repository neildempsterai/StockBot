"""API service: health, strategies, signals, shadow trades, metrics. Manual signal submit is test-only."""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import func, select

from stockbot.db.models import ShadowTrade, Signal, SymbolIntelligenceSnapshot
from stockbot.db.session import get_session_factory
from stockbot.ledger.store import LedgerStore
from stockbot.scrappy.api import router as scrappy_router
from stockbot.scrappy.store import (
    get_gate_rejection_counts,
    get_latest_snapshot_by_symbol,
    get_recent_snapshots,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="StockBot API", version="0.1.0", lifespan=lifespan)
app.include_router(scrappy_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/strategies")
async def list_strategies() -> dict:
    """List configured strategies (INTRA_EVENT_MOMO shadow-only)."""
    return {
        "strategies": [
            {
                "strategy_id": "INTRA_EVENT_MOMO",
                "strategy_version": "0.1.0",
                "mode": "shadow-only",
                "entry_window_et": "09:35-11:30",
                "force_flat_et": "15:45",
            }
        ]
    }


@app.get("/v1/signals")
async def list_signals(limit: int = Query(default=50, ge=1, le=200)) -> dict:
    """Recent signals from DB."""
    factory = get_session_factory()
    async with factory() as session:
        store = LedgerStore(session)
        signals = await store.get_signals(limit=limit)
    return {
        "signals": [
            {
                "signal_uuid": str(s.signal_uuid),
                "symbol": s.symbol,
                "side": s.side,
                "qty": float(s.qty) if s.qty else None,
                "strategy_id": s.strategy_id,
                "strategy_version": s.strategy_version,
                "feed": s.feed,
                "signal_ts": s.quote_ts.isoformat() if s.quote_ts else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "reason_codes": s.reason_codes,
            }
            for s in signals
        ],
        "count": len(signals),
    }


def _snapshot_to_dict(snap: SymbolIntelligenceSnapshot | None) -> dict | None:
    if not snap:
        return None
    return {
        "id": snap.id,
        "symbol": snap.symbol,
        "snapshot_ts": snap.snapshot_ts.isoformat() if snap.snapshot_ts else None,
        "freshness_minutes": snap.freshness_minutes,
        "catalyst_direction": snap.catalyst_direction,
        "catalyst_strength": snap.catalyst_strength,
        "sentiment_label": snap.sentiment_label,
        "evidence_count": snap.evidence_count,
        "source_count": snap.source_count,
        "stale_flag": snap.stale_flag,
        "conflict_flag": snap.conflict_flag,
        "scrappy_run_id": snap.scrappy_run_id,
        "scrappy_version": snap.scrappy_version,
    }


@app.get("/v1/signals/{signal_uuid}")
async def get_signal(signal_uuid: UUID) -> dict:
    """Single signal by UUID; includes linked intelligence snapshot if present."""
    factory = get_session_factory()
    async with factory() as session:
        store = LedgerStore(session)
        s = await store.get_signal_by_uuid(signal_uuid)
        snapshot = None
        if s and getattr(s, "intelligence_snapshot_id", None):
            from sqlalchemy import select
            r = await session.execute(
                select(SymbolIntelligenceSnapshot).where(
                    SymbolIntelligenceSnapshot.id == s.intelligence_snapshot_id
                ).limit(1)
            )
            snapshot = r.scalars().first()
    if not s:
        raise HTTPException(status_code=404, detail="not_found")
    out = {
        "signal_uuid": str(s.signal_uuid),
        "symbol": s.symbol,
        "side": s.side,
        "qty": float(s.qty) if s.qty else None,
        "strategy_id": s.strategy_id,
        "strategy_version": s.strategy_version,
        "feed": s.feed,
        "signal_ts": s.quote_ts.isoformat() if s.quote_ts else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "reason_codes": s.reason_codes,
        "feature_snapshot_json": s.feature_snapshot_json,
        "quote_snapshot_json": s.quote_snapshot_json,
        "news_snapshot_json": s.news_snapshot_json,
        "intelligence_snapshot_id": getattr(s, "intelligence_snapshot_id", None),
    }
    if snapshot:
        out["intelligence_snapshot"] = _snapshot_to_dict(snapshot)
    return out


@app.get("/v1/intelligence/latest")
async def intelligence_latest(symbol: str = Query(..., min_length=1, max_length=32)) -> dict:
    """Latest intelligence snapshot for symbol."""
    factory = get_session_factory()
    async with factory() as session:
        snap = await get_latest_snapshot_by_symbol(session, symbol.strip().upper())
    if not snap:
        raise HTTPException(status_code=404, detail="no_snapshot")
    return _snapshot_to_dict(snap) or {}


@app.get("/v1/intelligence/recent")
async def intelligence_recent(
    symbol: str | None = Query(None, max_length=32),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Recent intelligence snapshots, optionally filtered by symbol."""
    factory = get_session_factory()
    async with factory() as session:
        rows = await get_recent_snapshots(session, limit=limit, symbol=symbol.strip().upper() if symbol else None)
    return {
        "snapshots": [_snapshot_to_dict(r) for r in rows],
        "count": len(rows),
    }


@app.get("/v1/intelligence/summary")
async def intelligence_summary() -> dict:
    """Summary: snapshot count, per-symbol latest catalyst direction."""
    factory = get_session_factory()
    async with factory() as session:
        total = (await session.execute(select(func.count(SymbolIntelligenceSnapshot.id)))).scalar() or 0
        rows = await get_recent_snapshots(session, limit=500)
    by_symbol: dict[str, dict] = {}
    for r in rows:
        if r.symbol not in by_symbol:
            by_symbol[r.symbol] = _snapshot_to_dict(r) or {}
    return {
        "snapshots_total": total,
        "symbols_with_snapshot": len(by_symbol),
        "by_symbol": by_symbol,
    }


@app.get("/v1/shadow/trades")
async def list_shadow_trades(limit: int = Query(default=50, ge=1, le=200)) -> dict:
    """Recent shadow trades (ideal + realistic)."""
    factory = get_session_factory()
    async with factory() as session:
        store = LedgerStore(session)
        trades = await store.list_shadow_trades(limit=limit)
    return {
        "trades": [
            {
                "signal_uuid": str(t.signal_uuid),
                "execution_mode": t.execution_mode,
                "entry_ts": t.entry_ts.isoformat() if t.entry_ts else None,
                "exit_ts": t.exit_ts.isoformat() if t.exit_ts else None,
                "entry_price": float(t.entry_price) if t.entry_price else None,
                "exit_price": float(t.exit_price) if t.exit_price else None,
                "exit_reason": t.exit_reason,
                "qty": float(t.qty) if t.qty else None,
                "gross_pnl": float(t.gross_pnl) if t.gross_pnl else None,
                "net_pnl": float(t.net_pnl) if t.net_pnl else None,
            }
            for t in trades
        ],
        "count": len(trades),
    }


@app.get("/v1/metrics/summary")
async def metrics_summary() -> dict:
    """Summary: signal count, shadow trade count, total net PnL, Scrappy attribution."""
    factory = get_session_factory()
    async with factory() as session:
        sig_count = (await session.execute(select(func.count(Signal.id)))).scalar() or 0
        trade_count = (await session.execute(select(func.count(ShadowTrade.id)))).scalar() or 0
        pnl_row = await session.execute(select(func.sum(ShadowTrade.net_pnl)))
        total_net_pnl = float(pnl_row.scalar() or 0)
        with_snapshot = (
            await session.execute(
                select(func.count(Signal.id)).where(Signal.intelligence_snapshot_id.isnot(None))
            )
        ).scalar() or 0
        without_snapshot = sig_count - with_snapshot
        rejection_counts = await get_gate_rejection_counts(session)
    return {
        "signals_total": sig_count,
        "shadow_trades_total": trade_count,
        "total_net_pnl_shadow": round(total_net_pnl, 2),
        "signals_with_scrappy_snapshot": with_snapshot,
        "signals_without_scrappy_snapshot": without_snapshot,
        "scrappy_gate_rejections": rejection_counts,
    }


@app.post("/v1/signals")
async def create_signal_manual(
    symbol: str, side: str, qty: float, strategy_id: str, strategy_version: str
) -> dict:
    """Manual/test-only: create a signal record. Does NOT place an Alpaca order."""
    signal_uuid = uuid.uuid4()
    return {
        "signal_uuid": str(signal_uuid),
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "note": "Manual/test-only; no order placed.",
    }
