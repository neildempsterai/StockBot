"""Worker: consume jobs (e.g. place orders with client_order_id = signal_uuid)."""
from __future__ import annotations

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_worker() -> None:
    # Placeholder: poll Redis or DB for signal jobs; call AlpacaClient.create_order(signal_uuid=client_order_id)
    while True:
        logger.info("worker tick")
        await asyncio.sleep(30)


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
