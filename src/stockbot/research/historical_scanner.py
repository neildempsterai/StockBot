"""Historical scanner run: rank symbols over past days using Alpaca bars; persist for research."""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from stockbot.alpaca.client import AlpacaClient
from stockbot.config import get_settings
from stockbot.db.session import get_session_factory
from stockbot.scanner.ranking import rank_candidate, select_top_candidates
from stockbot.scanner.store import (
    create_scanner_run,
    insert_scanner_candidates,
    insert_toplist_snapshot,
)
from stockbot.scanner.types import ScannerCandidate
from stockbot.alpaca.types import Bar, Snapshot

logger = logging.getLogger(__name__)


def _trading_days(end_date: datetime, days: int) -> list[datetime]:
    """Return list of trading day dates (UTC midnight) for the last `days` calendar days."""
    out: list[datetime] = []
    d = end_date.date() if hasattr(end_date, "date") else end_date
    for _ in range(days):
        out.append(datetime(d.year, d.month, d.day, tzinfo=UTC))
        d = d - timedelta(days=1)
    return out


def _snapshot_from_bar(symbol: str, bar: Bar, prev_close: Decimal | None) -> Snapshot:
    """Build minimal Snapshot from one bar (for historical ranking)."""
    return Snapshot(
        symbol=symbol,
        latest_trade=None,
        latest_quote=None,
        minute_bar=bar,
        daily_bar=bar,
        prev_daily_bar=Bar(symbol=symbol, open=prev_close or bar.open, high=bar.high, low=bar.low, close=prev_close or bar.close, volume=0, timestamp=bar.timestamp, feed=bar.feed) if prev_close else None,
        feed=bar.feed,
    )


async def run_historical_scanner(
    lookback_days: int = 30,
    symbols: list[str] | None = None,
    end_date: datetime | None = None,
) -> list[str]:
    """
    Run scanner logic over historical bars for each trading day in [end_date - lookback_days, end_date].
    Persists one scanner_run per day; returns list of run_ids.
    """
    settings = get_settings()
    if not symbols:
        raw = getattr(settings, "backtest_default_universe", settings.stockbot_universe) or "AAPL,SPY"
        symbols = [s.strip() for s in raw.split(",") if s.strip()]
    if not symbols:
        symbols = ["AAPL", "SPY"]
    end = end_date or datetime.now(UTC)
    days = _trading_days(end, lookback_days)
    client = AlpacaClient()
    top_n = getattr(settings, "scanner_top_candidates", 25)
    min_price = getattr(settings, "scanner_min_price", 5.0)
    max_price = getattr(settings, "scanner_max_price", 2000.0)
    min_dollar_volume = getattr(settings, "scanner_min_dollar_volume_1m", 1_000_000.0)
    min_rvol = getattr(settings, "scanner_min_rvol_5m", 0.3)
    max_spread_bps = getattr(settings, "scanner_max_spread_bps", 100)
    min_gap_pct = getattr(settings, "scanner_min_gap_pct", -10.0)
    run_ids: list[str] = []
    factory = get_session_factory()

    for day_start in days:
        start_str = day_start.isoformat()
        end_day = day_start + timedelta(hours=23, minutes=59)
        end_str = end_day.isoformat()
        try:
            bars, _ = client.get_bars(symbols, start=start_str, end=end_str, timeframe="1Day", limit=1000)
        except Exception as e:
            logger.warning("historical_scanner get_bars failed for %s: %s", start_str[:10], e)
            continue
        by_symbol: dict[str, list[Bar]] = {}
        for b in bars:
            by_symbol.setdefault(b.symbol, []).append(b)
        prev_closes: dict[str, Decimal] = {}
        candidates: list[ScannerCandidate] = []
        for sym in symbols:
            sym_bars = by_symbol.get(sym, [])
            if not sym_bars:
                continue
            bar = sym_bars[-1]
            prev_close = prev_closes.get(sym)
            snap = _snapshot_from_bar(sym, bar, prev_close)
            dollar_vol = float(bar.close * bar.volume) if bar.volume else None
            c = rank_candidate(
                sym,
                snap,
                prev_close=prev_close or bar.open,
                dollar_volume_1m=dollar_vol,
                rvol_5m=1.0,
                min_price=min_price,
                max_price=max_price,
                min_dollar_volume_1m=min_dollar_volume,
                min_rvol_5m=min_rvol,
                max_spread_bps=max_spread_bps,
                min_gap_pct=min_gap_pct,
            )
            candidates.append(c)
            prev_closes[sym] = bar.close
        top = select_top_candidates(candidates, top_n)
        run_id = "hist_" + str(uuid.uuid4())
        run_ts = day_start
        async with factory() as session:
            await create_scanner_run(
                session,
                run_id=run_id,
                run_ts=run_ts,
                mode="historical",
                universe_mode="custom",
                universe_size=len(symbols),
                candidates_scored=len(candidates),
                top_candidates_count=len(top),
                market_session="historical",
                status="completed",
                notes=f"lookback_days={lookback_days}",
            )
            await insert_scanner_candidates(session, run_id, candidates)
            await insert_toplist_snapshot(session, run_ts, [c.symbol for c in top], run_id)
            await session.commit()
        run_ids.append(run_id)
    return run_ids
