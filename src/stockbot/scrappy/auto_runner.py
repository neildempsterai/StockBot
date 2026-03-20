"""
Proactive Scrappy: run on scanner/opportunity top symbols on a schedule.
Does not require manual "Run Scrappy" clicks. Uses live top from Redis first, then watchlist.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

import redis.asyncio as redis

from stockbot.config import get_settings
from stockbot.market_sessions import current_session, is_premarket, is_regular_hours
from stockbot.scrappy.run_service import get_watchlist_symbols_list, run_scrappy

logger = logging.getLogger(__name__)

REDIS_KEY_SCRAPPY_AUTO_LAST_RUN = "stockbot:scrappy_auto:last_run_ts"
REDIS_KEY_SCRAPPY_AUTO_LAST_OUTCOME = "stockbot:scrappy_auto:last_outcome"
REDIS_KEY_SCRAPPY_AUTO_LAST_ATTEMPT = "stockbot:scrappy_auto:last_attempt_ts"
REDIS_KEY_SCRAPPY_AUTO_LAST_FAILURE = "stockbot:scrappy_auto:last_failure_reason"
REDIS_KEY_SCRAPPY_AUTO_LAST_SYMBOLS = "stockbot:scrappy_auto:last_symbols"
REDIS_KEY_SCRAPPY_AUTO_LAST_SYMBOLS_REQUESTED = "stockbot:scrappy_auto:last_symbols_requested"
REDIS_KEY_SCRAPPY_AUTO_LAST_SYMBOLS_RESEARCHED = "stockbot:scrappy_auto:last_symbols_researched"
REDIS_KEY_SCANNER_TOP = "stockbot:scanner:top_symbols"
REDIS_TTL_LAST_SYMBOLS_SEC = 86400 * 2

# During premarket, refresh research even if symbols unchanged if last run was > this many minutes ago
PREMARKET_REFRESH_MINUTES = 30


async def _persist_auto_run(result: dict, symbols: list[str], failure_reason: str | None = None) -> None:
    """Write ScrappyAutoRun row for audit."""
    try:
        from datetime import UTC, datetime
        from stockbot.db.session import get_session_factory
        from stockbot.db.models import ScrappyAutoRun
        run_id = result.get("run_id") or ""
        if not run_id and not failure_reason:
            return
        factory = get_session_factory()
        async with factory() as session:
            row = ScrappyAutoRun(
                run_id=run_id or f"failed_{datetime.now(UTC).isoformat()}",
                run_ts=datetime.now(UTC),
                source="scanner_watchlist",
                symbols_json=symbols,
                notes_created=result.get("notes_created", 0) or 0 if result else 0,
                snapshots_updated=result.get("snapshots_updated", 0) or 0 if result else 0,
                status=result.get("outcome_code") or ("failed" if failure_reason else "completed") if result else "failed",
            )
            session.add(row)
            await session.commit()
    except Exception as e:
        logger.debug("scrappy_auto persist: %s", e)


async def _get_live_top_symbols() -> list[str]:
    """Live top symbols from Redis (from scanner/opportunity). Empty if none."""
    try:
        settings = get_settings()
        r = redis.from_url(settings.redis_url, decode_responses=True)
        raw = await r.get(REDIS_KEY_SCANNER_TOP)
        await r.aclose()
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, list) and data:
            return [str(s).strip() for s in data if s][:50]
    except Exception:
        pass
    return []


async def _should_refresh_during_premarket(
    r: redis.Redis, symbols: list[str], last_symbols_json: str | None
) -> bool:
    """During premarket, refresh if symbols changed OR if last run was > PREMARKET_REFRESH_MINUTES ago."""
    if not is_premarket():
        # Outside premarket, use symbol-change logic only
        if last_symbols_json:
            try:
                last_symbols = json.loads(last_symbols_json)
                if isinstance(last_symbols, list) and last_symbols == symbols:
                    return False
            except Exception:
                pass
        return True
    
    # During premarket: check time-based refresh
    last_run_iso = await r.get(REDIS_KEY_SCRAPPY_AUTO_LAST_RUN)
    if last_run_iso:
        try:
            last_run = datetime.fromisoformat(last_run_iso.replace('Z', '+00:00'))
            if last_run.tzinfo is None:
                last_run = last_run.replace(tzinfo=UTC)
            age_minutes = (datetime.now(UTC) - last_run).total_seconds() / 60.0
            if age_minutes < PREMARKET_REFRESH_MINUTES:
                # Recent run and symbols unchanged - skip
                if last_symbols_json:
                    try:
                        last_symbols = json.loads(last_symbols_json)
                        if isinstance(last_symbols, list) and last_symbols == symbols:
                            logger.debug("scrappy_auto premarket: symbols unchanged and last run %d min ago (< %d min), skipping", int(age_minutes), PREMARKET_REFRESH_MINUTES)
                            return False
                    except Exception:
                        pass
        except Exception:
            pass
    
    # Refresh if symbols changed OR if last run was old enough
    return True


async def run_scrappy_auto_once() -> dict | None:
    """Run Scrappy on live top symbols from Redis first, else watchlist. Returns run result or None if skipped."""
    settings = get_settings()
    if not getattr(settings, "scrappy_auto_enabled", True):
        return None
    session = current_session()
    if session in ("closed", "overnight"):
        return None
    
    attempt_ts = datetime.now(UTC).isoformat()
    symbols_requested: list[str] = []
    failure_reason: str | None = None
    
    try:
        r = redis.from_url(settings.redis_url, decode_responses=True)
        await r.set(REDIS_KEY_SCRAPPY_AUTO_LAST_ATTEMPT, attempt_ts, ex=REDIS_TTL_LAST_SYMBOLS_SEC)
        
        symbols = await _get_live_top_symbols()
        if not symbols:
            symbols = await get_watchlist_symbols_list()
        if not symbols:
            failure_reason = "no_live_top_symbols_and_no_watchlist"
            logger.debug("scrappy_auto %s, skipping", failure_reason)
            await r.set(REDIS_KEY_SCRAPPY_AUTO_LAST_FAILURE, failure_reason, ex=REDIS_TTL_LAST_SYMBOLS_SEC)
            await r.set(REDIS_KEY_SCRAPPY_AUTO_LAST_OUTCOME, "skipped", ex=REDIS_TTL_LAST_SYMBOLS_SEC)
            await r.aclose()
            await _persist_auto_run({}, [], failure_reason)
            return None
        
        top_n = getattr(settings, "scrappy_auto_top_symbols", 15)
        symbols = symbols[:top_n]
        symbols_requested = symbols.copy()
        await r.set(REDIS_KEY_SCRAPPY_AUTO_LAST_SYMBOLS_REQUESTED, json.dumps(symbols_requested), ex=REDIS_TTL_LAST_SYMBOLS_SEC)
        
        # Check if we should refresh (symbols changed OR premarket time-based refresh)
        last_symbols_json = await r.get(REDIS_KEY_SCRAPPY_AUTO_LAST_SYMBOLS)
        should_refresh = await _should_refresh_during_premarket(r, symbols, last_symbols_json)
        if not should_refresh:
            await r.aclose()
            return None
        
        async def _watchlist_fn():
            return symbols

        result = await run_scrappy(
            run_type="watchlist",
            symbols=[],
            themes=[],
            watchlist_symbols_fn=_watchlist_fn,
        )
        
        symbols_researched = symbols_requested.copy()  # All requested symbols were attempted
        snapshots_updated = result.get("snapshots_updated", 0) or 0
        
        logger.info(
            "scrappy_auto run_id=%s outcome=%s notes_created=%s snapshots_updated=%s symbols_requested=%d",
            result.get("run_id", "")[:8],
            result.get("outcome_code", ""),
            result.get("notes_created", 0),
            snapshots_updated,
            len(symbols_requested),
        )
        
        await _persist_auto_run(result, symbols_requested)
        
        await r.set(REDIS_KEY_SCRAPPY_AUTO_LAST_SYMBOLS, json.dumps(symbols), ex=REDIS_TTL_LAST_SYMBOLS_SEC)
        await r.set(REDIS_KEY_SCRAPPY_AUTO_LAST_RUN, datetime.now(UTC).isoformat(), ex=REDIS_TTL_LAST_SYMBOLS_SEC)
        await r.set(REDIS_KEY_SCRAPPY_AUTO_LAST_OUTCOME, result.get("outcome_code", "unknown"), ex=REDIS_TTL_LAST_SYMBOLS_SEC)
        await r.set(REDIS_KEY_SCRAPPY_AUTO_LAST_SYMBOLS_RESEARCHED, json.dumps(symbols_researched), ex=REDIS_TTL_LAST_SYMBOLS_SEC)
        await r.delete(REDIS_KEY_SCRAPPY_AUTO_LAST_FAILURE)  # Clear failure on success
        await r.aclose()
        return result
    except asyncio.CancelledError:
        raise
    except Exception as e:
        failure_reason = f"exception: {str(e)[:100]}"
        logger.exception("scrappy_auto run failed: %s", e)
        try:
            r = redis.from_url(settings.redis_url, decode_responses=True)
            await r.set(REDIS_KEY_SCRAPPY_AUTO_LAST_FAILURE, failure_reason, ex=REDIS_TTL_LAST_SYMBOLS_SEC)
            await r.set(REDIS_KEY_SCRAPPY_AUTO_LAST_OUTCOME, "failed", ex=REDIS_TTL_LAST_SYMBOLS_SEC)
            await r.aclose()
        except Exception:
            pass
        await _persist_auto_run({}, symbols_requested if symbols_requested else [], failure_reason)
        return None


async def run_scrappy_auto_loop() -> None:
    """Loop: bootstrap once after delay (scanner/opportunity populate Redis), then every SCRAPPY_AUTO_REFRESH_SEC."""
    settings = get_settings()
    if not getattr(settings, "scrappy_auto_enabled", True):
        logger.info("scrappy_auto disabled (SCRAPPY_AUTO_ENABLED=false)")
        return
    refresh_sec = getattr(settings, "scrappy_auto_refresh_sec", 120)
    bootstrap_on_start = getattr(settings, "scrappy_bootstrap_on_start", True)
    await asyncio.sleep(30)
    try:
        if is_premarket() or is_regular_hours():
            await run_scrappy_auto_once()
        elif bootstrap_on_start:
            await run_scrappy_auto_once()
            logger.info("scrappy_auto bootstrap run (session outside premarket/regular) — last_run_ts set")
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.exception("scrappy_auto bootstrap error: %s", e)
    while True:
        try:
            if is_premarket() or is_regular_hours():
                await run_scrappy_auto_once()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception("scrappy_auto loop error: %s", e)
        await asyncio.sleep(refresh_sec)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_scrappy_auto_loop())


if __name__ == "__main__":
    main()
