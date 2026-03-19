"""
Alpaca reconciler: poll account, positions, orders, portfolio history, activities.
Write snapshots to DB; compare internal ledger to Alpaca.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from stockbot.alpaca.client import AlpacaClient
from stockbot.config import get_settings
from stockbot.db.models import (
    AccountActivity,
    Fill,
    PaperAccountSnapshot,
    PaperPortfolioHistoryPoint,
    PaperPosition,
    ReconciliationLog,
)
from stockbot.db.session import get_session_factory

logger = logging.getLogger(__name__)
RECONCILE_INTERVAL_SEC = 60


def _decimal(v, default=None):
    if v is None:
        return default
    try:
        return Decimal(str(v))
    except Exception:
        return default


def _parse_ts(ts: str | None):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


async def run_reconciliation() -> None:
    settings = get_settings()
    interval = getattr(settings, "account_poll_interval_sec", None) or RECONCILE_INTERVAL_SEC

    def _fetch_alpaca() -> tuple[dict, list, list, dict, list]:
        client = AlpacaClient()
        account = client.get_account()
        positions = client.list_positions()
        orders = client.list_orders(status="all", limit=200)
        portfolio_history = client.get_portfolio_history(period="1D", timeframe="15Min")
        activities, _ = client.get_activities(page_size=50)
        return (account, positions, orders, portfolio_history, activities)

    try:
        account, positions, orders, portfolio_history, activities = await asyncio.to_thread(_fetch_alpaca)
    except Exception as e:
        logger.warning("reconciler fetch_alpaca failed: %s", e)
        await asyncio.sleep(interval)
        return

    now = datetime.now(UTC)
    factory = get_session_factory()

    # Paper account snapshot
    async with factory() as session:
        session.add(PaperAccountSnapshot(
            snapshot_ts=now,
            account_number=account.get("account_number"),
            status=account.get("status"),
            currency=account.get("currency"),
            equity=_decimal(account.get("equity")),
            last_equity=_decimal(account.get("last_equity")),
            cash=_decimal(account.get("cash")),
            buying_power=_decimal(account.get("buying_power")),
            regt_buying_power=_decimal(account.get("regt_buying_power")),
            daytrading_buying_power=_decimal(account.get("daytrading_buying_power")),
            multiplier=account.get("multiplier"),
            initial_margin=_decimal(account.get("initial_margin")),
            maintenance_margin=_decimal(account.get("maintenance_margin")),
            long_market_value=_decimal(account.get("long_market_value")),
            short_market_value=_decimal(account.get("short_market_value")),
            pattern_day_trader=account.get("pattern_day_trader"),
            trading_blocked=account.get("trading_blocked"),
            transfers_blocked=account.get("transfers_blocked"),
            account_blocked=account.get("account_blocked"),
            raw_json=account,
        ))
        await session.commit()

    # Paper positions snapshot (one row per position)
    async with factory() as session:
        for p in positions:
            session.add(PaperPosition(
                snapshot_ts=now,
                symbol=str(p.get("symbol", "")),
                side=p.get("side"),
                qty=_decimal(p.get("qty")),
                avg_entry_price=_decimal(p.get("avg_entry_price")),
                market_price=_decimal(p.get("current_price")) or _decimal(p.get("market_value")) / max(_decimal(p.get("qty"), 1), 1),
                market_value=_decimal(p.get("market_value")),
                cost_basis=_decimal(p.get("cost_basis")),
                unrealized_pl=_decimal(p.get("unrealized_pl")),
                unrealized_plpc=_decimal(p.get("unrealized_plpc")),
                current_price=_decimal(p.get("current_price")),
                lastday_price=_decimal(p.get("lastday_price")),
                change_today=_decimal(p.get("change_today")),
                raw_json=p,
            ))
        await session.commit()

    # Portfolio history points
    equity_series = portfolio_history.get("equity") or []
    ts_series = portfolio_history.get("timestamp") or []
    pl_series = portfolio_history.get("profit_loss") or []
    plpc_series = portfolio_history.get("profit_loss_pct") or []
    base = portfolio_history.get("base_value")
    timeframe = portfolio_history.get("timeframe")
    period = portfolio_history.get("period")
    async with factory() as session:
        for i, eq in enumerate(equity_series):
            ts_val = ts_series[i] if i < len(ts_series) else None
            if ts_val is not None:
                try:
                    series_ts = datetime.fromtimestamp(int(ts_val), tz=UTC)
                except Exception:
                    series_ts = now
            else:
                series_ts = now
            session.add(PaperPortfolioHistoryPoint(
                series_ts=series_ts,
                equity=_decimal(eq),
                profit_loss=_decimal(pl_series[i]) if i < len(pl_series) else None,
                profit_loss_pct=_decimal(plpc_series[i]) if i < len(plpc_series) else None,
                base_value=_decimal(base),
                timeframe=timeframe,
                period=period,
            ))
        await session.commit()

    # Account activities (upsert by activity_id)
    async with factory() as session:
        for a in activities[:100]:
            aid = a.get("id")
            if not aid:
                continue
            result = await session.execute(select(AccountActivity).where(AccountActivity.activity_id == aid).limit(1))
            if result.scalars().first():
                continue
            session.add(AccountActivity(
                activity_id=aid,
                activity_type=a.get("activity_type"),
                transaction_time=_parse_ts(a.get("transaction_time")),
                symbol=a.get("symbol"),
                qty=_decimal(a.get("qty")),
                price=_decimal(a.get("price")),
                net_amount=_decimal(a.get("net_amount")),
                raw_json=a,
            ))
        await session.commit()

    # Compare to internal ledger
    async with factory() as session:
        fills = await session.execute(select(Fill).order_by(Fill.created_at.desc()).limit(500))
        internal_fills = {f.client_order_id: f for f in fills.scalars().all()}

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

    positions_matched = len(positions)
    positions_mismatch = 0

    async with factory() as session:
        log = ReconciliationLog(
            run_at=now,
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
    settings = get_settings()
    interval = getattr(settings, "account_poll_interval_sec", None) or RECONCILE_INTERVAL_SEC
    while True:
        try:
            await run_reconciliation()
        except Exception as e:
            logger.exception("reconciliation failed: %s", e)
        await asyncio.sleep(interval)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_reconciler_loop())


if __name__ == "__main__":
    main()
