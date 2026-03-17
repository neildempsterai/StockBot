"""Scheduler: regular-hours only in v0.1; trigger strategy runs."""
from __future__ import annotations

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_scheduler() -> None:
    # Placeholder: cron-like triggers; extended_hours disabled for v0.1
    while True:
        logger.info("scheduler tick")
        await asyncio.sleep(60)


def main() -> None:
    asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()
