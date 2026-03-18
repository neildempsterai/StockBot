"""
Scheduler: daily reset at session boundary (America/New_York).
Clear per-day symbol trade locks so strategy can trade again next day.
No extended-hours scheduling. No order placement.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import redis.asyncio as redis

from stockbot.config import get_settings

TRADED_TODAY_KEY = "stockbot:strategies:intra_event_momo:traded_today"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Run reset once per day when we cross into 04:00 ET (before market open)
RESET_HOUR_ET = 4
RESET_MINUTE_ET = 0


def _is_reset_time_et() -> bool:
    try:
        import zoneinfo
        et = zoneinfo.ZoneInfo("America/New_York")
        now = datetime.now(timezone.utc).astimezone(et)
        return now.hour == RESET_HOUR_ET and now.minute == RESET_MINUTE_ET
    except Exception:
        return False


async def run_scheduler() -> None:
    settings = get_settings()
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    last_reset_date: str | None = None

    while True:
        try:
            now_et = datetime.now(timezone.utc)
            try:
                import zoneinfo
                now_et = now_et.astimezone(zoneinfo.ZoneInfo("America/New_York"))
            except Exception:
                pass
            day_key = now_et.strftime("%Y-%m-%d")
            past_reset = now_et.hour > RESET_HOUR_ET or (now_et.hour == RESET_HOUR_ET and now_et.minute >= RESET_MINUTE_ET)
            if last_reset_date != day_key and past_reset:
                await redis_client.delete(TRADED_TODAY_KEY)
                last_reset_date = day_key
                logger.info("day reset: cleared %s for %s", TRADED_TODAY_KEY, day_key)
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception("scheduler error: %s", e)
            await asyncio.sleep(60)


def main() -> None:
    asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()
