"""API service: health, strategies, signals, shadow trades, metrics. Manual signal submit is test-only."""
from __future__ import annotations

import json
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import UUID

import redis.asyncio as redis
from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError

from asyncpg.exceptions import InvalidPasswordError

from stockbot.ai_referee.store import (
    aggregate_decision_counts,
    aggregate_assisted_vs_unassisted_metrics,
    get_assessment_by_id,
    get_assessment_row_by_pk,
    list_recent_assessments,
)
from stockbot.alpaca.client import AlpacaClient
from stockbot.config import get_settings
from stockbot.strategies.open_drive_momo import STRATEGY_VERSION as ODM_VERSION
from stockbot.strategies.intra_event_momo import STRATEGY_VERSION as IEM_VERSION
from stockbot.strategies.intraday_continuation import STRATEGY_VERSION as IC_VERSION
from stockbot.strategies.swing_event_continuation import STRATEGY_VERSION as SEC_VERSION
from stockbot.execution.paper_test import (
    get_paper_test_status,
    run_buy_cover,
    run_buy_open,
    run_cancel_all,
    run_flatten_all,
    run_sell_close,
    run_short_open,
)
from stockbot.db.models import (
    AiRefereeAssessment,
    BacktestRun,
    BacktestSummary,
    BacktestTrade,
    Fill,
    OpportunityCandidateRow,
    OpportunityRun,
    PaperAccountSnapshot,
    PaperLifecycle,
    PaperOrder,
    PaperPortfolioHistoryPoint,
    ReconciliationLog,
    ScannerCandidateRow,
    ScannerRun,
    ScannerToplistSnapshot,
    ScrappyAutoRun,
    ScrappyGateRejection,
    ShadowTrade,
    Signal,
    SymbolIntelligenceSnapshot,
)
from stockbot.db.session import get_session_factory
from stockbot.ledger.store import LedgerStore
from stockbot.scrappy.api import router as scrappy_router
from stockbot.scrappy.snapshot import classify_coverage_status
from stockbot.scrappy.store import (
    get_gate_rejection_counts,
    get_gate_rejection_counts_by_mode,
    get_latest_snapshot_by_symbol,
    get_recent_snapshots,
)
from stockbot.scanner.store import (
    get_candidates_for_run,
    get_latest_live_scanner_run,
    get_latest_live_toplist_snapshot,
    get_latest_toplist_snapshot,
    get_scanner_run_by_id,
    get_scanner_runs,
    _row_to_candidate,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="StockBot API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(scrappy_router)


@app.exception_handler(InvalidPasswordError)
async def db_invalid_password_handler(_request: Request, exc: InvalidPasswordError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Database unavailable: password authentication failed. Check POSTGRES_PASSWORD in .env and that the postgres container was started with the same .env (e.g. ./scripts/dev/compose.sh up -d)."
        },
    )


@app.exception_handler(OperationalError)
async def db_operational_error_handler(_request: Request, exc: OperationalError) -> JSONResponse:
    orig = getattr(exc, "orig", None)
    if type(orig).__name__ == "InvalidPasswordError" or "password authentication failed" in str(orig or exc):
        detail = "Database unavailable: password authentication failed. Check POSTGRES_PASSWORD in .env and that the postgres container was started with the same .env (e.g. ./scripts/dev/compose.sh up -d)."
    else:
        detail = f"Database unavailable: {str(orig) if orig else str(exc)}"
    return JSONResponse(status_code=503, content={"detail": detail})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


WORKER_HEARTBEAT_KEY = "stockbot:worker:heartbeat"
GATEWAY_MARKET_HEARTBEAT_KEY = "stockbot:gateway:market:heartbeat"
GATEWAY_SYMBOL_REFRESH_TS_KEY = "stockbot:gateway:market:symbol_refresh_ts"
GATEWAY_SYMBOL_COUNT_KEY = "stockbot:gateway:market:symbol_count"
GATEWAY_SYMBOL_SOURCE_KEY = "stockbot:gateway:market:symbol_source"
GATEWAY_FALLBACK_REASON_KEY = "stockbot:gateway:market:fallback_reason"
SCANNER_TOP_TS_KEY = "stockbot:scanner:top_updated_at"
WORKER_UNIVERSE_REFRESH_TS_KEY = "stockbot:worker:universe_refresh_ts"
WORKER_UNIVERSE_SOURCE_KEY = "stockbot:worker:universe_source"
WORKER_UNIVERSE_COUNT_KEY = "stockbot:worker:universe_count"
WORKER_FALLBACK_REASON_KEY = "stockbot:worker:universe_fallback_reason"
PAPER_ARMED_REDIS_KEY = "stockbot:paper:armed"


@app.get("/health/detail")
async def health_detail() -> dict:
    """API, database, Redis, worker, gateway status; live universe and freshness for System Health."""
    out: dict = {"api": "ok"}

    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        out["database"] = "ok"
    except Exception as e:
        out["database"] = "error"
        out["database_hint"] = str(e).split("\n")[0][:120]

    try:
        from stockbot.market_sessions import current_session
        out["session"] = current_session()
    except Exception:
        out["session"] = "unknown"

    try:
        settings = get_settings()
        r = redis.from_url(settings.redis_url, decode_responses=True)
        await r.ping()
        worker_ts = await r.get(WORKER_HEARTBEAT_KEY)
        gateway_ts = await r.get(GATEWAY_MARKET_HEARTBEAT_KEY)
        gateway_symbol_refresh_ts = await r.get(GATEWAY_SYMBOL_REFRESH_TS_KEY)
        gateway_symbol_count = await r.get(GATEWAY_SYMBOL_COUNT_KEY)
        gateway_symbol_source = await r.get(GATEWAY_SYMBOL_SOURCE_KEY)
        gateway_fallback_reason = await r.get(GATEWAY_FALLBACK_REASON_KEY)
        worker_universe_refresh_ts = await r.get(WORKER_UNIVERSE_REFRESH_TS_KEY)
        worker_universe_source = await r.get(WORKER_UNIVERSE_SOURCE_KEY)
        worker_universe_count = await r.get(WORKER_UNIVERSE_COUNT_KEY)
        worker_fallback_reason = await r.get(WORKER_FALLBACK_REASON_KEY)
        await r.aclose()
        out["redis"] = "ok"
        out["worker"] = "ok" if worker_ts else "no_heartbeat"
        out["alpaca_gateway"] = "ok" if gateway_ts else "no_heartbeat"
        out["gateway_symbol_count"] = int(gateway_symbol_count) if gateway_symbol_count is not None else None
        out["gateway_symbol_refresh_ts"] = gateway_symbol_refresh_ts
        out["gateway_symbol_source"] = gateway_symbol_source
        out["gateway_fallback_reason"] = gateway_fallback_reason or None
        out["dynamic_symbols_available"] = gateway_symbol_source == "dynamic"
        out["worker_universe_count"] = int(worker_universe_count) if worker_universe_count is not None else None
        out["worker_universe_source"] = worker_universe_source
        out["worker_universe_refresh_ts"] = worker_universe_refresh_ts
        out["worker_fallback_reason"] = worker_fallback_reason or None
    except Exception:
        out["redis"] = "error"
        out["worker"] = "error"
        out["alpaca_gateway"] = "error"
        out["gateway_symbol_count"] = None
        out["gateway_symbol_refresh_ts"] = None
        out["gateway_symbol_source"] = None
        out["gateway_fallback_reason"] = None
        out["dynamic_symbols_available"] = False
        out["worker_universe_count"] = None
        out["worker_universe_source"] = None
        out["worker_fallback_reason"] = None
        out["worker_universe_refresh_ts"] = None

    try:
        factory = get_session_factory()
        async with factory() as session:
            r = await session.execute(
                select(ScannerRun)
                .where(ScannerRun.mode != "historical")
                .order_by(ScannerRun.run_ts.desc())
                .limit(1)
            )
            last_scanner = r.scalars().first()
            r2 = await session.execute(
                select(OpportunityRun)
                .where(~OpportunityRun.run_id.like("hist_%"))
                .order_by(OpportunityRun.run_ts.desc())
                .limit(1)
            )
            last_opportunity = r2.scalars().first()
            r3 = await session.execute(
                select(ScrappyAutoRun).order_by(ScrappyAutoRun.run_ts.desc()).limit(1)
            )
            last_scrappy_auto = r3.scalars().first()
        out["last_scanner_run_ts"] = last_scanner.run_ts.isoformat() if last_scanner and last_scanner.run_ts else None
        out["last_opportunity_run_ts"] = last_opportunity.run_ts.isoformat() if last_opportunity and last_opportunity.run_ts else None
        out["last_scrappy_auto_run_ts"] = last_scrappy_auto.run_ts.isoformat() if last_scrappy_auto and last_scrappy_auto.run_ts else None
    except Exception:
        out["last_scanner_run_ts"] = None
        out["last_opportunity_run_ts"] = None
        out["last_scrappy_auto_run_ts"] = None

    return out


@app.get("/v1/config")
def get_config() -> dict:
    """Read-only runtime config truth. No secrets."""
    s = get_settings()
    paper_e2e_supported = bool(s.alpaca_api_key_id and s.alpaca_api_secret_key)
    return {
        "FEED": s.feed,
        "EXTENDED_HOURS_ENABLED": s.extended_hours_enabled,
        "SCRAPPY_MODE": s.scrappy_mode,
        "AI_REFEREE_MODE": s.ai_referee_mode,
        "AI_REFEREE_ENABLED": s.ai_referee_enabled,
        "SCANNER_MODE": s.scanner_mode,
        "SCANNER_TOP_STALE_SEC": s.scanner_top_stale_sec,
        "STOCKBOT_UNIVERSE": s.stockbot_universe,
        "EXECUTION_MODE": getattr(s, "execution_mode", "shadow"),
        "PAPER_EXECUTION_ENABLED": getattr(s, "paper_execution_enabled", False),
        "PAPER_TRADING_ARMED": getattr(s, "paper_trading_armed", False),
        "OPERATOR_PAPER_TEST_ENABLED": getattr(s, "operator_paper_test_enabled", False),
        "OPERATOR_PAPER_TEST_MAX_QTY": getattr(s, "operator_paper_test_max_qty", 1),
        "OPERATOR_PAPER_TEST_MAX_NOTIONAL": getattr(s, "operator_paper_test_max_notional", 500.0),
        "PAPER_EXECUTION_E2E_SUPPORTED": paper_e2e_supported,
        "PAPER_EXECUTION_E2E_NOTE": (
            "Supported when Alpaca credentials are configured and trade gateway/reconciler are running."
            if paper_e2e_supported
            else "Not currently supported end-to-end because Alpaca credentials are not configured."
        ),
    }


@app.get("/v1/runtime/status")
async def runtime_status() -> dict:
    """Runtime mode truth: source-of-symbols, scheduler/ui mode, and paper support status."""
    s = get_settings()
    paper_e2e_supported = bool(s.alpaca_api_key_id and s.alpaca_api_secret_key)
    out: dict = {
        "strategy": {
            "id": "MULTI_STRATEGY",
            "active_strategies": [
                sid for sid, enabled in [
                    ("OPEN_DRIVE_MOMO", getattr(s, "strategy_open_drive_enabled", True)),
                    ("INTRADAY_CONTINUATION", getattr(s, "strategy_intraday_continuation_enabled", True)),
                    ("INTRA_EVENT_MOMO", getattr(s, "strategy_intra_event_momo_enabled", False)),
                    ("SWING_EVENT_CONTINUATION", getattr(s, "strategy_swing_event_continuation_enabled", True)),
                ] if enabled
            ],
            "execution_mode": s.execution_mode,
            "paper_execution_enabled": s.paper_execution_enabled,
        },
        "market_data": {
            "feed": s.feed,
            "extended_hours_enabled": s.extended_hours_enabled,
        },
        "risk_management": {
            "max_daily_loss_pct": getattr(s, "max_daily_loss_pct_equity", 3.0),
            "max_portfolio_heat_pct": getattr(s, "max_portfolio_heat_pct_equity", 5.0),
            "max_total_concurrent_positions": getattr(s, "max_total_concurrent_positions", 6),
            "trailing_stop_enabled": getattr(s, "trailing_stop_enabled", True),
            "partial_exit_enabled": getattr(s, "partial_exit_enabled", True),
            "min_entry_quality_score": getattr(s, "min_entry_quality_score", 40),
            "short_max_concurrent": getattr(s, "short_max_concurrent", 2),
            "max_short_gross_exposure_pct": getattr(s, "max_short_gross_exposure_pct_equity", 15.0),
        },
        "scheduler": {
            "mode": "daily_reset_only",
            "note": "Current scheduler only clears traded_today at 04:00 ET; no orchestration.",
        },
        "ui": {
            "mode": "react_operator_console",
            "note": "UI consumes backend routes only; no mock data mode in runtime endpoints.",
        },
        "paper_execution": {
            "supported_end_to_end": paper_e2e_supported,
            "note": (
                "Worker can submit paper orders; trade updates and reconciliation services exist in compose."
                if paper_e2e_supported
                else "Not yet supported end-to-end in this runtime because Alpaca credentials are missing."
            ),
        },
        "operator_paper_test": {
            "enabled": getattr(s, "operator_paper_test_enabled", False),
            "max_qty": getattr(s, "operator_paper_test_max_qty", 1),
            "max_notional": getattr(s, "operator_paper_test_max_notional", 500.0),
        },
        "scrappy": {
            "mode": getattr(s, "scrappy_mode", "advisory"),
            "paper_required": getattr(s, "scrappy_required_for_paper", False),
        },
        "ai_referee": {
            "enabled": getattr(s, "ai_referee_enabled", False),
            "mode": getattr(s, "ai_referee_mode", "advisory"),
            "paper_required": getattr(s, "ai_referee_required_for_paper", False),
        },
    }
    try:
        r = redis.from_url(s.redis_url, decode_responses=True)
        gateway_source = await r.get(GATEWAY_SYMBOL_SOURCE_KEY)
        gateway_reason = await r.get(GATEWAY_FALLBACK_REASON_KEY)
        gateway_count = await r.get(GATEWAY_SYMBOL_COUNT_KEY)
        gateway_refresh_ts = await r.get(GATEWAY_SYMBOL_REFRESH_TS_KEY)
        worker_source = await r.get(WORKER_UNIVERSE_SOURCE_KEY)
        worker_reason = await r.get(WORKER_FALLBACK_REASON_KEY)
        worker_count = await r.get(WORKER_UNIVERSE_COUNT_KEY)
        worker_refresh_ts = await r.get(WORKER_UNIVERSE_REFRESH_TS_KEY)
        scanner_top_ts = await r.get(SCANNER_TOP_TS_KEY)
        await r.aclose()
        out["symbol_source"] = {
            "gateway": {
                "active_source": gateway_source or "unknown",
                "active_source_label": "redis_dynamic" if gateway_source == "dynamic" else "static_env",
                "symbol_count": int(gateway_count) if gateway_count is not None else None,
                "refresh_ts": gateway_refresh_ts,
                "fallback_reason": gateway_reason or None,
            },
            "worker": {
                "active_source": worker_source or "unknown",
                "active_source_label": "redis_dynamic" if worker_source in ("dynamic", "hybrid") else "static_env",
                "symbol_count": int(worker_count) if worker_count is not None else None,
                "refresh_ts": worker_refresh_ts,
                "fallback_reason": worker_reason or None,
            },
            "dynamic_universe_last_updated_at": scanner_top_ts,
            "dynamic_universe_stale_after_sec": s.scanner_top_stale_sec,
        }
    except Exception as e:
        out["symbol_source"] = {
            "gateway": {"active_source": "unknown", "active_source_label": "unknown", "fallback_reason": None},
            "worker": {"active_source": "unknown", "active_source_label": "unknown", "fallback_reason": None},
            "dynamic_universe_last_updated_at": None,
            "dynamic_universe_stale_after_sec": s.scanner_top_stale_sec,
            "error": str(e)[:120],
        }
    # Paper armed: config permits arming; actual armed state is in Redis (so we can disarm via API without restart)
    try:
        r2 = redis.from_url(s.redis_url, decode_responses=True)
        paper_armed_redis = await r2.get(PAPER_ARMED_REDIS_KEY)
        await r2.aclose()
        config_armed = getattr(s, "paper_trading_armed", False)
        effective_armed = config_armed and paper_armed_redis == "1"
        out["paper_trading_armed"] = effective_armed
        if effective_armed:
            out["paper_armed_reason"] = "armed"
        elif not config_armed:
            out["paper_armed_reason"] = "disarmed_by_default"
        else:
            out["paper_armed_reason"] = "disarmed_via_api"
    except Exception:
        out["paper_trading_armed"] = False
        out["paper_armed_reason"] = "disarmed_unable_to_read_redis"
    return out


@app.get("/v1/runtime/worker-telemetry")
async def runtime_worker_telemetry() -> dict:
    """Live worker telemetry: position runtime state, regime, circuit breaker."""
    try:
        r = redis.from_url(get_settings().redis_url, decode_responses=True)
        pos_raw = await r.get("worker:position_runtime")
        meta_raw = await r.get("worker:runtime_meta")
        await r.aclose()
        pos_data = json.loads(pos_raw) if pos_raw else {}
        meta_data = json.loads(meta_raw) if meta_raw else {}
        return {
            "positions": pos_data,
            "regime": meta_data.get("regime"),
            "circuit_breaker": meta_data.get("circuit_breaker"),
        }
    except Exception as e:
        return {"positions": {}, "regime": None, "circuit_breaker": None, "error": str(e)[:200]}


def _replay_sessions() -> list[dict]:
    """Discover replay sessions from replay/ dir (if present)."""
    # API may run in Docker without replay/; repo root relative to this file.
    replay_dir = Path(__file__).resolve().parent.parent.parent / "replay"
    if not replay_dir.is_dir():
        return []
    sessions = []
    for path in replay_dir.iterdir():
        if not path.is_dir():
            continue
        meta_file = path / "metadata.json"
        if not meta_file.is_file():
            continue
        try:
            with meta_file.open() as f:
                meta = json.load(f)
            sessions.append({
                "id": meta.get("session_id", path.name),
                "date_utc": meta.get("date_utc", ""),
                "description": meta.get("description", ""),
            })
        except (json.JSONDecodeError, OSError):
            continue
    sessions.sort(key=lambda s: s["id"])
    return sessions


@app.get("/v1/backtest/status")
def backtest_status() -> dict:
    """Backtest runner status for Strategy Lab: available sessions and message."""
    sessions = _replay_sessions()
    available = len(sessions) > 0
    if available:
        message = "Replay sessions available. Run from host: make replay (or python scripts/run_replay.py --session replay/session_001). REST trigger for Strategy Lab is planned."
    else:
        message = "Replay data not in container. On host, run: make replay. REST trigger for Strategy Lab is planned."
    return {
        "available": available,
        "sessions": sessions,
        "message": message,
    }


@app.get("/v1/strategies")
async def list_strategies() -> dict:
    """List all configured strategies with their enable/paper status."""
    settings = get_settings()
    exec_mode = getattr(settings, "execution_mode", "shadow")
    strategies = [
        {
            "strategy_id": "OPEN_DRIVE_MOMO",
            "strategy_version": ODM_VERSION,
            "mode": "paper" if exec_mode == "paper" and getattr(settings, "strategy_open_drive_paper_enabled", True) else "shadow-only",
            "entry_window_et": "09:35-10:00",
            "force_flat_et": "15:45",
            "enabled": getattr(settings, "strategy_open_drive_enabled", True),
            "paper_enabled": getattr(settings, "strategy_open_drive_paper_enabled", True),
            "holding_period_type": "intraday",
        },
        {
            "strategy_id": "INTRADAY_CONTINUATION",
            "strategy_version": IC_VERSION,
            "mode": "paper" if exec_mode == "paper" and getattr(settings, "strategy_intraday_continuation_paper_enabled", False) else "shadow-only",
            "entry_window_et": "10:30-14:30",
            "force_flat_et": "15:45",
            "enabled": getattr(settings, "strategy_intraday_continuation_enabled", True),
            "paper_enabled": getattr(settings, "strategy_intraday_continuation_paper_enabled", False),
            "holding_period_type": "intraday",
        },
        {
            "strategy_id": "INTRA_EVENT_MOMO",
            "strategy_version": IEM_VERSION,
            "mode": "shadow-only",
            "entry_window_et": "09:35-11:30",
            "force_flat_et": "15:45",
            "enabled": getattr(settings, "strategy_intra_event_momo_enabled", False),
            "paper_enabled": False,
            "holding_period_type": "intraday",
            "note": "frozen baseline",
        },
        {
            "strategy_id": "SWING_EVENT_CONTINUATION",
            "strategy_version": SEC_VERSION,
            "mode": "paper" if exec_mode == "paper" and getattr(settings, "strategy_swing_event_continuation_paper_enabled", False) else "shadow-only",
            "entry_window_et": "13:00-15:30",
            "force_flat_et": None,
            "enabled": getattr(settings, "strategy_swing_event_continuation_enabled", True),
            "paper_enabled": getattr(settings, "strategy_swing_event_continuation_paper_enabled", False),
            "holding_period_type": "swing",
            "max_hold_days": 5,
            "overnight_carry": True,
        },
    ]
    return {"strategies": strategies}


@app.get("/v1/signals/rejection-summary")
async def get_signals_rejection_summary() -> dict:
    """Recent candidate rejection reasons summary for operator visibility.
    Reads from worker runtime (Redis) first, falls back to DB (Scrappy/AI gate rejections) if needed.
    """
    try:
        from datetime import UTC, datetime, timedelta
        from stockbot.market_sessions import current_session
        from stockbot.config import get_settings
        import redis.asyncio as redis
        
        settings = get_settings()
        session_label = current_session()
        entry_windows = {
            "OPEN_DRIVE_MOMO": ("09:35", "11:30"),
            "INTRADAY_CONTINUATION": ("10:30", "14:30"),
            "SWING_EVENT_CONTINUATION": ("13:00", "15:30"),
        }
        
        # Check if currently in any entry window
        now_utc = datetime.now(UTC)
        in_entry_window = False
        active_windows: list[str] = []
        entry_start = "09:35"
        entry_end = "15:30"
        try:
            import zoneinfo
            et = zoneinfo.ZoneInfo("America/New_York")
            et_now = now_utc.astimezone(et)
            et_time_str = et_now.strftime("%H:%M")
            for sid, (start, end) in entry_windows.items():
                if start <= et_time_str <= end:
                    in_entry_window = True
                    active_windows.append(f"{sid} ({start}-{end})")
            if active_windows:
                entry_start = active_windows[0].split("(")[1].rstrip(")").split("-")[0]
                entry_end = active_windows[-1].split("(")[1].rstrip(")").split("-")[1]
        except Exception:
            in_entry_window = False
        
        # PRIMARY SOURCE: Read worker rejection summary from Redis (strategy-level rejections)
        recent_rejections: dict[str, int] = {}
        source = "none"
        try:
            r = redis.from_url(settings.redis_url, decode_responses=True)
            # Scan for all rejection keys: stockbot:worker:rejection_summary:REASON
            pattern = "stockbot:worker:rejection_summary:*"
            cursor = 0
            rejection_keys: list[str] = []
            while True:
                cursor, keys = await r.scan(cursor, match=pattern, count=100)
                rejection_keys.extend([k for k in keys if ":rejection_summary:" in k and k.count(":") == 3])
                if cursor == 0:
                    break
            # Extract rejection reasons and counts (skip symbol-specific keys)
            for key in rejection_keys:
                # Format: stockbot:worker:rejection_summary:REASON
                # Skip: stockbot:worker:rejection_summary:SYMBOL:REASON
                parts = key.split(":")
                if len(parts) == 4 and parts[3]:  # Only reason-level keys, not symbol-level
                    reason = parts[3]
                    count_str = await r.get(key)
                    if count_str:
                        try:
                            count = int(count_str)
                            recent_rejections[reason] = recent_rejections.get(reason, 0) + count
                        except (ValueError, TypeError):
                            pass
            await r.aclose()
            if recent_rejections:
                source = "worker_runtime"
        except Exception as e:
            logger.debug("worker_rejection_summary_read_failed: %s", e)
        
        # FALLBACK: If no worker rejections found, read from DB (Scrappy/AI gate rejections)
        if not recent_rejections:
            try:
                factory = get_session_factory()
                async with factory() as session:
                    cutoff = datetime.now(UTC) - timedelta(minutes=30)
                    r = await session.execute(
                        select(ScrappyGateRejection.reason_code, func.count(ScrappyGateRejection.id))
                        .where(ScrappyGateRejection.created_at >= cutoff)
                        .group_by(ScrappyGateRejection.reason_code)
                    )
                    recent_rejections = {row[0]: row[1] for row in r.all()}
                if recent_rejections:
                    source = "fallback_db"
            except Exception as e:
                logger.debug("db_rejection_summary_read_failed: %s", e)
        
        result = {
            "recent_rejections": recent_rejections,
            "session": session_label,
            "entry_window": f"{entry_start}-{entry_end} ET",
            "in_entry_window": in_entry_window,
            "top_rejection_reasons": sorted(
                recent_rejections.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
            "source": source,
        }
        return _sanitize_json_value(result)
    except Exception as e:
        logger.exception("Error in get_signals_rejection_summary")
        return _sanitize_json_value({
            "error": "internal_error",
            "message": str(e)[:200],
            "recent_rejections": {},
            "session": "unknown",
            "entry_window": "09:35-11:30 ET",
            "in_entry_window": False,
            "top_rejection_reasons": [],
            "source": "none",
        })


@app.get("/v1/signals")
async def list_signals(
    limit: int = Query(default=50, ge=1, le=200),
    scrappy_mode: str | None = Query(None, description="Filter by scrappy_mode (advisory, required, off)"),
    strategy_id: str | None = Query(None, description="Filter by strategy_id (e.g., OPEN_DRIVE_MOMO, INTRADAY_CONTINUATION)"),
) -> dict:
    """Recent signals from DB, optionally filtered by scrappy_mode."""
    factory = get_session_factory()
    async with factory() as session:
        store = LedgerStore(session)
        signals = await store.get_signals(limit=limit, scrappy_mode=scrappy_mode, strategy_id=strategy_id)
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
                "scrappy_mode": getattr(s, "scrappy_mode", None),
                "paper_order_id": getattr(s, "paper_order_id", None),
                "execution_mode": getattr(s, "execution_mode", None),
                # Opportunity attribution
                "opportunity_run_id": getattr(s, "opportunity_run_id", None),
                "opportunity_candidate_rank": getattr(s, "opportunity_candidate_rank", None),
                "opportunity_candidate_source": getattr(s, "opportunity_candidate_source", None),
                "opportunity_market_score": float(getattr(s, "opportunity_market_score", None)) if getattr(s, "opportunity_market_score", None) is not None else None,
                "opportunity_semantic_score": float(getattr(s, "opportunity_semantic_score", None)) if getattr(s, "opportunity_semantic_score", None) is not None else None,
                # Intelligence participation
                "intelligence_snapshot_id": getattr(s, "intelligence_snapshot_id", None),
                "ai_referee_assessment_id": getattr(s, "ai_referee_assessment_id", None),
                # Price data at signal time
                "bid": float(s.bid) if s.bid is not None else None,
                "ask": float(s.ask) if s.ask is not None else None,
                "last": float(s.last) if s.last is not None else None,
                "spread_bps": s.spread_bps,
            }
            for s in signals
        ],
        "count": len(signals),
        "scrappy_mode_filter": scrappy_mode,
    }


def _snapshot_to_dict(snap: SymbolIntelligenceSnapshot | None) -> dict | None:
    if not snap:
        return None
    # catalyst_strength is int in DB; always serialize as string for frontend
    raw_strength = getattr(snap, "catalyst_strength", None)
    catalyst_strength: str | None = str(raw_strength) if raw_strength is not None else None
    
    # Classify coverage status
    coverage = classify_coverage_status(snap)
    headline_set = getattr(snap, "headline_set_json", None) or []
    headline_count = len(headline_set) if isinstance(headline_set, list) else 0
    out = {
        "id": snap.id,
        "symbol": snap.symbol,
        "snapshot_ts": snap.snapshot_ts.isoformat() if snap.snapshot_ts else None,
        "freshness_minutes": snap.freshness_minutes,
        "catalyst_direction": snap.catalyst_direction,
        "catalyst_strength": catalyst_strength,
        "sentiment_label": snap.sentiment_label,
        "evidence_count": snap.evidence_count,
        "source_count": snap.source_count,
        "stale_flag": bool(snap.stale_flag) if snap.stale_flag is not None else None,
        "conflict_flag": bool(snap.conflict_flag) if snap.conflict_flag is not None else None,
        "scrappy_run_id": snap.scrappy_run_id,
        "scrappy_version": snap.scrappy_version,
        "headline_count": headline_count,
        "headlines": headline_set[:10] if isinstance(headline_set, list) else [],
        "coverage_status": coverage.status,
        "coverage_reason": coverage.reason,
        "coverage_latest_evidence_ts": coverage.latest_evidence_ts.isoformat() if coverage.latest_evidence_ts else None,
    }
    return out


def _snapshot_to_scrappy_enrichment(snap: SymbolIntelligenceSnapshot | None) -> dict:
    """Flat Scrappy-facing fields for opportunity/signal enrichment."""
    if not snap:
        return {}
    raw_strength = getattr(snap, "catalyst_strength", None)
    catalyst_strength: str | None = str(raw_strength) if raw_strength is not None else None
    headline_set = getattr(snap, "headline_set_json", None) or []
    headline_count = len(headline_set) if isinstance(headline_set, list) else 0
    
    # Classify coverage status
    coverage = classify_coverage_status(snap)
    
    return {
        "latest_scrappy_snapshot_id": snap.id,
        "latest_scrappy_snapshot_ts": snap.snapshot_ts.isoformat() if snap.snapshot_ts else None,
        "scrappy_catalyst_direction": snap.catalyst_direction,
        "scrappy_catalyst_strength": catalyst_strength,
        "scrappy_stale_flag": bool(snap.stale_flag) if snap.stale_flag is not None else None,
        "scrappy_conflict_flag": bool(snap.conflict_flag) if snap.conflict_flag is not None else None,
        "scrappy_evidence_count": snap.evidence_count,
        "scrappy_source_count": snap.source_count,
        "scrappy_headline_count": headline_count,
        "coverage_status": coverage.status,
        "coverage_reason": coverage.reason,
    }


async def _get_latest_snapshots_for_symbols(session, symbols: list[str]) -> dict[str, SymbolIntelligenceSnapshot]:
    """Return dict symbol -> latest snapshot row for each symbol (for Scrappy enrichment)."""
    if not symbols:
        return {}
    seen: set[str] = set()
    result: dict[str, SymbolIntelligenceSnapshot] = {}
    r = await session.execute(
        select(SymbolIntelligenceSnapshot)
        .where(SymbolIntelligenceSnapshot.symbol.in_(symbols))
        .order_by(SymbolIntelligenceSnapshot.snapshot_ts.desc())
    )
    for row in r.scalars().all():
        sym = (row.symbol or "").strip()
        if sym and sym not in seen:
            seen.add(sym)
            result[sym] = row
    return result


def _sanitize_json_value(value: Any) -> Any:
    """Sanitize value for JSON serialization: convert NaN/Infinity to None, ensure all values are JSON-serializable."""
    import math
    from datetime import datetime
    if value is None:
        return None
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, (int, str, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_sanitize_json_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _sanitize_json_value(v) for k, v in value.items()}
    # For other types, convert to string as fallback
    try:
        return str(value)
    except Exception:
        return None


def _referee_assessment_to_dict(a: AiRefereeAssessment | None) -> dict | None:
    if not a:
        return None
    return {
        "id": a.id,
        "assessment_id": a.assessment_id,
        "assessment_ts": a.assessment_ts.isoformat() if a.assessment_ts else None,
        "symbol": a.symbol,
        "strategy_id": a.strategy_id,
        "strategy_version": a.strategy_version,
        "model_name": a.model_name,
        "referee_version": a.referee_version,
        "setup_quality_score": a.setup_quality_score,
        "catalyst_strength": a.catalyst_strength,
        "regime_label": a.regime_label,
        "evidence_sufficiency": a.evidence_sufficiency,
        "contradiction_flag": a.contradiction_flag,
        "stale_flag": a.stale_flag,
        "decision_class": a.decision_class,
        "reason_codes": a.reason_codes_json or [],
        "plain_english_rationale": a.plain_english_rationale,
    }


@app.get("/v1/signals/{signal_uuid}")
async def get_signal(signal_uuid: UUID) -> dict:
    """Single signal by UUID; includes linked intelligence snapshot and AI referee assessment if present."""
    factory = get_session_factory()
    async with factory() as session:
        store = LedgerStore(session)
        s = await store.get_signal_by_uuid(signal_uuid)
        snapshot = None
        referee = None
        if s:
            if getattr(s, "intelligence_snapshot_id", None):
                from sqlalchemy import select
                r = await session.execute(
                    select(SymbolIntelligenceSnapshot).where(
                        SymbolIntelligenceSnapshot.id == s.intelligence_snapshot_id
                    ).limit(1)
                )
                snapshot = r.scalars().first()
            if getattr(s, "ai_referee_assessment_id", None):
                referee = await get_assessment_row_by_pk(session, s.ai_referee_assessment_id)
            # Look up lifecycle by signal_uuid
            lifecycle_result = await session.execute(
                select(PaperLifecycle).where(PaperLifecycle.signal_uuid == signal_uuid).limit(1)
            )
            lifecycle = lifecycle_result.scalars().first()
    if not s:
        raise HTTPException(status_code=404, detail="not_found")
    reason_codes = s.reason_codes or []
    scrappy_reason_codes = [rc for rc in reason_codes if isinstance(rc, str) and ("scrappy_" in rc.lower() or rc.lower().startswith("scrappy"))]
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
        "reason_codes": reason_codes,
        "scrappy_reason_codes": scrappy_reason_codes,
        "feature_snapshot_json": s.feature_snapshot_json,
        "quote_snapshot_json": s.quote_snapshot_json,
        "news_snapshot_json": s.news_snapshot_json,
        "intelligence_snapshot_id": getattr(s, "intelligence_snapshot_id", None),
        "scrappy_mode": getattr(s, "scrappy_mode", None),
        "ai_referee_assessment_id": getattr(s, "ai_referee_assessment_id", None),
        "paper_order_id": getattr(s, "paper_order_id", None),
        "execution_mode": getattr(s, "execution_mode", None),
    }
    if snapshot:
        out["intelligence_snapshot"] = _snapshot_to_dict(snapshot)
    if referee:
        out["ai_referee_assessment"] = _referee_assessment_to_dict(referee)
    if lifecycle:
        out["lifecycle"] = {
            "lifecycle_status": lifecycle.lifecycle_status,
            "entry_order_id": lifecycle.entry_order_id,
            "exit_order_id": lifecycle.exit_order_id,
            "stop_price": float(lifecycle.stop_price) if lifecycle.stop_price else None,
            "target_price": float(lifecycle.target_price) if lifecycle.target_price else None,
            "force_flat_time": lifecycle.force_flat_time,
            "protection_mode": lifecycle.protection_mode,
            "protection_active": lifecycle.exit_order_id is not None,
            "managed_status": "exited" if lifecycle.lifecycle_status in ("exited", "exit_submitted") else
                             "managed" if lifecycle.lifecycle_status in ("entry_filled", "exit_pending") else
                             "pending" if lifecycle.lifecycle_status == "entry_submitted" else
                             "orphaned" if lifecycle.lifecycle_status == "orphaned" else
                             "blocked" if lifecycle.lifecycle_status == "blocked" else "unknown",
            "universe_source": lifecycle.universe_source,
            "static_fallback_at_entry": lifecycle.universe_source == "static",
        }
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
    """Summary: snapshot count, per-symbol latest, stale/conflict/fresh counts for operator visibility."""
    factory = get_session_factory()
    async with factory() as session:
        total = (await session.execute(select(func.count(SymbolIntelligenceSnapshot.id)))).scalar() or 0
        rows = await get_recent_snapshots(session, limit=500)
    by_symbol: dict[str, dict] = {}
    stale_count = conflict_count = fresh_count = 0
    for r in rows:
        if r.symbol not in by_symbol:
            by_symbol[r.symbol] = _snapshot_to_dict(r) or {}
        if getattr(r, "stale_flag", False):
            stale_count += 1
        elif getattr(r, "conflict_flag", False):
            conflict_count += 1
        else:
            fresh_count += 1
    return {
        "snapshots_total": total,
        "symbols_with_snapshot": len(by_symbol),
        "by_symbol": by_symbol,
        "stale_count": stale_count,
        "conflict_count": conflict_count,
        "fresh_count": fresh_count,
    }


@app.get("/v1/shadow/trades")
async def list_shadow_trades(
    limit: int = Query(default=50, ge=1, le=200),
    scrappy_mode: str | None = Query(None, description="Filter by scrappy_mode (advisory, required, off)"),
    strategy_id: str | None = Query(None, description="Filter by strategy_id (e.g., OPEN_DRIVE_MOMO, INTRADAY_CONTINUATION)"),
) -> dict:
    """Recent shadow trades (ideal + realistic), optionally filtered by scrappy_mode or strategy_id."""
    factory = get_session_factory()
    async with factory() as session:
        store = LedgerStore(session)
        trades = await store.list_shadow_trades(limit=limit, scrappy_mode=scrappy_mode, strategy_id=strategy_id)
        # Fetch strategy info for each trade by joining with Signal
        signal_uuids = [t.signal_uuid for t in trades]
        strategy_map: dict[UUID, tuple[str | None, str | None]] = {}
        if signal_uuids:
            sig_result = await session.execute(
                select(Signal.signal_uuid, Signal.strategy_id, Signal.strategy_version)
                .where(Signal.signal_uuid.in_(signal_uuids))
            )
            for sig in sig_result.all():
                strategy_map[sig.signal_uuid] = (sig.strategy_id, sig.strategy_version)
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
                "scrappy_mode": getattr(t, "scrappy_mode", None),
                "strategy_id": strategy_map.get(t.signal_uuid, (None, None))[0],
                "strategy_version": strategy_map.get(t.signal_uuid, (None, None))[1],
            }
            for t in trades
        ],
        "count": len(trades),
        "scrappy_mode_filter": scrappy_mode,
        "strategy_id_filter": strategy_id,
    }


# ---------- Alpaca paper account (broker truth for UI) ----------

def _alpaca_client_or_503() -> AlpacaClient:
    """Return AlpacaClient or raise HTTPException 503 if not configured."""
    s = get_settings()
    if not s.alpaca_api_key_id or not s.alpaca_api_secret_key:
        raise HTTPException(status_code=503, detail="Alpaca not configured (ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY)")
    return AlpacaClient()


@app.get("/v1/account")
def get_paper_account() -> dict:
    """Paper account: status, equity, cash, buying power, tradable (full Alpaca response)."""
    client = _alpaca_client_or_503()
    try:
        return client.get_account()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Alpaca account: {str(e)[:200]}")


@app.get("/v1/account/status")
def get_account_status() -> dict:
    """Account protection and trading visibility: PDT, trading_blocked, buying power, equity. For operator UI per Alpaca playbook."""
    client = _alpaca_client_or_503()
    try:
        acc = client.get_account()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Alpaca account: {str(e)[:200]}")
    return {
        "trading_blocked": acc.get("trading_blocked"),
        "account_blocked": acc.get("account_blocked"),
        "pattern_day_trader": acc.get("pattern_day_trader"),
        "daytrading_buying_power": acc.get("daytrading_buying_power"),
        "buying_power": acc.get("buying_power"),
        "equity": acc.get("equity"),
        "cash": acc.get("cash"),
        "status": acc.get("status"),
        "multiplier": acc.get("multiplier"),
    }


@app.get("/v1/positions")
def list_paper_positions() -> dict:
    """Paper open positions with P&L data from Alpaca."""
    client = _alpaca_client_or_503()
    try:
        positions = client.list_positions()
        # Ensure all position data including P&L is included
        enriched_positions = []
        for p in positions:
            enriched = dict(p)  # Copy all Alpaca fields
            # Ensure numeric P&L fields are properly typed
            if "unrealized_pl" in enriched:
                try:
                    enriched["unrealized_pl"] = float(enriched["unrealized_pl"])
                except (TypeError, ValueError):
                    pass
            if "unrealized_plpc" in enriched:
                try:
                    enriched["unrealized_plpc"] = float(enriched["unrealized_plpc"])
                except (TypeError, ValueError):
                    pass
            if "market_value" in enriched:
                try:
                    enriched["market_value"] = float(enriched["market_value"])
                except (TypeError, ValueError):
                    pass
            enriched_positions.append(enriched)
        return {"positions": enriched_positions, "count": len(enriched_positions)}
    except Exception as e:
        error_msg = str(e)
        if "unauthorized" in error_msg.lower() or "401" in error_msg or "403" in error_msg:
            raise HTTPException(
                status_code=503,
                detail=f"Alpaca authentication failed: {error_msg[:200]}. Check ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY."
            )
        raise HTTPException(status_code=503, detail=f"Alpaca positions: {error_msg[:200]}")


@app.get("/v1/positions/{symbol_or_asset_id}")
def get_paper_position(symbol_or_asset_id: str) -> dict:
    """Single paper position by symbol or asset ID."""
    client = _alpaca_client_or_503()
    try:
        pos = client.get_position(symbol_or_asset_id)
        if pos is None:
            raise HTTPException(status_code=404, detail="Position not found")
        return pos
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Alpaca position: {str(e)[:200]}")


@app.get("/v1/orders")
async def list_paper_orders(
    status: str | None = Query(None, description="open, closed, all"),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    """Paper orders from Alpaca, enriched with order_origin and order_intent from DB when present."""
    import asyncio
    client = _alpaca_client_or_503()
    try:
        orders = await asyncio.to_thread(
            client.list_orders,
            status=status or "all",
            limit=limit,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Alpaca orders: {str(e)[:200]}")
    order_ids = [str(o.get("id")) for o in orders if o.get("id")]
    origin_map: dict[str, tuple[str | None, str | None]] = {}
    if order_ids:
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(PaperOrder.order_id, PaperOrder.order_origin, PaperOrder.order_intent).where(
                    PaperOrder.order_id.in_(order_ids)
                )
            )
            for row in result.all():
                origin_map[str(row.order_id)] = (row.order_origin, row.order_intent)
    for o in orders:
        oid = str(o.get("id")) if o.get("id") else None
        if oid and oid in origin_map:
            origin, intent = origin_map[oid]
            o["order_origin"] = origin
            o["order_intent"] = intent
            o["order_source"] = (
                "strategy_paper" if origin == "strategy" else
                "operator_test" if origin == "operator_test" else
                "legacy_unknown"
            )
        else:
            o["order_origin"] = None
            o["order_intent"] = None
            o["order_source"] = "legacy_unknown"
    return {"orders": orders, "count": len(orders)}


@app.get("/v1/orders/{order_id}")
def get_paper_order(order_id: str) -> dict:
    """Single paper order by ID."""
    client = _alpaca_client_or_503()
    try:
        order = client.get_order(order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        return order
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Alpaca order: {str(e)[:200]}")


def _order_origin_to_source(origin: str | None) -> str:
    """Canonical order_source: strategy_paper | operator_test | legacy_unknown."""
    if origin == "strategy":
        return "strategy_paper"
    if origin == "operator_test":
        return "operator_test"
    return "legacy_unknown"


@app.get("/v1/paper/exposure")
async def paper_exposure() -> dict:
    """Current paper exposure: for each position, symbol, source, provenance, exit plan status, orphaned.
    Truthful; no fake values. Use to diagnose what caused a position and whether it is managed."""
    import asyncio
    client = _alpaca_client_or_503()
    try:
        positions = await asyncio.to_thread(client.list_positions)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Alpaca positions: {str(e)[:200]}")
    exposure: list[dict] = []
    factory = get_session_factory()
    async with factory() as session:
        for p in positions or []:
            symbol = p.get("symbol") or ""
            qty_val = p.get("qty") or 0
            try:
                qty_float = float(qty_val)
            except (TypeError, ValueError):
                qty_float = 0.0
            side = "long" if qty_float >= 0 else "short"
            entry_ts = p.get("opened_at") or p.get("created_at")
            # Find best-matching PaperOrder for this symbol/side (filled orders that opened position)
            result = await session.execute(
                select(PaperOrder)
                .where(PaperOrder.symbol == symbol)
                .where(PaperOrder.side == ("buy" if qty_float >= 0 else "sell"))
                .order_by(PaperOrder.submitted_at.desc().nullslast())
                .limit(5)
            )
            rows = result.scalars().all()
            order_source = "legacy_unknown"
            order_origin = None
            order_intent = None
            signal_uuid = None
            strategy_id = None
            strategy_version = None
            scrappy_at_entry = None
            ai_referee_at_entry = None
            sizing_at_entry = None
            scrappy_detail = None
            ai_referee_detail = None
            lifecycle = None
            # Try to find lifecycle by entry_order_id first, then by signal_uuid
            if rows:
                row = rows[0]
                order_origin = row.order_origin
                order_intent = row.order_intent
                order_source = _order_origin_to_source(row.order_origin)
                signal_uuid = str(row.signal_uuid) if row.signal_uuid else None
                # Look up lifecycle by entry_order_id
                if row.order_id:
                    lifecycle_result = await session.execute(
                        select(PaperLifecycle).where(PaperLifecycle.entry_order_id == row.order_id).limit(1)
                    )
                    lifecycle = lifecycle_result.scalars().first()
                # If not found, try by signal_uuid
                if not lifecycle and row.signal_uuid:
                    lifecycle_result = await session.execute(
                        select(PaperLifecycle).where(PaperLifecycle.signal_uuid == row.signal_uuid).limit(1)
                    )
                    lifecycle = lifecycle_result.scalars().first()
                # Fallback to signal lookup if no lifecycle
                if row.signal_uuid and not lifecycle:
                    sig_result = await session.execute(
                        select(Signal).where(Signal.signal_uuid == row.signal_uuid).limit(1)
                    )
                    sig = sig_result.scalars().first()
                    if sig:
                        strategy_id = getattr(sig, "strategy_id", None)
                        strategy_version = getattr(sig, "strategy_version", None)
                        scrappy_at_entry = getattr(sig, "scrappy_mode", None)
                        ai_referee_at_entry = "ran" if getattr(sig, "ai_referee_assessment_id", None) else "not_run"
                        if getattr(sig, "intelligence_snapshot_id", None):
                            snap = await session.get(SymbolIntelligenceSnapshot, sig.intelligence_snapshot_id)
                            if snap:
                                headline_count = len(snap.headline_set_json) if isinstance(getattr(snap, "headline_set_json", None), list) else 0
                                scrappy_detail = {
                                    "snapshot_id": snap.id,
                                    "freshness_minutes": getattr(snap, "freshness_minutes", None),
                                    "catalyst_direction": getattr(snap, "catalyst_direction", None),
                                    "evidence_count": getattr(snap, "evidence_count", None),
                                    "headline_count": headline_count,
                                    "stale_flag": getattr(snap, "stale_flag", None),
                                    "conflict_flag": getattr(snap, "conflict_flag", None),
                                }
                        if getattr(sig, "ai_referee_assessment_id", None):
                            ref = await session.get(AiRefereeAssessment, sig.ai_referee_assessment_id)
                            if ref:
                                ai_referee_detail = {
                                    "ran": True,
                                    "model_name": getattr(ref, "model_name", None),
                                    "referee_version": getattr(ref, "referee_version", None),
                                    "decision_class": getattr(ref, "decision_class", None),
                                    "setup_quality_score": getattr(ref, "setup_quality_score", None),
                                    "contradiction_flag": getattr(ref, "contradiction_flag", None),
                                    "stale_flag": getattr(ref, "stale_flag", None),
                                    "evidence_sufficiency": getattr(ref, "evidence_sufficiency", None),
                                    "plain_english_rationale": (getattr(ref, "plain_english_rationale", None) or "")[:500],
                                }
            # Use lifecycle data if available
            if lifecycle:
                signal_uuid = str(lifecycle.signal_uuid)
                strategy_id = lifecycle.strategy_id
                strategy_version = lifecycle.strategy_version
                order_source = "strategy_paper"
                order_origin = "strategy"
                # Get intelligence details from lifecycle
                if lifecycle.intelligence_snapshot_id:
                    snap = await session.get(SymbolIntelligenceSnapshot, lifecycle.intelligence_snapshot_id)
                    if snap:
                        headline_count = len(snap.headline_set_json) if isinstance(getattr(snap, "headline_set_json", None), list) else 0
                        scrappy_detail = {
                            "snapshot_id": snap.id,
                            "freshness_minutes": getattr(snap, "freshness_minutes", None),
                            "catalyst_direction": getattr(snap, "catalyst_direction", None),
                            "evidence_count": getattr(snap, "evidence_count", None),
                            "headline_count": headline_count,
                            "stale_flag": getattr(snap, "stale_flag", None),
                            "conflict_flag": getattr(snap, "conflict_flag", None),
                        }
                if lifecycle.ai_referee_assessment_id:
                    ref = await session.get(AiRefereeAssessment, lifecycle.ai_referee_assessment_id)
                    if ref:
                        ai_referee_detail = {
                            "ran": True,
                            "model_name": getattr(ref, "model_name", None),
                            "referee_version": getattr(ref, "referee_version", None),
                            "decision_class": getattr(ref, "decision_class", None),
                            "setup_quality_score": getattr(ref, "setup_quality_score", None),
                            "contradiction_flag": getattr(ref, "contradiction_flag", None),
                            "stale_flag": getattr(ref, "stale_flag", None),
                            "evidence_sufficiency": getattr(ref, "evidence_sufficiency", None),
                            "plain_english_rationale": (getattr(ref, "plain_english_rationale", None) or "")[:500],
                        }
                # Sizing details from lifecycle
                sizing_at_entry = {
                    "equity": float(lifecycle.sizing_equity) if lifecycle.sizing_equity else None,
                    "buying_power": float(lifecycle.sizing_buying_power) if lifecycle.sizing_buying_power else None,
                    "stop_distance": float(lifecycle.sizing_stop_distance) if lifecycle.sizing_stop_distance else None,
                    "risk_per_trade_pct": float(lifecycle.sizing_risk_per_trade_pct) if lifecycle.sizing_risk_per_trade_pct else None,
                    "max_position_pct": float(lifecycle.sizing_max_position_pct) if lifecycle.sizing_max_position_pct else None,
                    "max_gross_exposure_pct": float(lifecycle.sizing_max_gross_exposure_pct) if lifecycle.sizing_max_gross_exposure_pct else None,
                    "max_symbol_exposure_pct": float(lifecycle.sizing_max_symbol_exposure_pct) if lifecycle.sizing_max_symbol_exposure_pct else None,
                    "max_concurrent_positions": lifecycle.sizing_max_concurrent_positions,
                    "qty_proposed": float(lifecycle.sizing_qty_proposed) if lifecycle.sizing_qty_proposed else None,
                    "qty_approved": float(lifecycle.sizing_qty_approved),
                    "notional_approved": float(lifecycle.sizing_notional_approved) if lifecycle.sizing_notional_approved else None,
                    "rejection_reason": lifecycle.sizing_rejection_reason,
                }
            # Determine managed/orphaned status
            managed_status = "unmanaged"
            if lifecycle:
                if lifecycle.lifecycle_status in ("exited", "exit_submitted"):
                    managed_status = "exited"
                elif lifecycle.lifecycle_status in ("entry_filled", "exit_pending") and lifecycle.exit_order_id:
                    managed_status = "managed"
                elif lifecycle.lifecycle_status in ("entry_filled", "exit_pending"):
                    managed_status = "managed"  # Has exit plan, waiting for exit
                elif lifecycle.lifecycle_status == "entry_submitted":
                    managed_status = "pending"
                elif lifecycle.lifecycle_status == "orphaned":
                    managed_status = "orphaned"
                elif lifecycle.lifecycle_status == "blocked":
                    managed_status = "blocked"
            elif order_source == "legacy_unknown":
                managed_status = "orphaned"
            # Extract P&L data from Alpaca position
            # Alpaca returns these as strings, handle None, empty string, and numeric strings
            unrealized_pl = p.get("unrealized_pl")
            unrealized_plpc = p.get("unrealized_plpc")
            market_value = p.get("market_value")
            current_price = p.get("current_price")
            avg_entry_price = p.get("avg_entry_price")
            
            # Convert to float, handling None, empty strings, and already-numeric values
            def safe_float(val):
                if val is None:
                    return None
                if isinstance(val, (int, float)):
                    return float(val)
                if isinstance(val, str):
                    val = val.strip()
                    if val == "" or val.lower() == "none" or val.lower() == "null":
                        return None
                    try:
                        return float(val)
                    except (TypeError, ValueError):
                        return None
                return None
            
            unrealized_pl_float = safe_float(unrealized_pl)
            unrealized_plpc_float = safe_float(unrealized_plpc)
            market_value_float = safe_float(market_value)
            current_price_float = safe_float(current_price)
            avg_entry_price_float = safe_float(avg_entry_price)
            exposure.append({
                "symbol": symbol,
                "side": side,
                "qty": qty_float,
                "entry_ts": entry_ts,
                "source": order_source,
                "order_origin": order_origin,
                "operator_intent": order_intent if order_source == "operator_test" else None,
                "strategy_id": strategy_id,
                "strategy_version": strategy_version,
                "signal_uuid": signal_uuid,
                "entry_order_id": lifecycle.entry_order_id if lifecycle else None,
                "exit_order_id": lifecycle.exit_order_id if lifecycle else None,
                "scrappy_at_entry": scrappy_at_entry,
                "scrappy_detail": scrappy_detail,
                "ai_referee_at_entry": ai_referee_at_entry,
                "ai_referee_detail": ai_referee_detail,
                "sizing_at_entry": sizing_at_entry,
                "exit_plan_status": lifecycle.lifecycle_status if lifecycle else "not_persisted",
                "stop_price": float(lifecycle.stop_price) if lifecycle else None,
                "target_price": float(lifecycle.target_price) if lifecycle else None,
                "force_flat_time": lifecycle.force_flat_time if lifecycle else None,
                "protection_mode": lifecycle.protection_mode if lifecycle else None,
                "protection_active": lifecycle.exit_order_id is not None if lifecycle else False,
                "broker_protection": lifecycle.protection_mode if lifecycle else "unknown",
                "managed_status": managed_status,
                "orphaned": managed_status == "orphaned",
                "universe_source": lifecycle.universe_source if lifecycle else None,
                "static_fallback_at_entry": lifecycle.universe_source == "static" if lifecycle else None,
                "lifecycle_status": lifecycle.lifecycle_status if lifecycle else None,
                "exit_reason": lifecycle.exit_reason if lifecycle else None,
                "exit_ts": lifecycle.exit_ts.isoformat() if lifecycle and lifecycle.exit_ts else None,
                "last_error": lifecycle.last_error if lifecycle else None,
                "unrealized_pl": unrealized_pl_float,
                "unrealized_plpc": unrealized_plpc_float,
                "market_value": market_value_float,
                "current_price": current_price_float,
                "avg_entry_price": avg_entry_price_float,
                "holding_period_type": getattr(lifecycle, "holding_period_type", "intraday") if lifecycle else "intraday",
                "max_hold_days": getattr(lifecycle, "max_hold_days", 0) if lifecycle else 0,
                "entry_date": getattr(lifecycle, "entry_date", None) if lifecycle else None,
                "scheduled_exit_date": getattr(lifecycle, "scheduled_exit_date", None) if lifecycle else None,
                "days_held": getattr(lifecycle, "days_held", 0) if lifecycle else 0,
                "overnight_carry": getattr(lifecycle, "overnight_carry", False) if lifecycle else False,
                "overnight_carry_count": getattr(lifecycle, "overnight_carry_count", 0) if lifecycle else 0,
            })
    return {"positions": exposure, "count": len(exposure)}


async def _paper_effective_armed() -> tuple[bool, str]:
    """Effective paper armed = config permits AND Redis says armed. Returns (armed, reason)."""
    s = get_settings()
    if not getattr(s, "paper_trading_armed", False):
        return (False, "disarmed_by_default")
    try:
        r = redis.from_url(s.redis_url, decode_responses=True)
        val = await r.get(PAPER_ARMED_REDIS_KEY)
        await r.aclose()
        if val == "1":
            return (True, "armed")
        return (False, "disarmed_via_api")
    except Exception as e:
        return (False, f"disarmed_redis_error:{str(e)[:50]}")


@app.get("/v1/paper/arming-prerequisites")
async def paper_arming_prerequisites() -> dict:
    """Checks that must pass before paper can be armed. Used to refuse arm unless all satisfied."""
    s = get_settings()
    checks: dict[str, dict] = {}
    blockers: list[str] = []

    # Paper execution enabled
    pe = getattr(s, "paper_execution_enabled", False)
    checks["paper_execution_enabled"] = {"ok": pe, "detail": "enabled" if pe else "disabled"}
    if not pe:
        blockers.append("paper_execution_disabled")

    # Credentials configured
    creds = bool(s.alpaca_api_key_id and s.alpaca_api_secret_key)
    checks["credentials_configured"] = {"ok": creds, "detail": "configured" if creds else "missing"}
    if not creds:
        blockers.append("credentials_missing")

    # Broker reachable
    broker_ok = False
    try:
        client = AlpacaClient()
        import asyncio as _aio
        _ = await _aio.to_thread(client.get_account)
        broker_ok = True
    except Exception as e:
        checks["broker_reachable"] = {"ok": False, "detail": str(e)[:80]}
        blockers.append("broker_unreachable")
    if broker_ok:
        checks["broker_reachable"] = {"ok": True, "detail": "ok"}

    # DB reachable
    db_ok = False
    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        checks["database_reachable"] = {"ok": False, "detail": str(e)[:80]}
        blockers.append("database_unreachable")
    if db_ok:
        checks["database_reachable"] = {"ok": True, "detail": "ok"}

    # Redis reachable
    redis_ok = False
    try:
        r = redis.from_url(s.redis_url, decode_responses=True)
        await r.ping()
        gateway_source = await r.get(GATEWAY_SYMBOL_SOURCE_KEY)
        worker_source = await r.get(WORKER_UNIVERSE_SOURCE_KEY)
        worker_ts = await r.get(WORKER_HEARTBEAT_KEY)
        gateway_ts = await r.get(GATEWAY_MARKET_HEARTBEAT_KEY)
        await r.aclose()
        redis_ok = True
        checks["redis_reachable"] = {"ok": True, "detail": "ok"}
        checks["worker_heartbeat"] = {"ok": bool(worker_ts), "detail": "present" if worker_ts else "absent"}
        if not worker_ts:
            blockers.append("worker_heartbeat_absent")
        checks["gateway_heartbeat"] = {"ok": bool(gateway_ts), "detail": "present" if gateway_ts else "absent"}
        if not gateway_ts:
            blockers.append("gateway_heartbeat_absent")
        checks["dynamic_universe_gateway"] = {"ok": gateway_source == "dynamic", "detail": gateway_source or "unknown"}
        if gateway_source == "static":
            blockers.append("gateway_on_static_fallback")
        checks["dynamic_universe_worker"] = {"ok": worker_source in ("dynamic", "hybrid"), "detail": worker_source or "unknown"}
        if worker_source == "static":
            blockers.append("worker_on_static_fallback")
    except Exception as e:
        checks["redis_reachable"] = {"ok": False, "detail": str(e)[:80]}
        blockers.append("redis_unreachable")

    # Exit protection: we can submit close orders via Alpaca (minimal check)
    checks["exit_protection_available"] = {"ok": broker_ok, "detail": "broker_can_submit_orders" if broker_ok else "broker_unreachable"}
    if not broker_ok and "exit_protection_available" not in [b.split("_")[0] for b in blockers]:
        pass  # already have broker_unreachable

    satisfied = len(blockers) == 0
    return {"satisfied": satisfied, "blockers": blockers, "checks": checks}


@app.post("/v1/paper/arm")
async def paper_arm() -> dict:
    """Arm paper trading only if config permits and all arming prerequisites are satisfied."""
    s = get_settings()
    if not getattr(s, "paper_trading_armed", False):
        raise HTTPException(
            status_code=400,
            detail="Config PAPER_TRADING_ARMED is false; enable it to allow arming via API.",
        )
    pre = await paper_arming_prerequisites()
    if not pre["satisfied"]:
        raise HTTPException(status_code=400, detail={"reason": "prerequisites_not_satisfied", "blockers": pre["blockers"]})
    try:
        r = redis.from_url(s.redis_url, decode_responses=True)
        await r.set(PAPER_ARMED_REDIS_KEY, "1")
        await r.aclose()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Redis set failed: {str(e)[:100]}")
    return {"armed": True, "message": "Paper trading armed. Call POST /v1/paper/disarm to disarm immediately."}


@app.post("/v1/paper/disarm")
async def paper_disarm() -> dict:
    """Disarm paper trading immediately. No prerequisites required."""
    s = get_settings()
    try:
        r = redis.from_url(s.redis_url, decode_responses=True)
        await r.set(PAPER_ARMED_REDIS_KEY, "0")
        await r.aclose()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Redis set failed: {str(e)[:100]}")
    return {"armed": False, "message": "Paper trading disarmed. No paper orders will be submitted until re-armed."}


@app.get("/v1/clock")
def get_market_clock() -> dict:
    """Market clock: is_open, next_open, next_close."""
    client = _alpaca_client_or_503()
    try:
        return client.get_clock()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Alpaca clock: {str(e)[:200]}")


@app.get("/v1/calendar")
def get_calendar(
    start: str | None = Query(None, description="YYYY-MM-DD"),
    end: str | None = Query(None, description="YYYY-MM-DD"),
) -> dict:
    """Trading calendar."""
    client = _alpaca_client_or_503()
    try:
        days = client.get_calendar(start=start, end=end)
        return {"calendar": days, "count": len(days)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Alpaca calendar: {str(e)[:200]}")


@app.get("/v1/movers")
def get_movers(
    top: int = Query(default=10, ge=1, le=50, description="Number of top gainers and losers each"),
    market_type: str = Query(default="stocks", description="stocks or crypto"),
) -> dict:
    """Top market movers (gainers/losers) from Alpaca screener. One discovery input for scanner; resets at market open for stocks."""
    client = _alpaca_client_or_503()
    try:
        return client.get_movers(market_type=market_type, top=top)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Alpaca movers: {str(e)[:200]}")


@app.get("/v1/assets")
def list_assets(
    status: str = Query("active", description="active or inactive"),
    asset_class: str = Query("us_equity", description="us_equity etc"),
    tradable_only: bool = Query(True, description="if true, return only assets with tradable=true"),
    shortable_only: bool = Query(False, description="if true, return only shortable assets (playbook: check borrow daily)"),
    fractionable_only: bool = Query(False, description="if true, return only fractionable assets"),
) -> dict:
    """Asset master from Alpaca. Use daily for tradable/shortable/fractionable; playbook recommends checking borrow status for shorts."""
    client = _alpaca_client_or_503()
    try:
        assets = client.get_assets(status=status, asset_class=asset_class)
        if tradable_only:
            assets = [a for a in assets if a.get("tradable") is True]
        if shortable_only:
            assets = [a for a in assets if a.get("shortable") is True]
        if fractionable_only:
            assets = [a for a in assets if a.get("fractionable") is True]
        return {"assets": assets, "count": len(assets)}
    except Exception as e:
        error_msg = str(e)
        if "unauthorized" in error_msg.lower() or "401" in error_msg or "403" in error_msg or "APCA" in error_msg:
            raise HTTPException(
                status_code=503,
                detail=f"Alpaca authentication failed: {error_msg[:200]}. Verify ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY are correct and have proper permissions."
            )
        raise HTTPException(status_code=503, detail=f"Alpaca assets: {error_msg[:200]}")


@app.get("/v1/portfolio/history")
def get_portfolio_history(
    period: str | None = Query(None, description="1D, 1W, 1M, 1A"),
    timeframe: str | None = Query(None, description="1Min, 5Min, 15Min, 1H, 1D"),
    date_end: str | None = Query(None),
) -> dict:
    """Account equity and P/L time series."""
    client = _alpaca_client_or_503()
    try:
        return client.get_portfolio_history(period=period, timeframe=timeframe, date_end=date_end)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Alpaca portfolio history: {str(e)[:200]}")


@app.get("/v1/account/activities")
def list_activities(
    activity_types: str | None = Query(None),
    date: str | None = Query(None),
    page_size: int = Query(50, ge=1, le=100),
    page_token: str | None = Query(None),
) -> dict:
    """Account activities: fills, cash, fees, dividends, etc."""
    client = _alpaca_client_or_503()
    try:
        activities, next_token = client.get_activities(
            activity_types=activity_types, date=date, page_size=page_size, page_token=page_token
        )
        return {"activities": activities, "next_page_token": next_token, "count": len(activities)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Alpaca activities: {str(e)[:200]}")


@app.get("/v1/account/history")
async def get_account_history(
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    """Account snapshot history from reconciler (paper_account_snapshots)."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(PaperAccountSnapshot)
            .order_by(PaperAccountSnapshot.snapshot_ts.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
    return {
        "snapshots": [
            {
                "snapshot_ts": r.snapshot_ts.isoformat() if r.snapshot_ts else None,
                "equity": float(r.equity) if r.equity else None,
                "cash": float(r.cash) if r.cash else None,
                "buying_power": float(r.buying_power) if r.buying_power else None,
                "status": r.status,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@app.get("/v1/trades/paper")
async def list_paper_trades(
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    """Paper fills from canonical ledger (trade_updates)."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Fill).where(Fill.alpaca_order_id.isnot(None)).order_by(Fill.created_at.desc()).limit(limit)
        )
        fills = result.scalars().all()
    return {
        "trades": [
            {
                "signal_uuid": str(f.signal_uuid),
                "client_order_id": f.client_order_id,
                "alpaca_order_id": f.alpaca_order_id,
                "symbol": f.symbol,
                "side": f.side,
                "qty": float(f.qty) if f.qty else None,
                "avg_fill_price": float(f.avg_fill_price) if f.avg_fill_price else None,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in fills
        ],
        "count": len(fills),
    }


@app.get("/v1/portfolio/compare-books")
async def portfolio_compare_books() -> dict:
    """Paper vs shadow summary: honest counts and PnL; null if not available."""
    import asyncio
    factory = get_session_factory()
    async with factory() as session:
        shadow_count = (await session.execute(select(func.count(ShadowTrade.id)))).scalar() or 0
        shadow_pnl = float((await session.execute(select(func.sum(ShadowTrade.net_pnl)))).scalar() or 0)
        paper_count = (await session.execute(select(func.count(Fill.id)).where(Fill.alpaca_order_id.isnot(None)))).scalar() or 0
    
    # Calculate paper P&L: use account equity vs baseline (first snapshot) for total P&L
    # This includes both realized (from closed positions) and unrealized (from open positions)
    paper_pnl = None
    try:
        client = _alpaca_client_or_503()
        account = await asyncio.to_thread(client.get_account)
        current_equity = account.get("equity")
        if current_equity is not None:
            try:
                current_equity_float = float(current_equity)
                # Get baseline equity from first account snapshot (or use current if no history)
                async with factory() as session:
                    first_snapshot = await session.execute(
                        select(PaperAccountSnapshot)
                        .order_by(PaperAccountSnapshot.snapshot_ts.asc())
                        .limit(1)
                    )
                    first_row = first_snapshot.scalar_one_or_none()
                    if first_row and first_row.equity is not None:
                        baseline_equity = float(first_row.equity)
                        total_pnl = current_equity_float - baseline_equity
                        paper_pnl = round(total_pnl, 2) if abs(total_pnl) > 0.01 else None
                    else:
                        # No baseline yet, use unrealized P&L from positions as fallback
                        positions = await asyncio.to_thread(client.list_positions)
                        total_unrealized = 0.0
                        for p in positions or []:
                            unrealized_pl = p.get("unrealized_pl")
                            if unrealized_pl is not None:
                                try:
                                    total_unrealized += float(unrealized_pl)
                                except (TypeError, ValueError):
                                    pass
                        paper_pnl = round(total_unrealized, 2) if abs(total_unrealized) > 0.01 else None
            except (TypeError, ValueError):
                pass
    except Exception:
        # If broker unavailable, return None (truthful)
        pass
    
    return {
        "shadow": {"trade_count": shadow_count, "total_net_pnl": round(shadow_pnl, 2)},
        "paper": {"fill_count": paper_count, "total_net_pnl": paper_pnl},
        "note": "Paper PnL calculated from account equity vs baseline (first snapshot). Includes realized + unrealized.",
    }


# ---------- Paper execution test (operator/debug only) ----------


@app.get("/v1/paper/test/status")
async def paper_test_status() -> dict:
    """Operator status: paper enabled, account tradable, buying power, positions, recent test orders, warnings."""
    try:
        return await get_paper_test_status()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e)[:200])


@app.get("/v1/paper/test/proof")
async def paper_test_proof() -> dict:
    """Last operator-test order per intent (buy_open, sell_close, short_open, buy_cover) to prove all four flows ran."""
    factory = get_session_factory()
    intents = ("buy_open", "sell_close", "short_open", "buy_cover")
    out: dict[str, dict | None] = {i: None for i in intents}
    async with factory() as session:
        # Last row per order_intent where order_origin = operator_test
        result = await session.execute(
            select(PaperOrder)
            .where(
                PaperOrder.order_origin == "operator_test",
                PaperOrder.order_intent.in_(intents),
            )
            .order_by(PaperOrder.submitted_at.desc().nullslast(), PaperOrder.updated_at.desc().nullslast())
        )
        rows = result.scalars().all()
    # Keep only the most recent per intent
    for row in rows:
        if row.order_intent and row.order_intent in out and out[row.order_intent] is None:
            out[row.order_intent] = {
                "order_id": row.order_id,
                "client_order_id": row.client_order_id,
                "symbol": row.symbol,
                "side": row.side,
                "qty": float(row.qty) if row.qty else None,
                "status": row.status,
                "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "filled_qty": float(row.filled_qty) if row.filled_qty else None,
                "filled_avg_price": float(row.filled_avg_price) if row.filled_avg_price else None,
                "order_intent": row.order_intent,
            }
    return {"proof": out, "intents": intents}


@app.post("/v1/paper/test/buy-open")
async def paper_test_buy_open(
    symbol: str = Body(..., embed=True),
    qty: float = Body(..., embed=True),
    order_type: str = Body("market", embed=True),
    limit_price: float | None = Body(None, embed=True),
    extended_hours: bool = Body(False, embed=True),
    note: str | None = Body(None, embed=True),
) -> dict:
    """Operator test: BUY to open long. Not strategy authority."""
    armed, reason = await _paper_effective_armed()
    if not armed:
        raise HTTPException(status_code=403, detail={"reason": reason, "message": "Paper trading is not armed. Call POST /v1/paper/arm after prerequisites pass."})
    out = await run_buy_open(symbol=symbol, qty=qty, order_type=order_type, limit_price=limit_price, extended_hours=extended_hours, note=note)
    out["_operator_only"] = True
    return out


@app.post("/v1/paper/test/sell-close")
async def paper_test_sell_close(
    symbol: str = Body(..., embed=True),
    qty: float = Body(..., embed=True),
    order_type: str = Body("market", embed=True),
    limit_price: float | None = Body(None, embed=True),
    extended_hours: bool = Body(False, embed=True),
    note: str | None = Body(None, embed=True),
) -> dict:
    """Operator test: SELL to close long. Not strategy authority."""
    armed, reason = await _paper_effective_armed()
    if not armed:
        raise HTTPException(status_code=403, detail={"reason": reason, "message": "Paper trading is not armed. Call POST /v1/paper/arm after prerequisites pass."})
    out = await run_sell_close(symbol=symbol, qty=qty, order_type=order_type, limit_price=limit_price, extended_hours=extended_hours, note=note)
    out["_operator_only"] = True
    return out


@app.post("/v1/paper/test/short-open")
async def paper_test_short_open(
    symbol: str = Body(..., embed=True),
    qty: float = Body(..., embed=True),
    order_type: str = Body("market", embed=True),
    limit_price: float | None = Body(None, embed=True),
    extended_hours: bool = Body(False, embed=True),
    note: str | None = Body(None, embed=True),
) -> dict:
    """Operator test: SELL to open short. Not strategy authority."""
    armed, reason = await _paper_effective_armed()
    if not armed:
        raise HTTPException(status_code=403, detail={"reason": reason, "message": "Paper trading is not armed. Call POST /v1/paper/arm after prerequisites pass."})
    out = await run_short_open(symbol=symbol, qty=qty, order_type=order_type, limit_price=limit_price, extended_hours=extended_hours, note=note)
    out["_operator_only"] = True
    return out


@app.post("/v1/paper/test/buy-cover")
async def paper_test_buy_cover(
    symbol: str = Body(..., embed=True),
    qty: float = Body(..., embed=True),
    order_type: str = Body("market", embed=True),
    limit_price: float | None = Body(None, embed=True),
    extended_hours: bool = Body(False, embed=True),
    note: str | None = Body(None, embed=True),
) -> dict:
    """Operator test: BUY to cover short. Not strategy authority."""
    armed, reason = await _paper_effective_armed()
    if not armed:
        raise HTTPException(status_code=403, detail={"reason": reason, "message": "Paper trading is not armed. Call POST /v1/paper/arm after prerequisites pass."})
    out = await run_buy_cover(symbol=symbol, qty=qty, order_type=order_type, limit_price=limit_price, extended_hours=extended_hours, note=note)
    out["_operator_only"] = True
    return out


@app.post("/v1/paper/test/flatten-all")
async def paper_test_flatten_all(note: str | None = Body(None, embed=True)) -> dict:
    """Operator test: market close all positions. Not strategy authority."""
    armed, reason = await _paper_effective_armed()
    if not armed:
        raise HTTPException(status_code=403, detail={"reason": reason, "message": "Paper trading is not armed. Call POST /v1/paper/arm after prerequisites pass."})
    out = await run_flatten_all(note=note)
    out["_operator_only"] = True
    return out


@app.post("/v1/paper/test/cancel-all")
async def paper_test_cancel_all() -> dict:
    """Operator test: cancel all open orders."""
    out = await run_cancel_all()
    out["_operator_only"] = True
    return out


@app.get("/v1/metrics/summary")
async def metrics_summary(
    scrappy_mode: str | None = Query(None, description="Filter by scrappy_mode (advisory, required, off)"),
    strategy_id: str | None = Query(None, description="Filter by strategy_id (e.g., OPEN_DRIVE_MOMO, INTRADAY_CONTINUATION)"),
) -> dict:
    """Summary: signal count, shadow trade count, total net PnL, Scrappy attribution; optionally filtered by scrappy_mode or strategy_id."""
    factory = get_session_factory()
    async with factory() as session:
        q_sig = select(func.count(Signal.id))
        q_trade = select(func.count(ShadowTrade.id))
        q_pnl = select(func.sum(ShadowTrade.net_pnl))
        q_with_snap = select(func.count(Signal.id)).where(Signal.intelligence_snapshot_id.isnot(None))
        if scrappy_mode is not None:
            q_sig = q_sig.where(Signal.scrappy_mode == scrappy_mode)
            q_trade = q_trade.where(ShadowTrade.scrappy_mode == scrappy_mode)
            q_pnl = q_pnl.where(ShadowTrade.scrappy_mode == scrappy_mode)
            q_with_snap = q_with_snap.where(Signal.scrappy_mode == scrappy_mode)
        if strategy_id is not None:
            q_sig = q_sig.where(Signal.strategy_id == strategy_id)
            q_trade = q_trade.join(Signal, ShadowTrade.signal_uuid == Signal.signal_uuid).where(Signal.strategy_id == strategy_id)
            q_pnl = q_pnl.join(Signal, ShadowTrade.signal_uuid == Signal.signal_uuid).where(Signal.strategy_id == strategy_id)
            q_with_snap = q_with_snap.where(Signal.strategy_id == strategy_id)
        sig_count = (await session.execute(q_sig)).scalar() or 0
        trade_count = (await session.execute(q_trade)).scalar() or 0
        total_net_pnl = float((await session.execute(q_pnl)).scalar() or 0)
        with_snapshot = (await session.execute(q_with_snap)).scalar() or 0
        without_snapshot = sig_count - with_snapshot
        rejection_counts = await get_gate_rejection_counts(session, scrappy_mode=scrappy_mode)
    out = {
        "signals_total": sig_count,
        "shadow_trades_total": trade_count,
        "total_net_pnl_shadow": round(total_net_pnl, 2),
        "signals_with_scrappy_snapshot": with_snapshot,
        "signals_without_scrappy_snapshot": without_snapshot,
        "scrappy_gate_rejections": rejection_counts,
    }
    if scrappy_mode is not None:
        out["scrappy_mode_filter"] = scrappy_mode
    if strategy_id is not None:
        out["strategy_id_filter"] = strategy_id
    return out


@app.get("/v1/metrics/compare-scrappy-modes")
async def metrics_compare_scrappy_modes() -> dict:
    """Metrics segmented by scrappy_mode for staging comparison (advisory vs required)."""
    factory = get_session_factory()
    async with factory() as session:
        rejection_by_mode = await get_gate_rejection_counts_by_mode(session)
        # Per-mode signal count, shadow trade count, net PnL
        modes = ["advisory", "required", "off"]
        segments: dict[str, dict] = {}
        for mode in modes:
            q_sig = select(func.count(Signal.id)).where(Signal.scrappy_mode == mode)
            q_trade = select(func.count(ShadowTrade.id)).where(ShadowTrade.scrappy_mode == mode)
            q_pnl = select(func.sum(ShadowTrade.net_pnl)).where(ShadowTrade.scrappy_mode == mode)
            sig_count = (await session.execute(q_sig)).scalar() or 0
            trade_count = (await session.execute(q_trade)).scalar() or 0
            total_pnl = float((await session.execute(q_pnl)).scalar() or 0)
            segments[mode] = {
                "signals_total": sig_count,
                "shadow_trades_total": trade_count,
                "total_net_pnl_shadow": round(total_pnl, 2),
                "scrappy_gate_rejections": rejection_by_mode.get(mode, {}),
            }
        # Unknown/null mode
        q_sig_u = select(func.count(Signal.id)).where(Signal.scrappy_mode.is_(None))
        q_trade_u = select(func.count(ShadowTrade.id)).where(ShadowTrade.scrappy_mode.is_(None))
        q_pnl_u = select(func.sum(ShadowTrade.net_pnl)).where(ShadowTrade.scrappy_mode.is_(None))
        segments["unknown"] = {
            "signals_total": (await session.execute(q_sig_u)).scalar() or 0,
            "shadow_trades_total": (await session.execute(q_trade_u)).scalar() or 0,
            "total_net_pnl_shadow": round(float((await session.execute(q_pnl_u)).scalar() or 0), 2),
            "scrappy_gate_rejections": rejection_by_mode.get("unknown", {}),
        }
    return {
        "by_scrappy_mode": segments,
        "note": "Sample size may be too small for statistical comparison; run staging passes with same universe and time window.",
    }


@app.get("/v1/ai-referee/recent")
async def ai_referee_recent(
    symbol: str | None = Query(None, max_length=32),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Recent AI referee assessments, optionally by symbol."""
    try:
        factory = get_session_factory()
        async with factory() as session:
            rows = await list_recent_assessments(session, symbol=symbol, limit=limit)
        result = {
            "assessments": [_referee_assessment_to_dict(r) for r in rows],
            "count": len(rows),
            "symbol_filter": symbol,
        }
        return _sanitize_json_value(result)
    except Exception as e:
        logger.exception("Error in ai_referee_recent")
        return _sanitize_json_value({
            "error": "internal_error",
            "message": str(e)[:200],
            "assessments": [],
            "count": 0,
            "symbol_filter": symbol,
        })


@app.get("/v1/ai-referee/status")
async def ai_referee_status() -> dict:
    """AI Referee premarket service status: health, last run, enabled state."""
    from stockbot.config import get_settings
    from datetime import UTC, datetime, timedelta
    import redis.asyncio as redis
    import json
    settings = get_settings()
    ai_referee_enabled = getattr(settings, "ai_referee_enabled", False)
    
    # Get Redis state for last run
    last_run_ts = None
    last_symbols = []
    try:
        r = redis.from_url(settings.redis_url, decode_responses=True)
        last_run_ts = await r.get("stockbot:ai_referee_premarket:last_run_ts")
        symbols_json = await r.get("stockbot:ai_referee_premarket:last_symbols")
        await r.aclose()
        if symbols_json:
            try:
                last_symbols = json.loads(symbols_json)
            except Exception:
                pass
    except Exception:
        pass
    
    # Count recent assessments (last 4 hours)
    recent_assessments_count = 0
    try:
        from stockbot.ai_referee.store import list_recent_assessments
        factory = get_session_factory()
        async with factory() as session:
            recent = await list_recent_assessments(session, limit=100)
            cutoff = datetime.now(UTC) - timedelta(hours=4)
            recent_assessments_count = len([
                a for a in recent 
                if a.assessment_ts and a.assessment_ts.replace(tzinfo=UTC) > cutoff
            ])
    except Exception:
        pass
    
    # Determine service health
    service_health = "unknown"
    service_health_reason = None
    if not ai_referee_enabled:
        service_health = "disabled"
        service_health_reason = "ai_referee_enabled=false"
    elif last_run_ts:
        try:
            run_dt = datetime.fromisoformat(last_run_ts.replace("Z", "+00:00"))
            age_minutes = (datetime.now(UTC) - run_dt.replace(tzinfo=UTC)).total_seconds() / 60
            if age_minutes < 240:  # Recent run within 4 hours
                service_health = "healthy"
            else:
                service_health = "stale"
                service_health_reason = f"last_run_{int(age_minutes)}_minutes_ago"
        except Exception:
            pass
    else:
        service_health = "no_runs"
        service_health_reason = "no_runs_recorded"
    
    return {
        "ai_referee_enabled": ai_referee_enabled,
        "service_health": service_health,
        "service_health_reason": service_health_reason,
        "last_run_at": last_run_ts,
        "last_symbols_checked": last_symbols,
        "recent_assessments_count": recent_assessments_count,
    }


@app.get("/v1/ai-referee/{assessment_id}")
async def ai_referee_get(assessment_id: str) -> dict:
    """Single assessment by assessment_id (UUID string)."""
    factory = get_session_factory()
    async with factory() as session:
        a = await get_assessment_by_id(session, assessment_id)
    if not a:
        raise HTTPException(status_code=404, detail="not_found")
    out = _referee_assessment_to_dict(a) or {}
    if getattr(a, "raw_response_json", None):
        out["raw_response_json"] = a.raw_response_json
    return out


@app.get("/v1/metrics/compare-ai-referee")
async def metrics_compare_ai_referee() -> dict:
    """Metrics: signals/trades with vs without AI referee; decision_class counts."""
    factory = get_session_factory()
    async with factory() as session:
        decision_counts = await aggregate_decision_counts(session)
        assisted = await aggregate_assisted_vs_unassisted_metrics(session)
    return {
        "by_decision_class": decision_counts,
        "signals_with_referee": assisted.get("signals_with_referee", 0),
        "signals_without_referee": assisted.get("signals_without_referee", 0),
        "signals_total": assisted.get("signals_total", 0),
        "note": "Sample size may be too small for statistical comparison.",
    }


@app.get("/v1/metrics/compare-strategies")
async def metrics_compare_strategies() -> dict:
    """Metrics segmented by strategy_id: signals, trades, PnL, rejection reasons."""
    factory = get_session_factory()
    async with factory() as session:
        # Get all unique strategy_ids
        q_strategies = select(Signal.strategy_id).distinct()
        result_strategies = await session.execute(q_strategies)
        strategy_ids = [s for s in result_strategies.scalars().all() if s]
        
        segments: dict[str, dict] = {}
        for strategy_id in strategy_ids:
            # Signals count
            q_sig = select(func.count(Signal.id)).where(Signal.strategy_id == strategy_id)
            sig_count = (await session.execute(q_sig)).scalar() or 0
            
            # Shadow trades count and PnL (join with Signal to filter by strategy)
            q_trade = select(func.count(ShadowTrade.id)).join(Signal, ShadowTrade.signal_uuid == Signal.signal_uuid).where(Signal.strategy_id == strategy_id)
            q_pnl = select(func.sum(ShadowTrade.net_pnl)).join(Signal, ShadowTrade.signal_uuid == Signal.signal_uuid).where(Signal.strategy_id == strategy_id)
            trade_count = (await session.execute(q_trade)).scalar() or 0
            total_pnl = float((await session.execute(q_pnl)).scalar() or 0)
            
            # Get strategy version (most recent)
            q_version = select(Signal.strategy_version).where(Signal.strategy_id == strategy_id).order_by(Signal.created_at.desc()).limit(1)
            version_result = await session.execute(q_version)
            strategy_version = version_result.scalar() or "unknown"
            
            # Get rejection summary from Redis (strategy-specific keys)
            rejection_counts: dict[str, int] = {}
            try:
                import redis.asyncio as redis
                from stockbot.config import get_settings
                settings = get_settings()
                redis_client = redis.from_url(settings.redis_url, decode_responses=True)
                # Check for strategy-specific rejection keys
                pattern = f"stockbot:worker:rejection_summary:{strategy_id}:*"
                keys = await redis_client.keys(pattern)
                for key in keys:
                    # Extract reason code from key (format: stockbot:worker:rejection_summary:STRATEGY_ID:REASON)
                    parts = key.split(":")
                    if len(parts) >= 5:
                        reason = ":".join(parts[4:])  # Get everything after strategy_id
                        count = await redis_client.get(key)
                        if count:
                            rejection_counts[reason] = int(count)
                await redis_client.aclose()
            except Exception:
                pass
            
            segments[strategy_id] = {
                "strategy_version": strategy_version,
                "signals_total": sig_count,
                "shadow_trades_total": trade_count,
                "total_net_pnl_shadow": round(total_pnl, 2),
                "rejection_counts": rejection_counts,
            }
        
        # Unknown/null strategy
        q_sig_u = select(func.count(Signal.id)).where(Signal.strategy_id.is_(None))
        q_trade_u = select(func.count(ShadowTrade.id)).where(~ShadowTrade.signal_uuid.in_(select(Signal.signal_uuid).where(Signal.strategy_id.isnot(None))))
        q_pnl_u = select(func.sum(ShadowTrade.net_pnl)).where(~ShadowTrade.signal_uuid.in_(select(Signal.signal_uuid).where(Signal.strategy_id.isnot(None))))
        segments["unknown"] = {
            "strategy_version": None,
            "signals_total": (await session.execute(q_sig_u)).scalar() or 0,
            "shadow_trades_total": (await session.execute(q_trade_u)).scalar() or 0,
            "total_net_pnl_shadow": round(float((await session.execute(q_pnl_u)).scalar() or 0), 2),
            "rejection_counts": {},
        }
    
    return {
        "by_strategy": segments,
        "note": "Metrics are segmented by strategy_id. Shadow trades are linked via signal_uuid. Rejection counts from Redis (1-hour rolling window).",
    }


@app.get("/v1/system/health")
async def system_health() -> dict:
    """Alias for /health/detail: API, DB, Redis, worker, gateway status."""
    return await health_detail()


@app.get("/v1/system/reconciliation")
async def system_reconciliation() -> dict:
    """Latest reconciliation run: orders/positions matched vs mismatch."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(ReconciliationLog).order_by(ReconciliationLog.run_at.desc()).limit(1)
        )
        row = result.scalars().first()
    if not row:
        return {"status": "no_runs", "orders_matched": 0, "orders_mismatch": 0, "positions_matched": 0, "positions_mismatch": 0}
    return {
        "status": "ok",
        "run_at": row.run_at.isoformat() if row.run_at else None,
        "orders_matched": row.orders_matched,
        "orders_mismatch": row.orders_mismatch,
        "positions_matched": row.positions_matched,
        "positions_mismatch": row.positions_mismatch,
        "details": row.details,
    }


@app.post("/v1/scanner/run/now")
async def scanner_run_now() -> dict:
    """Manual trigger: run one live scanner cycle (and opportunity merge if enabled). Returns run_id and mode."""
    from stockbot.scanner.main import run_scan_and_publish, _get_watchlist_from_db
    try:
        result = await run_scan_and_publish(get_watchlist_fn=_get_watchlist_from_db)
        return {
            "status": "completed",
            "run_id": result.run_id,
            "mode": result.mode or "dynamic",
            "top_count": result.top_candidates_count,
        }
    except Exception as e:
        logger.exception("scanner run/now failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)[:200])


@app.post("/v1/opportunities/run/now")
async def opportunities_run_now() -> dict:
    """Manual trigger: re-blend from latest live scanner run (no new scan). Returns run_id and top_count."""
    from stockbot.opportunities.service import run_opportunity_merge_from_latest_scanner
    try:
        symbols = await run_opportunity_merge_from_latest_scanner()
        if symbols is not None:
            return {"status": "completed", "top_count": len(symbols), "run_id": "see latest opportunity run"}
        return {"status": "no_live_scanner_run", "reason": "no_live_scanner_run", "top_count": 0}
    except Exception as e:
        logger.exception("opportunities run/now failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)[:200])


@app.post("/v1/scrappy/auto-run/now")
async def scrappy_auto_run_now() -> dict:
    """Manual trigger: run one Scrappy auto cycle on live top symbols. Returns run_id if run executed."""
    from stockbot.scrappy.auto_runner import run_scrappy_auto_once
    try:
        result = await run_scrappy_auto_once()
        if result:
            return {"status": "completed", "run_id": result.get("run_id", "")[:16], "outcome": result.get("outcome_code", "")}
        return {"status": "skipped", "reason": "no_symbols_or_session"}
    except Exception as e:
        logger.exception("scrappy auto-run/now failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)[:200])


@app.post("/v1/ai-referee/premarket/now")
async def ai_referee_premarket_now() -> dict:
    """Manual trigger: run one AI Referee premarket assessment pass on focus symbols with fresh research."""
    from stockbot.ai_referee.premarket_runner import run_ai_referee_premarket_once
    try:
        result = await run_ai_referee_premarket_once()
        return result
    except Exception as e:
        logger.exception("ai_referee premarket/now failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)[:200])


@app.post("/v1/system/reconcile-now")
async def system_reconcile_now() -> dict:
    """Manual trigger: run one reconciliation cycle (Alpaca account/positions/orders). Operator/debug only."""
    import asyncio
    from stockbot.gateways.reconciler import run_reconciliation
    asyncio.create_task(run_reconciliation())
    return {"status": "accepted", "message": "reconciliation started in background"}


@app.post("/v1/backtests/run")
async def backtests_run(
    strategy_id: str = Query(default="INTRA_EVENT_MOMO"),
    strategy_version: str = Query(default="0.1.0"),
    symbols: str = Query(default="AAPL,SPY", description="Comma-separated"),
    start: str = Query(..., description="YYYY-MM-DD or ISO"),
    end: str | None = Query(None, description="YYYY-MM-DD or ISO"),
    feed: str = Query(default="iex"),
) -> dict:
    """Run historical backtest over Alpaca bars; returns run_id."""
    import asyncio
    from stockbot.research.backtest import run_backtest
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not sym_list:
        raise HTTPException(status_code=400, detail="symbols required")
    try:
        run_id = await asyncio.to_thread(
            run_backtest,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            symbols=sym_list,
            start=start,
            end=end,
            feed=feed,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:200])
    return {"run_id": run_id, "status": "completed"}


@app.get("/v1/backtests")
async def list_backtests(
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """List recent backtest runs."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(BacktestRun).order_by(BacktestRun.created_at.desc()).limit(limit)
        )
        rows = result.scalars().all()
    return {
        "runs": [
            {
                "run_id": r.run_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "strategy_id": r.strategy_id,
                "strategy_version": r.strategy_version,
                "start_ts": r.start_ts.isoformat() if r.start_ts else None,
                "end_ts": r.end_ts.isoformat() if r.end_ts else None,
                "status": r.status,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@app.get("/v1/backtests/{run_id}")
async def get_backtest(run_id: str) -> dict:
    """Single backtest run metadata."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(BacktestRun).where(BacktestRun.run_id == run_id).limit(1))
        r = result.scalars().first()
    if not r:
        raise HTTPException(status_code=404, detail="not_found")
    return {
        "run_id": r.run_id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "strategy_id": r.strategy_id,
        "strategy_version": r.strategy_version,
        "symbols_json": r.symbols_json,
        "start_ts": r.start_ts.isoformat() if r.start_ts else None,
        "end_ts": r.end_ts.isoformat() if r.end_ts else None,
        "feed": r.feed,
        "scrappy_mode": r.scrappy_mode,
        "ai_referee_mode": r.ai_referee_mode,
        "status": r.status,
        "notes": r.notes,
    }


@app.get("/v1/backtests/{run_id}/trades")
async def get_backtest_trades(run_id: str) -> dict:
    """Backtest trades for run."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(BacktestTrade).where(BacktestTrade.run_id == run_id).order_by(BacktestTrade.entry_ts))
        rows = result.scalars().all()
    return {
        "trades": [
            {
                "symbol": t.symbol,
                "side": t.side,
                "entry_ts": t.entry_ts.isoformat() if t.entry_ts else None,
                "exit_ts": t.exit_ts.isoformat() if t.exit_ts else None,
                "entry_price": float(t.entry_price) if t.entry_price else None,
                "exit_price": float(t.exit_price) if t.exit_price else None,
                "qty": float(t.qty) if t.qty else None,
                "gross_pnl": float(t.gross_pnl) if t.gross_pnl else None,
                "net_pnl": float(t.net_pnl) if t.net_pnl else None,
                "exit_reason": t.exit_reason,
            }
            for t in rows
        ],
        "count": len(rows),
    }


@app.get("/v1/backtests/{run_id}/summary")
async def get_backtest_summary(run_id: str) -> dict:
    """Backtest summary for run."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(BacktestSummary).where(BacktestSummary.run_id == run_id).limit(1))
        s = result.scalars().first()
    if not s:
        raise HTTPException(status_code=404, detail="not_found")
    return {
        "run_id": s.run_id,
        "signal_count": s.signal_count,
        "trade_count": s.trade_count,
        "win_rate": float(s.win_rate) if s.win_rate else None,
        "avg_return_per_trade": float(s.avg_return_per_trade) if s.avg_return_per_trade else None,
        "expectancy": float(s.expectancy) if s.expectancy else None,
        "gross_pnl": float(s.gross_pnl) if s.gross_pnl else None,
        "net_pnl": float(s.net_pnl) if s.net_pnl else None,
        "max_drawdown": float(s.max_drawdown) if s.max_drawdown else None,
        "regime_label": s.regime_label,
        "rejection_counts_json": s.rejection_counts_json,
    }


# ---------- Scanner / opportunities ----------


@app.get("/v1/scanner/runs")
async def list_scanner_runs(
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(None, description="Filter by status"),
) -> dict:
    """List recent scanner runs."""
    factory = get_session_factory()
    async with factory() as session:
        runs = await get_scanner_runs(session, limit=limit, status=status)
    return {
        "runs": [
            {
                "run_id": r.run_id,
                "run_ts": r.run_ts.isoformat() if r.run_ts else None,
                "mode": r.mode,
                "universe_mode": r.universe_mode,
                "universe_size": r.universe_size,
                "candidates_scored": r.candidates_scored,
                "top_candidates_count": r.top_candidates_count,
                "market_session": r.market_session,
                "status": r.status,
                "notes": r.notes,
            }
            for r in runs
        ],
        "count": len(runs),
    }


@app.get("/v1/scanner/runs/{run_id}")
async def get_scanner_run(run_id: str) -> dict:
    """Scanner run by ID."""
    factory = get_session_factory()
    async with factory() as session:
        r = await get_scanner_run_by_id(session, run_id)
    if not r:
        raise HTTPException(status_code=404, detail="not_found")
    return {
        "run_id": r.run_id,
        "run_ts": r.run_ts.isoformat() if r.run_ts else None,
        "mode": r.mode,
        "universe_mode": r.universe_mode,
        "universe_size": r.universe_size,
        "candidates_scored": r.candidates_scored,
        "top_candidates_count": r.top_candidates_count,
        "market_session": r.market_session,
        "status": r.status,
        "notes": r.notes,
    }


@app.get("/v1/scanner/candidates")
async def list_scanner_candidates(
    status: str | None = Query(None, description="top_candidate | filtered_out"),
    run_id: str | None = Query(None, description="Filter by run_id"),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    """Candidates for latest run or specified run_id."""
    factory = get_session_factory()
    async with factory() as session:
        if run_id:
            r = await get_scanner_run_by_id(session, run_id)
            if not r:
                raise HTTPException(status_code=404, detail="run not found")
            run_id_val = run_id
        else:
            latest = await get_scanner_runs(session, limit=1)
            if not latest:
                return {"candidates": [], "count": 0, "run_id": None}
            run_id_val = latest[0].run_id
        rows = await get_candidates_for_run(session, run_id_val, status=status, limit=limit)
    return {
        "candidates": [_row_to_candidate(r) for r in rows],
        "count": len(rows),
        "run_id": run_id_val,
    }


@app.get("/v1/scanner/top")
async def get_scanner_top() -> dict:
    """Latest live top-candidate list (symbols + run_id). Never returns historical (hist_*) runs."""
    factory = get_session_factory()
    async with factory() as session:
        snap = await get_latest_live_toplist_snapshot(session)
    if not snap:
        return {
            "symbols": [],
            "run_id": None,
            "snapshot_ts": None,
            "source": "none",
            "reason": "no_live_scanner_run",
        }
    return {
        "symbols": snap.symbols_json or [],
        "run_id": snap.run_id,
        "snapshot_ts": snap.snapshot_ts.isoformat() if snap.snapshot_ts else None,
    }


@app.get("/v1/scanner/symbol/{symbol}")
async def get_scanner_symbol(symbol: str) -> dict:
    """Latest candidate row for symbol (any run). Includes strategy eligibility."""
    factory = get_session_factory()
    async with factory() as session:
        r = await session.execute(
            select(ScannerCandidateRow)
            .where(ScannerCandidateRow.symbol == symbol.upper())
            .order_by(ScannerCandidateRow.created_at.desc())
            .limit(1)
        )
        row = r.scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    result = _row_to_candidate(row)
    
    # PHASE 5: Add strategy eligibility information
    try:
        market_data = {
            "price": float(row.price) if row.price else None,
            "gap_pct": row.gap_pct,
            "spread_bps": row.spread_bps,
        }
        strategy_eligibility = await _get_strategy_eligibility_for_symbol(
            symbol.upper(),
            market_data=market_data,
        )
        result["strategy_eligibility"] = strategy_eligibility
    except Exception as e:
        logger.debug("strategy_eligibility_check_failed symbol=%s error=%s", symbol, e)
        result["strategy_eligibility"] = {}
    
    return result


@app.get("/v1/scanner/summary")
async def get_scanner_summary() -> dict:
    """Scanner health: last live run, top count, rejection reasons. Excludes historical runs."""
    factory = get_session_factory()
    async with factory() as session:
        live_run = await get_latest_live_scanner_run(session)
        snap = await get_latest_live_toplist_snapshot(session)
        candidates = (
            await get_candidates_for_run(session, live_run.run_id, status="filtered_out", limit=200)
            if live_run else []
        )
    filter_reason_counts: dict[str, int] = {}
    for c in candidates:
        for reason in (c.filter_reasons_json or []):
            filter_reason_counts[reason] = filter_reason_counts.get(reason, 0) + 1
    return {
        "last_run_id": live_run.run_id if live_run else None,
        "last_run_ts": live_run.run_ts.isoformat() if live_run and live_run.run_ts else None,
        "last_run_status": live_run.status if live_run else None,
        "top_count": len(snap.symbols_json) if snap and snap.symbols_json else 0,
        "rejection_reasons": filter_reason_counts,
    }


@app.get("/v1/opportunities/now")
async def get_opportunities_now() -> dict:
    """Top current candidates (live only). Prefers opportunity engine; includes Scrappy enrichment when present."""
    try:
        from stockbot.opportunities.service import get_latest_opportunity_run_and_candidates
        from stockbot.scanner.store import get_latest_live_scanner_result
        from sqlalchemy import select
        from stockbot.db.models import ScannerCandidateRow
        run_id, updated_at, candidates = await get_latest_opportunity_run_and_candidates()
        if run_id and candidates:
            opportunities = []
            # PHASE 2 FIX: Check actual snapshots for ALL focus symbols, not just those with scrappy_present=True
            # This ensures UI shows real research coverage even when candidate row flag is stale
            all_symbols = [c["symbol"] for c in candidates if c.get("symbol")]
            snapshot_map: dict[str, SymbolIntelligenceSnapshot] = {}
            market_data_map: dict[str, dict] = {}  # symbol -> {price, gap_pct, spread_bps}
            factory = get_session_factory()
            async with factory() as session:
                # Look up snapshots for ALL symbols, not just those marked scrappy_present
                snapshot_map = await _get_latest_snapshots_for_symbols(session, all_symbols)
                # Fetch market data (price/gap/spread) from scanner run that matches opportunity run_id
                # Opportunity run_id is the same as the scanner run_id that created it
                symbol_list = [(c["symbol"] or "").strip().upper() for c in candidates if c.get("symbol")]
                if symbol_list and run_id:
                    r = await session.execute(
                        select(ScannerCandidateRow)
                        .where(ScannerCandidateRow.run_id == run_id)
                        .where(ScannerCandidateRow.symbol.in_(symbol_list))
                    )
                    scanner_rows = r.scalars().all()
                    for row in scanner_rows:
                        symbol_key = (row.symbol or "").strip().upper()
                        if symbol_key:
                            market_data_map[symbol_key] = {
                                "price": float(row.price) if row.price is not None else None,
                                "gap_pct": row.gap_pct,
                                "spread_bps": row.spread_bps,
                            }
                    # If no matches found with opportunity run_id, try latest scanner run as fallback
                    if not market_data_map:
                        scanner_result = await get_latest_live_scanner_result(session)
                        if scanner_result and scanner_result.run_id:
                            r2 = await session.execute(
                                select(ScannerCandidateRow)
                                .where(ScannerCandidateRow.run_id == scanner_result.run_id)
                                .where(ScannerCandidateRow.symbol.in_(symbol_list))
                            )
                            scanner_rows2 = r2.scalars().all()
                            for row in scanner_rows2:
                                symbol_key = (row.symbol or "").strip().upper()
                                if symbol_key and symbol_key not in market_data_map:
                                    market_data_map[symbol_key] = {
                                        "price": float(row.price) if row.price is not None else None,
                                        "gap_pct": row.gap_pct,
                                        "spread_bps": row.spread_bps,
                                    }
            for c in candidates:
                symbol_upper = (c["symbol"] or "").upper()
                market_data = market_data_map.get(symbol_upper, {})
                base = {
                    "symbol": c["symbol"],
                    "rank": c["rank"],
                    "total_score": c["total_score"],
                    "market_score": c.get("market_score"),
                    "semantic_score": c.get("semantic_score"),
                    "candidate_source": c.get("candidate_source"),
                    "inclusion_reasons": c.get("inclusion_reasons") or [],
                    "component_scores": {},
                    "reason_codes": c.get("inclusion_reasons") or [],
                    "price": market_data.get("price"),
                    "gap_pct": market_data.get("gap_pct"),
                    "spread_bps": market_data.get("spread_bps"),
                    "scrappy_present": c.get("scrappy_present", False),
                }
                # PHASE 2 FIX: Always check actual snapshot existence, update scrappy_present based on reality
                snap = snapshot_map.get(symbol_upper)
                if snap:
                    base.update(_snapshot_to_scrappy_enrichment(snap))
                    base["scrappy_present"] = True  # Override stale flag with actual snapshot existence
                else:
                    base["scrappy_present"] = False  # Ensure flag reflects reality
                
                # PHASE 5: Add strategy eligibility information
                try:
                    strategy_eligibility = await _get_strategy_eligibility_for_symbol(
                        symbol_upper,
                        market_data=market_data,
                    )
                    base["strategy_eligibility"] = strategy_eligibility
                except Exception as e:
                    logger.debug("strategy_eligibility_check_failed symbol=%s error=%s", symbol_upper, e)
                    base["strategy_eligibility"] = {}
                
                opportunities.append(_sanitize_json_value(base))
            result = {"opportunities": opportunities, "run_id": run_id, "updated_at": updated_at}
            return _sanitize_json_value(result)
        
        factory = get_session_factory()
        async with factory() as session:
            top_snap = await get_latest_live_toplist_snapshot(session)
            if not top_snap or not top_snap.run_id:
                return _sanitize_json_value({
                    "opportunities": [],
                    "run_id": None,
                    "updated_at": None,
                    "source": "none",
                    "reason": "no_live_scanner_run",
                })
            candidates = await get_candidates_for_run(
                session, top_snap.run_id, status="top_candidate", limit=50
            )
            # PHASE 2 FIX: Check actual snapshots for ALL symbols, not just those with scrappy_present=True
            all_symbols = [c.symbol for c in candidates if c.symbol]
            snapshot_map = await _get_latest_snapshots_for_symbols(session, all_symbols)
        opportunities = []
        for c in candidates:
            symbol_upper = (c.symbol or "").strip().upper()
            market_data = {
                "price": float(c.price) if c.price else None,
                "gap_pct": c.gap_pct,
                "spread_bps": c.spread_bps,
            }
            base = {
                "symbol": c.symbol,
                "rank": c.rank,
                "total_score": c.total_score,
                "market_score": None,
                "semantic_score": None,
                "candidate_source": "market",
                "component_scores": c.component_scores_json or {},
                "reason_codes": c.reason_codes_json or [],
                "inclusion_reasons": c.reason_codes_json or [],
                "price": market_data["price"],
                "gap_pct": market_data["gap_pct"],
                "spread_bps": market_data["spread_bps"],
                "scrappy_present": c.scrappy_present or False,
            }
            # PHASE 2 FIX: Always check actual snapshot existence, update scrappy_present based on reality
            snap = snapshot_map.get(symbol_upper)
            if snap:
                base.update(_snapshot_to_scrappy_enrichment(snap))
                base["scrappy_present"] = True  # Override stale flag with actual snapshot existence
            else:
                base["scrappy_present"] = False  # Ensure flag reflects reality
            
            # PHASE 5: Add strategy eligibility information
            try:
                strategy_eligibility = await _get_strategy_eligibility_for_symbol(
                    symbol_upper,
                    market_data=market_data,
                )
                base["strategy_eligibility"] = strategy_eligibility
            except Exception as e:
                logger.debug("strategy_eligibility_check_failed symbol=%s error=%s", symbol_upper, e)
                base["strategy_eligibility"] = {}
            
            opportunities.append(_sanitize_json_value(base))
        result = {
            "opportunities": opportunities,
            "run_id": top_snap.run_id,
            "updated_at": top_snap.snapshot_ts.isoformat() if top_snap.snapshot_ts else None,
        }
        return _sanitize_json_value(result)
    except Exception as e:
        logger.exception("Error in get_opportunities_now")
        return _sanitize_json_value({
            "error": "internal_error",
            "message": str(e)[:200],
            "opportunities": [],
            "run_id": None,
            "updated_at": None,
        })


async def _get_strategy_eligibility_for_symbol(
    symbol: str,
    market_data: dict | None = None,
) -> dict[str, dict]:
    """
    Check strategy eligibility for a symbol.
    Returns dict mapping strategy_id -> {eligible: bool, reason: str | None, entry_window: str, paper_enabled: bool}.
    """
    from datetime import UTC, datetime
    from stockbot.config import get_settings
    from stockbot.strategies.router import StrategyConfig, get_active_strategies, should_evaluate_strategy
    import redis.asyncio as redis
    
    settings = get_settings()
    now = datetime.now(UTC)
    
    configs = []
    configs.append(StrategyConfig(
        strategy_id="OPEN_DRIVE_MOMO",
        strategy_version=ODM_VERSION,
        entry_start_et=getattr(settings, "open_drive_entry_start_et", "09:35"),
        entry_end_et=getattr(settings, "open_drive_entry_end_et", "11:30"),
        force_flat_et=getattr(settings, "force_flat_et", "15:45"),
        enabled=getattr(settings, "strategy_open_drive_enabled", True),
        paper_enabled=getattr(settings, "strategy_open_drive_paper_enabled", True),
    ))

    configs.append(StrategyConfig(
        strategy_id="INTRADAY_CONTINUATION",
        strategy_version=IC_VERSION,
        entry_start_et=getattr(settings, "intraday_entry_start_et", "10:30"),
        entry_end_et=getattr(settings, "intraday_entry_end_et", "14:30"),
        force_flat_et=getattr(settings, "force_flat_et", "15:45"),
        enabled=getattr(settings, "strategy_intraday_continuation_enabled", True),
        paper_enabled=getattr(settings, "strategy_intraday_continuation_paper_enabled", False),
    ))
    
    intra_event_enabled = getattr(settings, "strategy_intra_event_momo_enabled", False)
    configs.append(StrategyConfig(
        strategy_id="INTRA_EVENT_MOMO",
        strategy_version=IEM_VERSION,
        entry_start_et=getattr(settings, "entry_start_et", "09:35"),
        entry_end_et=getattr(settings, "entry_end_et", "11:30"),
        force_flat_et=getattr(settings, "force_flat_et", "15:45"),
        enabled=intra_event_enabled,
        paper_enabled=False,
    ))

    swing_enabled = getattr(settings, "strategy_swing_event_continuation_enabled", True)
    swing_paper = getattr(settings, "strategy_swing_event_continuation_paper_enabled", False)
    configs.append(StrategyConfig(
        strategy_id="SWING_EVENT_CONTINUATION",
        strategy_version=SEC_VERSION,
        entry_start_et="13:00",
        entry_end_et="15:30",
        force_flat_et=None,
        enabled=swing_enabled,
        paper_enabled=swing_paper,
        holding_period_type="swing",
        max_hold_days=5,
    ))

    # Get already-traded symbols from Redis (per strategy)
    already_traded: set[str] = set()
    try:
        redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        for config in configs:
            traded_key = f"stockbot:strategies:{config.strategy_id.lower()}:traded_today"
            try:
                traded = await redis_client.smembers(traded_key)
                already_traded.update(traded)
            except Exception:
                pass
        await redis_client.aclose()
    except Exception:
        pass
    
    # Check eligibility for each strategy
    eligibility: dict[str, dict] = {}
    for config in configs:
        should_eval, reason = should_evaluate_strategy(
            config.strategy_id,
            symbol,
            now,
            already_traded,
            configs,
        )
        entry_window = f"{config.entry_start_et}-{config.entry_end_et} ET"
        elig_entry: dict[str, Any] = {
            "eligible": should_eval,
            "reason": reason,
            "entry_window": entry_window,
            "paper_enabled": config.paper_enabled,
            "enabled": config.enabled,
            "holding_period_type": getattr(config, "holding_period_type", "intraday"),
        }
        if getattr(config, "holding_period_type", "intraday") == "swing":
            elig_entry["max_hold_days"] = getattr(config, "max_hold_days", 5)
            elig_entry["overnight_carry"] = True
            elig_entry["force_flat_et"] = None
        else:
            elig_entry["force_flat_et"] = config.force_flat_et
        eligibility[config.strategy_id] = elig_entry

    return eligibility


def _session_allowed_and_reason() -> tuple[str, bool, bool, str | None]:
    """Return (session, scanner_session_allowed, opportunity_session_allowed, reason_if_blocked)."""
    from stockbot.config import get_settings
    from stockbot.market_sessions import current_session, session_allows_scanner
    settings = get_settings()
    try:
        session = current_session()
    except Exception:
        session = "unknown"
    scanner_ok = session_allows_scanner(
        session,
        premarket_ok=getattr(settings, "scanner_premarket_enabled", False),
        regular_ok=getattr(settings, "scanner_regular_hours_enabled", True),
        afterhours_ok=getattr(settings, "scanner_after_hours_enabled", False),
        overnight_ok=getattr(settings, "scanner_overnight_enabled", False),
    )
    reason = None if scanner_ok else f"scanning_disabled_in_{session}"
    return (session, scanner_ok, scanner_ok, reason)


@app.get("/v1/opportunities/summary")
async def get_opportunities_summary() -> dict:
    """Summary of latest live opportunity run. Never returns historical (hist_*) run_id."""
    from stockbot.opportunities.service import get_latest_opportunity_run_and_candidates
    session, scanner_ok, opportunity_ok, reason_if_blocked = _session_allowed_and_reason()
    run_id, updated_at, candidates = await get_latest_opportunity_run_and_candidates()
    base = {
        "session": session,
        "scanner_session_allowed": scanner_ok,
        "opportunity_session_allowed": opportunity_ok,
        "reason_if_blocked": reason_if_blocked,
    }
    if run_id:
        top_scrappy_count = sum(1 for c in candidates if c.get("scrappy_present"))
        return {
            **base,
            "run_id": run_id,
            "updated_at": updated_at,
            "top_count": len(candidates),
            "top_scrappy_count": top_scrappy_count,
            "source": "opportunity_engine",
        }
    factory = get_session_factory()
    async with factory() as session:
        snap = await get_latest_live_toplist_snapshot(session)
        if not snap:
            return {
                **base,
                "run_id": None,
                "updated_at": None,
                "top_count": 0,
                "top_scrappy_count": 0,
                "source": "none",
                "reason": "no_live_scanner_run",
            }
        candidates_scanner = await get_candidates_for_run(
            session, snap.run_id, status="top_candidate", limit=500
        )
        top_scrappy_count = sum(1 for c in candidates_scanner if c.scrappy_present)
        return {
            **base,
            "run_id": snap.run_id,
            "updated_at": snap.snapshot_ts.isoformat() if snap.snapshot_ts else None,
            "top_count": len(snap.symbols_json) if snap.symbols_json else 0,
            "top_scrappy_count": top_scrappy_count,
            "source": "scanner",
        }


@app.get("/v1/opportunities/session")
async def get_opportunities_session() -> dict:
    """Current market session (overnight, premarket, regular, afterhours, closed)."""
    from stockbot.market_sessions import current_session
    return {"session": current_session()}


@app.get("/v1/opportunities/symbol/{symbol}")
async def get_opportunities_symbol(symbol: str) -> dict:
    """Latest opportunity candidate for symbol (from latest opportunity run); includes Scrappy enrichment when present."""
    sym = symbol.upper().strip()
    factory = get_session_factory()
    row = None
    async with factory() as session:
        r = await session.execute(
            select(OpportunityCandidateRow)
            .where(OpportunityCandidateRow.symbol == sym)
            .order_by(OpportunityCandidateRow.run_id.desc())
            .limit(1)
        )
        row = r.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="not_found")
        out = {
            "symbol": row.symbol,
            "run_id": row.run_id,
            "rank": row.rank,
            "total_score": row.total_score,
            "market_score": row.market_score,
            "semantic_score": row.semantic_score,
            "candidate_source": row.candidate_source,
            "inclusion_reasons": row.inclusion_reasons_json or [],
            "filter_reasons": row.filter_reasons_json or [],
            "session": row.session,
            "news_count": row.news_count,
            "scrappy_present": row.scrappy_present,
        }
        if row.scrappy_present:
            snap = await get_latest_snapshot_by_symbol(session, sym)
            if snap:
                out.update(_snapshot_to_scrappy_enrichment(snap))
        
        # PHASE 5: Add strategy eligibility information
        try:
            market_data = {
                "price": float(row.total_score) if row.total_score else None,
            }
            strategy_eligibility = await _get_strategy_eligibility_for_symbol(
                sym,
                market_data=market_data,
            )
            out["strategy_eligibility"] = strategy_eligibility
        except Exception as e:
            logger.debug("strategy_eligibility_check_failed symbol=%s error=%s", sym, e)
            out["strategy_eligibility"] = {}
    
    return out


@app.get("/v1/scrappy/status")
async def get_scrappy_status() -> dict:
    """Scrappy automation status: last auto-run, watchlist size, auto-enabled, with truthful failure tracking."""
    try:
        from stockbot.config import get_settings
        from stockbot.scrappy.run_service import get_watchlist_symbols_list
        from datetime import UTC, datetime, timedelta
        import redis.asyncio as redis
        import json
        settings = get_settings()
        auto_enabled = getattr(settings, "scrappy_auto_enabled", True)
        watchlist = await get_watchlist_symbols_list()
        factory = get_session_factory()
        
        last_auto = None
        async with factory() as session:
            r = await session.execute(
                select(ScrappyAutoRun).order_by(ScrappyAutoRun.run_ts.desc()).limit(1)
            )
            last_auto = r.scalars().first()
        
        # Get Redis state for last attempt, failure reason, symbols
        last_attempt_ts = None
        last_failure_reason = None
        last_outcome = None
        last_symbols_requested = []
        last_symbols_researched = []
        try:
            r = redis.from_url(settings.redis_url, decode_responses=True)
            last_attempt_ts = await r.get("stockbot:scrappy_auto:last_attempt_ts")
            last_failure_reason = await r.get("stockbot:scrappy_auto:last_failure_reason")
            last_outcome = await r.get("stockbot:scrappy_auto:last_outcome")
            symbols_req_json = await r.get("stockbot:scrappy_auto:last_symbols_requested")
            symbols_res_json = await r.get("stockbot:scrappy_auto:last_symbols_researched")
            await r.aclose()
            if symbols_req_json:
                try:
                    last_symbols_requested = json.loads(symbols_req_json)
                except Exception:
                    pass
            if symbols_res_json:
                try:
                    last_symbols_researched = json.loads(symbols_res_json)
                except Exception:
                    pass
        except Exception:
            pass
        
        # Determine service health: healthy if no recent auth errors and last attempt was recent
        service_health = "unknown"
        service_health_reason = None
        if last_failure_reason:
            if "password authentication failed" in last_failure_reason.lower() or "invalidpassword" in last_failure_reason.lower():
                service_health = "failed"
                service_health_reason = f"auth_error: {last_failure_reason}"
            else:
                service_health = "degraded"
                service_health_reason = last_failure_reason
        elif last_attempt_ts:
            try:
                attempt_dt = datetime.fromisoformat(last_attempt_ts.replace("Z", "+00:00"))
                age_minutes = (datetime.now(UTC) - attempt_dt.replace(tzinfo=UTC)).total_seconds() / 60
                if age_minutes < 120:  # Recent attempt within 2 hours
                    if last_outcome and last_outcome not in ("failed", "skipped"):
                        service_health = "healthy"
                    elif last_outcome == "skipped":
                        service_health = "healthy"  # Skipped is normal (e.g., no symbols)
                        service_health_reason = "skipped (no symbols or outside session)"
                    else:
                        service_health = "unknown"
                else:
                    service_health = "stale"
                    service_health_reason = f"last_attempt_{int(age_minutes)}_minutes_ago"
            except Exception:
                pass
        elif last_auto and last_auto.run_ts:
            age_minutes = (datetime.now(UTC) - last_auto.run_ts.replace(tzinfo=UTC)).total_seconds() / 60
            if age_minutes < 120:
                service_health = "healthy"
            else:
                service_health = "stale"
                service_health_reason = f"last_run_{int(age_minutes)}_minutes_ago"
        
        # Calculate coverage status counts for focus symbols
        coverage_counts = {"fresh_research": 0, "carried_forward_research": 0, "low_evidence": 0, "no_research": 0}
        try:
            from stockbot.scrappy.snapshot import classify_coverage_status
            r = redis.from_url(settings.redis_url, decode_responses=True)
            scanner_top_json = await r.get("stockbot:scanner:top_symbols")
            await r.aclose()
            focus_symbols = []
            if scanner_top_json:
                try:
                    focus_symbols = json.loads(scanner_top_json)
                    if isinstance(focus_symbols, list):
                        focus_symbols = [s.strip().upper() for s in focus_symbols if s][:20]
                except Exception:
                    pass
            
            if focus_symbols:
                async with factory() as session:
                    for sym in focus_symbols:
                        try:
                            snap = await get_latest_snapshot_by_symbol(session, sym)
                            coverage = classify_coverage_status(snap)
                            if coverage.status in coverage_counts:
                                coverage_counts[coverage.status] += 1
                        except Exception:
                            pass
        except Exception:
            pass
        
        result = {
            "scrappy_auto_enabled": auto_enabled,
            "service_health": service_health,
            "service_health_reason": service_health_reason,
            "last_run_at": last_auto.run_ts.isoformat() if last_auto and last_auto.run_ts else None,
            "last_attempt_at": last_attempt_ts,
            "last_run_id": last_auto.run_id if last_auto else None,
            "last_outcome": last_outcome or (last_auto.status if last_auto else None),
            "last_failure_reason": last_failure_reason,
            "last_notes_created": last_auto.notes_created if last_auto else 0,
            "last_snapshots_updated": last_auto.snapshots_updated if last_auto else 0,
            "last_symbols_requested": last_symbols_requested,
            "last_symbols_researched": last_symbols_researched,
            "watchlist_size": len(watchlist) if watchlist else 0,
            "coverage_counts": coverage_counts,
        }
        return _sanitize_json_value(result)
    except Exception as e:
        logger.exception("Error in get_scrappy_status")
        return {
            "error": "internal_error",
            "message": str(e)[:200],
            "scrappy_auto_enabled": False,
            "service_health": "error",
            "service_health_reason": f"exception: {type(e).__name__}",
            "last_run_at": None,
            "last_attempt_at": None,
            "last_run_id": None,
            "last_outcome": None,
            "last_failure_reason": None,
            "last_notes_created": 0,
            "last_snapshots_updated": 0,
            "last_symbols_requested": [],
            "last_symbols_researched": [],
            "watchlist_size": 0,
            "coverage_counts": {"fresh_research": 0, "carried_forward_research": 0, "low_evidence": 0, "no_research": 0},
        }


@app.get("/v1/premarket/status")
async def get_premarket_status() -> dict:
    """Comprehensive premarket status: scanner, opportunities, Scrappy coverage, AI Referee, overall state."""
    try:
        from datetime import UTC, datetime
        from stockbot.config import get_settings
        from stockbot.market_sessions import current_session, is_premarket
        from stockbot.scrappy.snapshot import classify_coverage_status
        import redis.asyncio as redis
        import json
        
        settings = get_settings()
        session_label = current_session()
        
        # Get focus symbols from scanner/opportunities
        focus_symbols = []
        scanner_live = False
        opportunities_count = 0
        try:
            r = redis.from_url(settings.redis_url, decode_responses=True)
            scanner_top_json = await r.get("stockbot:scanner:top_symbols")
            scanner_top_ts = await r.get(SCANNER_TOP_TS_KEY)  # Use consistent key: stockbot:scanner:top_updated_at
            await r.aclose()
            if scanner_top_json:
                try:
                    focus_symbols = json.loads(scanner_top_json)
                    if isinstance(focus_symbols, list):
                        focus_symbols = [s.strip().upper() for s in focus_symbols if s]
                except Exception:
                    pass
            if scanner_top_ts:
                scanner_live = True
        except Exception:
            pass
        
        # Get opportunities count
        try:
            from stockbot.opportunities.service import get_latest_opportunity_run_and_candidates
            _, _, candidates = await get_latest_opportunity_run_and_candidates()
            if candidates:
                opportunities_count = len(candidates)
        except Exception:
            pass
        
        # Get Scrappy status (with error handling)
        scrappy_status = {}
        try:
            scrappy_status = await get_scrappy_status()
        except Exception:
            scrappy_status = {
                "scrappy_auto_enabled": False,
                "last_run_at": None,
                "last_attempt_at": None,
                "last_failure_reason": "error_fetching_status",
                "last_notes_created": 0,
                "last_snapshots_updated": 0,
                "coverage_counts": {"fresh_research": 0, "carried_forward_research": 0, "low_evidence": 0, "no_research": 0},
            }
        
        # Classify coverage for all focus symbols
        coverage_counts = {"fresh_research": 0, "carried_forward_research": 0, "low_evidence": 0, "no_research": 0}
        coverage_details: list[dict] = []
        factory = get_session_factory()
        try:
            async with factory() as session:
                for sym in focus_symbols[:20]:
                    try:
                        snap = await get_latest_snapshot_by_symbol(session, sym)
                        coverage = classify_coverage_status(snap)
                        if coverage.status in coverage_counts:
                            coverage_counts[coverage.status] += 1
                        coverage_details.append({
                            "symbol": sym,
                            "coverage_status": coverage.status,
                            "coverage_reason": coverage.reason,
                            "evidence_count": coverage.evidence_count,
                            "freshness_minutes": coverage.freshness_minutes,
                        })
                    except Exception:
                        coverage_details.append({
                            "symbol": sym,
                            "coverage_status": "no_research",
                            "coverage_reason": "error_checking_snapshot",
                            "evidence_count": 0,
                            "freshness_minutes": 0,
                        })
        except Exception:
            pass
        
        # Get AI Referee premarket status
        ai_referee_enabled = getattr(settings, "ai_referee_enabled", False)
        ai_referee_last_run = None
        ai_referee_assessed = 0
        try:
            r = redis.from_url(settings.redis_url, decode_responses=True)
            ai_referee_last_run = await r.get("stockbot:ai_referee_premarket:last_run_ts")
            await r.aclose()
            # Count recent assessments
            from stockbot.ai_referee.store import list_recent_assessments
            async with factory() as session:
                recent = await list_recent_assessments(session, limit=100)
                ai_referee_assessed = len([a for a in recent if a.assessment_ts and (datetime.now(UTC) - a.assessment_ts.replace(tzinfo=UTC)).total_seconds() < 3600 * 4])
        except Exception:
            pass
        
        # Determine overall premarket state
        overall_state = "not_running"
        if scanner_live and opportunities_count > 0:
            if coverage_counts["fresh_research"] > 0 or coverage_counts["carried_forward_research"] > 0:
                overall_state = "alive"
            elif coverage_counts["low_evidence"] > 0 or coverage_counts["no_research"] > 0:
                overall_state = "degraded"
            else:
                overall_state = "partial"
        elif scanner_live:
            overall_state = "partial"
        
        result = {
            "session": session_label,
            "is_premarket": is_premarket(),
            "overall_state": overall_state,
            "scanner": {
                "live": scanner_live,
                "focus_symbols_count": len(focus_symbols),
                "focus_symbols": focus_symbols[:20],
            },
            "opportunities": {
                "count": opportunities_count,
            },
            "scrappy": {
                "auto_enabled": scrappy_status.get("scrappy_auto_enabled"),
                "last_run_at": scrappy_status.get("last_run_at"),
                "last_attempt_at": scrappy_status.get("last_attempt_at"),
                "last_failure_reason": scrappy_status.get("last_failure_reason"),
                "last_notes_created": scrappy_status.get("last_notes_created"),
                "last_snapshots_updated": scrappy_status.get("last_snapshots_updated"),
                "coverage_counts": coverage_counts,
            },
            "ai_referee": {
                "enabled": ai_referee_enabled,
                "last_run_at": ai_referee_last_run,
                "assessed_count_recent": ai_referee_assessed,
            },
            "coverage_details": coverage_details,
        }
        return _sanitize_json_value(result)
    except Exception as e:
        logger.exception("Error in get_premarket_status")
        return {
            "error": "internal_error",
            "message": str(e)[:200],
            "session": "unknown",
            "is_premarket": False,
            "overall_state": "error",
            "scanner": {"live": False, "focus_symbols_count": 0, "focus_symbols": []},
            "opportunities": {"count": 0},
            "scrappy": {
                "auto_enabled": False,
                "last_run_at": None,
                "last_attempt_at": None,
                "last_failure_reason": f"exception: {type(e).__name__}",
                "last_notes_created": 0,
                "last_snapshots_updated": 0,
                "coverage_counts": {"fresh_research": 0, "carried_forward_research": 0, "low_evidence": 0, "no_research": 0},
            },
            "ai_referee": {"enabled": False, "last_run_at": None, "assessed_count_recent": 0},
            "coverage_details": [],
        }


@app.get("/v1/scrappy/auto-runs")
async def get_scrappy_auto_runs(
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Recent Scrappy auto-run audit records."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(ScrappyAutoRun)
            .order_by(ScrappyAutoRun.run_ts.desc())
            .limit(limit)
        )
        rows = list(result.scalars().all())
    return {
        "runs": [
            {
                "run_id": r.run_id,
                "run_ts": r.run_ts.isoformat() if r.run_ts else None,
                "source": r.source,
                "symbols_count": len(r.symbols_json) if r.symbols_json else 0,
                "notes_created": r.notes_created,
                "snapshots_updated": r.snapshots_updated,
                "status": r.status,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@app.post("/v1/scanner/run/historical")
async def run_historical_scanner_endpoint(
    days: int = Query(default=30, ge=1, le=365, description="Lookback days (30 or 90)"),
    symbols: str | None = Query(None, description="Comma-separated symbols; default from config"),
) -> dict:
    """Run historical scanner over past days; persist runs for research."""
    from stockbot.research.historical_scanner import run_historical_scanner
    sym_list = [s.strip() for s in symbols.split(",")] if symbols else None
    try:
        run_ids = await run_historical_scanner(lookback_days=days, symbols=sym_list)
        return {"run_ids": run_ids, "count": len(run_ids)}
    except Exception as e:
        msg = str(e).strip()
        if not msg:
            msg = type(e).__name__
        raise HTTPException(status_code=500, detail=msg[:500])


@app.get("/v1/opportunities/history")
async def get_opportunities_history(
    symbol: str | None = Query(None),
    days: int = Query(default=30, ge=1, le=365),
) -> dict:
    """Historical candidate appearances for a symbol (for research)."""
    from datetime import timedelta
    from datetime import UTC, datetime
    factory = get_session_factory()
    if not symbol:
        return {"symbol": None, "days": days, "appearances": [], "count": 0}
    async with factory() as session:
        q = (
            select(ScannerCandidateRow)
            .where(ScannerCandidateRow.symbol == symbol.upper())
            .order_by(ScannerCandidateRow.created_at.desc())
            .limit(200)
        )
        result = await session.execute(q)
        rows = list(result.scalars().all())
    cutoff = datetime.now(UTC) - timedelta(days=days)
    filtered = [r for r in rows if r.created_at and r.created_at >= cutoff]
    return {
        "symbol": symbol,
        "days": days,
        "appearances": [
            {"run_id": r.run_id, "rank": r.rank, "total_score": r.total_score, "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in filtered[:50]
        ],
        "count": len(filtered),
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
