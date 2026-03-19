"""
Proactive Scrappy: run on scanner/opportunity top symbols on a schedule.
Does not require manual "Run Scrappy" clicks. Uses live top from Redis first, then watchlist.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime

import redis.asyncio as redis

from stockbot.config import get_settings
from stockbot.market_sessions import current_session, is_premarket, is_regular_hours
from stockbot.scrappy.run_service import get_watchlist_symbols_list, run_scrappy

logger = logging.getLogger(__name__)

REDIS_KEY_SCRAPPY_AUTO_LAST_RUN = "stockbot:scrappy_auto:last_run_ts"
REDIS_KEY_SCRAPPY_AUTO_LAST_OUTCOME = "stockbot:scrappy_auto:last_outcome"
REDIS_KEY_SCRAPPY_AUTO_LAST_SYMBOLS = "stockbot:scrappy_auto:last_symbols"
REDIS_KEY_SCANNER_TOP = "stockbot:scanner:top_symbols"
REDIS_TTL_LAST_SYMBOLS_SEC = 86400 * 2


async def _persist_auto_run(result: dict, symbols: list[str]) -> None:
    """Write ScrappyAutoRun row for audit."""
    try:
        from datetime import UTC, datetime
        from stockbot.db.session import get_session_factory
        from stockbot.db.models import ScrappyAutoRun
        run_id = result.get("run_id") or ""
        if not run_id:
            return
        factory = get_session_factory()
        async with factory() as session:
            row = ScrappyAutoRun(
                run_id=run_id,
                run_ts=datetime.now(UTC),
                source="scanner_watchlist",
                symbols_json=symbols,
                notes_created=result.get("notes_created", 0) or 0,
                snapshots_updated=result.get("snapshots_updated", 0) or 0,
                status=result.get("outcome_code") or "completed",
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


async def run_scrappy_auto_once() -> dict | None:
    """Run Scrappy on live top symbols from Redis first, else watchlist. Returns run result or None if skipped."""
    settings = get_settings()
    if not getattr(settings, "scrappy_auto_enabled", True):
        return None
    session = current_session()
    if session in ("closed", "overnight"):
        return None
    try:
        symbols = await _get_live_top_symbols()
        if not symbols:
            symbols = await get_watchlist_symbols_list()
        if not symbols:
            logger.debug("scrappy_auto no live top symbols and no watchlist, skipping")
            return None
        top_n = getattr(settings, "scrappy_auto_top_symbols", 15)
        symbols = symbols[:top_n]
        # Skip if top symbol list unchanged (simple optimization)
        try:
            r = redis.from_url(settings.redis_url, decode_responses=True)
            last_json = await r.get(REDIS_KEY_SCRAPPY_AUTO_LAST_SYMBOLS)
            await r.aclose()
            if last_json:
                last_symbols = json.loads(last_json)
                if isinstance(last_symbols, list) and last_symbols == symbols:
                    logger.debug("scrappy_auto top symbols unchanged, skipping run")
                    return None
        except Exception:
            pass

        async def _watchlist_fn():
            return symbols

        result = await run_scrappy(
            run_type="watchlist",
            symbols=[],
            themes=[],
            watchlist_symbols_fn=_watchlist_fn,
        )
        logger.info(
            "scrappy_auto run_id=%s outcome=%s notes_created=%s snapshots_updated=%s",
            result.get("run_id", "")[:8],
            result.get("outcome_code", ""),
            result.get("notes_created", 0),
            result.get("snapshots_updated", 0),
        )
        await _persist_auto_run(result, symbols)
        try:
            r = redis.from_url(settings.redis_url, decode_responses=True)
            await r.set(REDIS_KEY_SCRAPPY_AUTO_LAST_SYMBOLS, json.dumps(symbols), ex=REDIS_TTL_LAST_SYMBOLS_SEC)
            await r.set(REDIS_KEY_SCRAPPY_AUTO_LAST_RUN, datetime.now(UTC).isoformat(), ex=REDIS_TTL_LAST_SYMBOLS_SEC)
            await r.aclose()
        except Exception:
            pass
        return result
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.exception("scrappy_auto run failed: %s", e)
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
