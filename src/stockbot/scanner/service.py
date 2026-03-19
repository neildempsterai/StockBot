"""Scanner service: run scan, persist, publish to Redis, update Scrappy watchlist."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Callable, Awaitable

import redis.asyncio as redis

from stockbot.alpaca.client import AlpacaClient
from stockbot.config import get_settings
from stockbot.db.session import get_session_factory
from stockbot.scanner.ranking import rank_candidate, select_top_candidates
from stockbot.scanner.store import (
    create_scanner_run,
    get_latest_toplist_snapshot,
    insert_scanner_candidates,
    insert_toplist_snapshot,
)
from stockbot.scanner.types import ScannerCandidate, ScannerRunResult
from stockbot.scanner.universe import build_universe

logger = logging.getLogger(__name__)

REDIS_KEY_SCANNER_TOP = "stockbot:scanner:top_symbols"
REDIS_KEY_SCANNER_TOP_TS = "stockbot:scanner:top_updated_at"
REDIS_KEY_SCANNER_RUN_ID = "stockbot:scanner:latest_run_id"
REDIS_TTL_TOP_SEC = 86400 * 2


async def _get_scrappy_snapshot_for_symbol(session_factory: Any, symbol: str) -> tuple[bool, str | None]:
    """Return (scrappy_present, catalyst_direction)."""
    try:
        from stockbot.scrappy.store import get_latest_snapshot_by_symbol
        async with session_factory() as session:
            snap = await get_latest_snapshot_by_symbol(session, symbol)
            if not snap:
                return (False, None)
            direction = getattr(snap, "catalyst_direction", None) or getattr(snap, "catalyst_strength", None)
            return (True, str(direction) if direction is not None else "neutral")
    except Exception:
        return (False, None)


async def _news_count_for_symbols(client: AlpacaClient, symbols: list[str], lookback_min: int) -> dict[str, int]:
    """Return symbol -> count of news in lookback window."""
    out: dict[str, int] = {s: 0 for s in symbols}
    if not symbols:
        return out
    from datetime import timedelta
    end = datetime.now(UTC)
    start = end - timedelta(minutes=lookback_min)
    try:
        news, _ = client.get_news(
            symbols=symbols,
            start=start.isoformat(),
            end=end.isoformat(),
            limit=100,
        )
        for article in news or []:
            for sym in article.get("symbols") or []:
                if sym in out:
                    out[sym] = out.get(sym, 0) + 1
    except Exception as e:
        logger.warning("scanner news fetch failed: %s", e)
    return out


def _market_session_et() -> str:
    try:
        import zoneinfo
        et = zoneinfo.ZoneInfo("America/New_York")
        now = datetime.now(UTC).astimezone(et)
        h, m = now.hour, now.minute
        if h < 9 or (h == 9 and m < 30):
            return "premarket"
        if h >= 16:
            return "after_hours"
        return "regular"
    except Exception:
        return "unknown"


async def run_scan(
    *,
    get_watchlist_fn: Callable[[], Awaitable[list[str]]] | None = None,
    session_factory: Any | None = None,
) -> ScannerRunResult:
    """
    Run one full scan: build universe, fetch snapshots, rank, persist run+candidates+toplist.
    Does not publish to Redis or update Scrappy; caller can do that after.
    """
    settings = get_settings()
    mode = getattr(settings, "scanner_mode", "dynamic")
    universe_mode = getattr(settings, "scanner_universe_mode", "liquid_us_equities")
    top_n = getattr(settings, "scanner_top_candidates", 25)
    min_price = getattr(settings, "scanner_min_price", 5.0)
    max_price = getattr(settings, "scanner_max_price", 2000.0)
    min_dollar_volume = getattr(settings, "scanner_min_dollar_volume_1m", 1_000_000.0)
    min_rvol = getattr(settings, "scanner_min_rvol_5m", 0.3)
    max_spread_bps = getattr(settings, "scanner_max_spread_bps", 100)
    min_gap_pct = getattr(settings, "scanner_min_gap_pct", -10.0)
    require_news = getattr(settings, "scanner_require_news", False)
    require_scrappy = getattr(settings, "scanner_require_scrappy", False)
    news_lookback = getattr(settings, "scanner_news_lookback_minutes", 60)

    universe = await build_universe(mode, universe_mode, get_watchlist_fn=get_watchlist_fn)
    if not universe:
        universe = [s.strip() for s in (settings.stockbot_universe or "AAPL,SPY").split(",") if s.strip()]
    if not universe:
        return ScannerRunResult(
            run_id="",
            run_ts=datetime.now(UTC),
            mode=mode,
            universe_mode=universe_mode,
            universe_size=0,
            candidates_scored=0,
            top_candidates_count=0,
            market_session=_market_session_et(),
            status="no_universe",
            notes="No symbols in universe",
            candidates=[],
        )

    client = AlpacaClient()
    snapshots = client.get_stock_snapshots(universe)
    news_counts = await _news_count_for_symbols(client, universe, news_lookback)
    factory = session_factory or get_session_factory()
    scrappy_cache: dict[str, tuple[bool, str | None]] = {}
    for sym in universe:
        scrappy_cache[sym] = await _get_scrappy_snapshot_for_symbol(factory, sym)

    candidates: list[ScannerCandidate] = []
    for symbol in universe:
        snap = snapshots.get(symbol)
        prev_close = None
        if snap and snap.prev_daily_bar:
            prev_close = snap.prev_daily_bar.close
        elif snap and snap.daily_bar:
            prev_close = snap.daily_bar.open
        dollar_vol = None
        rvol = None
        if snap and snap.daily_bar and snap.daily_bar.volume:
            v = snap.daily_bar.volume
            p = float(_price(snap) or 0)
            if p > 0:
                dollar_vol = v * p
            rvol = 1.0
        sp, sc = scrappy_cache.get(symbol, (False, None))
        c = rank_candidate(
            symbol,
            snap,
            prev_close=prev_close,
            dollar_volume_1m=dollar_vol,
            rvol_5m=rvol,
            news_count=news_counts.get(symbol, 0),
            scrappy_present=sp,
            scrappy_catalyst_direction=sc,
            min_price=min_price,
            max_price=max_price,
            min_dollar_volume_1m=min_dollar_volume,
            min_rvol_5m=min_rvol,
            max_spread_bps=max_spread_bps,
            min_gap_pct=min_gap_pct,
            require_news=require_news,
            require_scrappy=require_scrappy,
        )
        candidates.append(c)

    top = select_top_candidates(candidates, top_n)
    run_id = str(uuid.uuid4())
    run_ts = datetime.now(UTC)
    session_label = _market_session_et()

    async with factory() as session:
        await create_scanner_run(
            session,
            run_id=run_id,
            run_ts=run_ts,
            mode=mode,
            universe_mode=universe_mode,
            universe_size=len(universe),
            candidates_scored=len(candidates),
            top_candidates_count=len(top),
            market_session=session_label,
            status="completed",
            notes=None,
        )
        await insert_scanner_candidates(session, run_id, candidates)
        await insert_toplist_snapshot(session, run_ts, [c.symbol for c in top], run_id)
        await session.commit()

    return ScannerRunResult(
        run_id=run_id,
        run_ts=run_ts,
        mode=mode,
        universe_mode=universe_mode,
        universe_size=len(universe),
        candidates_scored=len(candidates),
        top_candidates_count=len(top),
        market_session=session_label,
        status="completed",
        notes=None,
        candidates=top,
    )


def _price(snap: Any) -> Decimal | None:
    if not snap:
        return None
    if getattr(snap, "latest_trade", None):
        return snap.latest_trade.price
    if getattr(snap, "latest_quote", None):
        q = snap.latest_quote
        return (q.bid_price + q.ask_price) / 2
    if getattr(snap, "daily_bar", None):
        return snap.daily_bar.close
    return None


async def publish_top_to_redis(symbols: list[str], run_id: str) -> None:
    """Write top symbols and run_id to Redis for worker consumption."""
    try:
        settings = get_settings()
        r = redis.from_url(settings.redis_url, decode_responses=True)
        await r.set(REDIS_KEY_SCANNER_TOP, json.dumps(symbols), ex=REDIS_TTL_TOP_SEC)
        await r.set(REDIS_KEY_SCANNER_TOP_TS, datetime.now(UTC).isoformat(), ex=REDIS_TTL_TOP_SEC)
        await r.set(REDIS_KEY_SCANNER_RUN_ID, run_id, ex=REDIS_TTL_TOP_SEC)
        await r.aclose()
    except Exception as e:
        logger.warning("scanner publish to Redis failed: %s", e)


async def update_scrappy_watchlist_from_top(symbols: list[str], max_symbols: int = 30) -> None:
    """Add top scanner symbols to Scrappy watchlist (source=scanner); cap size."""
    if not symbols:
        return
    to_add = symbols[:max_symbols]
    try:
        from stockbot.scrappy.store import add_watchlist_symbol
        factory = get_session_factory()
        async with factory() as session:
            for sym in to_add:
                await add_watchlist_symbol(session, sym.strip().upper()[:32], source="scanner")
            await session.commit()
    except Exception as e:
        logger.warning("scanner update Scrappy watchlist failed: %s", e)


async def run_scan_and_publish(
    get_watchlist_fn: Callable[[], Awaitable[list[str]]] | None = None,
) -> ScannerRunResult:
    """Run scan, persist, merge with opportunity engine (if enabled), publish to Redis, update Scrappy watchlist."""
    result = await run_scan(get_watchlist_fn=get_watchlist_fn)
    if result.candidates:
        settings = get_settings()
        if getattr(settings, "opportunity_engine_enabled", True):
            try:
                from stockbot.opportunities.service import merge_and_publish
                top_symbols = await merge_and_publish(result, result.run_id)
            except Exception as e:
                logger.warning("opportunity merge_and_publish failed, using scanner top: %s", e)
                top_symbols = [c.symbol for c in result.candidates]
                await publish_top_to_redis(top_symbols, result.run_id)
        else:
            top_symbols = [c.symbol for c in result.candidates]
            await publish_top_to_redis(top_symbols, result.run_id)
        max_scrappy = getattr(settings, "scanner_max_scrappy_symbols", 30)
        await update_scrappy_watchlist_from_top(top_symbols, max_symbols=max_scrappy)
    return result
