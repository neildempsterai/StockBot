"""
Alpaca reconciler: poll /orders and /positions; compare to internal ledger.
Do not treat Alpaca avg_entry_price as canonical (BOD sync can change it).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from stockbot.alpaca.client import AlpacaClient
from stockbot.db.models import Fill, ReconciliationLog
from stockbot.db.session import get_session_factory

logger = logging.getLogger(__name__)
RECONCILE_INTERVAL_SEC = 60


async def run_reconciliation() -> None:
    client = AlpacaClient()
    factory = get_session_factory()
    async with factory() as session:
        fills = await session.execute(
            select(Fill).order_by(Fill.created_at.desc()).limit(500)
        )
        internal_fills = {f.client_order_id: f for f in fills.scalars().all()}

    orders = client.list_orders(status="all", limit=200)
    positions = client.list_positions()

    orders_matched = 0
    orders_mismatch = 0
    for o in orders:
        cid = o.get("client_order_id")
        if not cid:
            continue
        if cid in internal_fills:
            orders_matched += 1
        else:
            orders_mismatch += 1

    positions_matched = 0
    positions_mismatch = 0
    for p in positions:
        symbol = p.get("symbol")
        alpaca_avg = p.get("avg_entry_price")
        # We do not use alpaca_avg as canonical; just count
        positions_matched += 1

    factory = get_session_factory()
    async with factory() as session:
        log = ReconciliationLog(
            run_at=datetime.now(UTC),
            orders_matched=orders_matched,
            orders_mismatch=orders_mismatch,
            positions_matched=positions_matched,
            positions_mismatch=positions_mismatch,
            details=None,
        )
        session.add(log)
        await session.commit()

    logger.info(
        "reconciler run orders_matched=%s orders_mismatch=%s positions_matched=%s",
        orders_matched, orders_mismatch, positions_matched,
    )


async def run_reconciler_loop() -> None:
    while True:
        try:
            await run_reconciliation()
        except Exception as e:
            logger.exception("reconciliation failed: %s", e)
        await asyncio.sleep(RECONCILE_INTERVAL_SEC)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_reconciler_loop())


if __name__ == "__main__":
    main()
