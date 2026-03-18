"""API service: health, strategies, signals, shadow trades, metrics. Manual signal submit is test-only."""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from decimal import Decimal
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import func, select

from stockbot.db.session import get_session_factory
from stockbot.db.models import Signal, ShadowTrade
from stockbot.ledger.store import LedgerStore
from stockbot.scrappy.api import router as scrappy_router


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


@app.get("/v1/signals/{signal_uuid}")
async def get_signal(signal_uuid: UUID) -> dict:
    """Single signal by UUID."""
    factory = get_session_factory()
    async with factory() as session:
        store = LedgerStore(session)
        s = await store.get_signal_by_uuid(signal_uuid)
    if not s:
        raise HTTPException(status_code=404, detail="not_found")
    return {
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
    """Summary: signal count, shadow trade count, total net PnL."""
    factory = get_session_factory()
    async with factory() as session:
        sig_count = (await session.execute(select(func.count(Signal.id)))).scalar() or 0
        trade_count = (await session.execute(select(func.count(ShadowTrade.id)))).scalar() or 0
        pnl_row = await session.execute(select(func.sum(ShadowTrade.net_pnl)))
        total_net_pnl = float(pnl_row.scalar() or 0)
    return {
        "signals_total": sig_count,
        "shadow_trades_total": trade_count,
        "total_net_pnl_shadow": round(total_net_pnl, 2),
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
