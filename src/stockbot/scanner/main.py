"""
Scanner service entrypoint: run scans on schedule (premarket + regular hours).
Writes scanner_runs, scanner_candidates, toplist snapshots; publishes top to Redis; updates Scrappy watchlist.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from stockbot.config import get_settings
from stockbot.scanner.service import run_scan_and_publish

logger = logging.getLogger(__name__)


def _session_allows_scan() -> bool:
    from stockbot.config import get_settings
    from stockbot.market_sessions import current_session, session_allows_scanner
    settings = get_settings()
    session = current_session()
    return session_allows_scanner(
        session,
        premarket_ok=getattr(settings, "scanner_premarket_enabled", False),
        regular_ok=getattr(settings, "scanner_regular_hours_enabled", True),
        afterhours_ok=getattr(settings, "scanner_after_hours_enabled", False),
        overnight_ok=getattr(settings, "scanner_overnight_enabled", False),
    )


async def _get_watchlist_from_db():
    from stockbot.scrappy.run_service import get_watchlist_symbols_list
    return await get_watchlist_symbols_list()


async def run_scanner_loop() -> None:
    settings = get_settings()
    if not getattr(settings, "scanner_enabled", True):
        logger.info("scanner disabled (SCANNER_ENABLED=false)")
        return
    refresh_sec = getattr(settings, "scanner_refresh_sec", 60)
    bootstrap_on_start = getattr(settings, "scanner_bootstrap_on_start", True)
    ran_once = False
    # Bootstrap: run once on startup. If SCANNER_BOOTSTRAP_ON_START=true, run even when session disallows (publish to Redis).
    try:
        if _session_allows_scan():
            result = await run_scan_and_publish(get_watchlist_fn=_get_watchlist_from_db)
            ran_once = True
            logger.info(
                "scanner_bootstrap run_id=%s universe=%s scored=%s top=%s",
                result.run_id[:8],
                result.universe_size,
                result.candidates_scored,
                result.top_candidates_count,
            )
        elif bootstrap_on_start:
            result = await run_scan_and_publish(get_watchlist_fn=_get_watchlist_from_db)
            ran_once = True
            logger.info(
                "scanner_bootstrap (session disallowed) run_id=%s universe=%s top=%s — live run published for gateway/worker",
                result.run_id[:8],
                result.universe_size,
                result.top_candidates_count,
            )
        else:
            logger.info("scanner_bootstrap skipped (session does not allow scan); will retry on interval")
    except Exception as e:
        logger.exception("scanner bootstrap run error: %s", e)
    while True:
        try:
            if not _session_allows_scan():
                await asyncio.sleep(60)
                continue
            result = await run_scan_and_publish(get_watchlist_fn=_get_watchlist_from_db)
            ran_once = True
            logger.info(
                "scanner_run run_id=%s universe=%s scored=%s top=%s",
                result.run_id[:8],
                result.universe_size,
                result.candidates_scored,
                result.top_candidates_count,
            )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception("scanner run error: %s", e)
        await asyncio.sleep(refresh_sec)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_scanner_loop())


if __name__ == "__main__":
    main()
