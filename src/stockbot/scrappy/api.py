"""Scrappy API: health, telemetry, sources/health, audit, notes/recent, run triggers."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from stockbot.db.session import get_session_factory
from stockbot.scrappy.run_service import (
    get_audit,
    get_notes_recent,
    get_telemetry,
    get_watchlist_symbols_list,
    run_scrappy,
)
from stockbot.scrappy.sources import load_scrappy_sources
from stockbot.scrappy.store import get_source_health_all

router = APIRouter(prefix="/scrappy", tags=["scrappy"])


@router.get("/health")
def scrappy_health() -> dict[str, str]:
    """Scrappy service health."""
    return {"status": "ok", "service": "scrappy"}


@router.get("/telemetry")
async def scrappy_telemetry(
    limit: int = Query(default=50, ge=1, le=200),
    hours: int = Query(default=24, ge=1, le=168),
) -> dict[str, Any]:
    """Scrappy run telemetry from DB: runs, notes_total, outcome codes, zero_yield_streak."""
    cfg = load_scrappy_sources()
    data = await get_telemetry(limit=limit, hours=hours)
    data["sources_count"] = len(cfg.get("sources") or [])
    return data


@router.get("/sources/health")
async def scrappy_sources_health() -> dict[str, Any]:
    """Configured sources and per-source health (last success/fail counts from DB)."""
    cfg = load_scrappy_sources()
    sources_list = cfg.get("sources") or []
    enabled = [s for s in sources_list if isinstance(s, dict) and s.get("enabled", True)]
    health_by_name: dict[str, dict] = {}
    try:
        factory = get_session_factory()
        async with factory() as session:
            for h in await get_source_health_all(session):
                health_by_name[h["source_name"]] = h
    except Exception:
        pass
    sources_payload = []
    for s in enabled:
        name = s.get("name")
        rec = {"name": name, "source_type": s.get("source_type"), "trust_tier": s.get("trust_tier")}
        if name and name in health_by_name:
            h = health_by_name[name]
            rec["last_attempt_at"] = h.get("last_attempt_at")
            rec["last_success_at"] = h.get("last_success_at")
            rec["attempt_count"] = h.get("attempt_count", 0)
            rec["success_count"] = h.get("success_count", 0)
            rec["failure_count"] = h.get("failure_count", 0)
            rec["fetch_success_count"] = h.get("fetch_success_count", 0)
            rec["fetch_failure_count"] = h.get("fetch_failure_count", 0)
            rec["candidate_count"] = h.get("candidate_count", 0)
            rec["post_dedup_count"] = h.get("post_dedup_count", 0)
            rec["notes_inserted_count"] = h.get("notes_inserted_count", 0)
            rec["last_error_code"] = h.get("last_error_code")
            rec["last_error_message"] = h.get("last_error_message")
        sources_payload.append(rec)
    return {
        "total_configured": len(sources_list),
        "enabled": len(enabled),
        "sources": sources_payload,
    }


@router.get("/audit")
async def scrappy_audit(
    limit: int = Query(default=10, ge=1, le=50),
) -> dict[str, Any]:
    """Persistence audit from DB: last N runs with candidate/post_dedup/notes_created, mismatch, errors."""
    return await get_audit(limit=limit)


@router.get("/notes/recent")
async def scrappy_notes_recent(
    limit: int = Query(default=50, ge=1, le=200),
    symbol: str | None = Query(default=None),
    catalyst_type: str | None = Query(default=None),
    sentiment_label: str | None = Query(default=None),
    content_mode: str | None = Query(default=None),
    since_hours: int | None = Query(default=None, ge=1, le=720),
) -> dict[str, Any]:
    """Recent market_intel_notes with optional filters: symbol, catalyst_type, sentiment_label, content_mode, since_hours."""
    notes = await get_notes_recent(
        limit=limit,
        symbol=symbol,
        catalyst_type=catalyst_type,
        sentiment_label=sentiment_label,
        content_mode=content_mode,
        since_hours=since_hours,
    )
    return {"notes": notes, "count": len(notes)}


@router.post("/run")
async def scrappy_run(
    run_type: str = "sweep",
    symbols: list[str] | None = None,
    themes: list[str] | None = None,
) -> dict[str, Any]:
    """Trigger a Scrappy run (sweep)."""
    result = await run_scrappy(run_type=run_type or "sweep", symbols=symbols or [], themes=themes or [])
    return result


@router.get("/watchlist")
async def scrappy_watchlist() -> dict[str, Any]:
    """Return watchlist symbols (from watchlist_symbols table)."""
    symbols = await get_watchlist_symbols_list()
    return {"symbols": symbols, "count": len(symbols)}


def _validate_watchlist_symbol(symbol: str) -> str:
    """Validate symbol for watchlist: non-empty, 1-10 chars, alphanumeric. Raises ValueError."""
    s = (symbol or "").strip().upper()
    if not s:
        raise ValueError("symbol is required")
    if len(s) > 10:
        raise ValueError("symbol too long")
    if not s.isalnum():
        raise ValueError("symbol must be alphanumeric")
    return s


@router.post("/watchlist")
async def scrappy_watchlist_add(symbol: str) -> dict[str, Any]:
    """Add symbol to watchlist. Validates symbol format."""
    from fastapi import HTTPException

    from stockbot.scrappy.store import add_watchlist_symbol
    try:
        validated = _validate_watchlist_symbol(symbol)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    factory = get_session_factory()
    async with factory() as session:
        await add_watchlist_symbol(session, validated, source="api")
    return {"symbol": validated, "added": True}


@router.post("/run/watchlist")
async def scrappy_run_watchlist() -> dict[str, Any]:
    """Trigger run with symbols from watchlist (watchlist_symbols table)."""
    return await run_scrappy(
        run_type="watchlist",
        symbols=[],
        themes=[],
        watchlist_symbols_fn=get_watchlist_symbols_list,
    )


@router.post("/run/symbol/{symbol}")
async def scrappy_run_symbol(symbol: str) -> dict[str, Any]:
    """Trigger run for a single symbol."""
    return await run_scrappy(run_type="symbol", symbols=[symbol], themes=[])
