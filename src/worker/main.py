"""
Worker: consume Redis bars (and quotes, news), maintain per-symbol state,
evaluate INTRA_EVENT_MOMO, persist signals and shadow fills. Shadow-only: no Alpaca orders.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import redis.asyncio as redis
from stockbot.config import get_settings
from stockbot.db.session import get_session_factory
from stockbot.ledger.events import SignalEvent
from stockbot.ledger.store import LedgerStore
from stockbot.shadow.engine import (
    ShadowPosition,
    ShadowState,
    close_shadow_position,
    compute_entry_fill,
    compute_exit_fill,
    resolve_exit_conservative,
    ShadowFillParams,
)
from stockbot.strategies.intra_event_momo import (
    STRATEGY_ID,
    STRATEGY_VERSION,
    NewsItem,
    classify_news_side,
    evaluate,
    exit_stop_target_prices,
)
from stockbot.strategies.state import BarLike, SymbolState
from stockbot.gateways.market_gateway import (
    REDIS_STREAM_BARS,
    REDIS_STREAM_QUOTES,
    REDIS_STREAM_NEWS,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TRADED_TODAY_KEY = "stockbot:strategies:intra_event_momo:traded_today"
DAY_RESET_KEY = "stockbot:strategies:day_reset_done"


def _parse_bar_from_payload(payload: dict) -> BarLike | None:
    """Parse bar from gateway payload (serialized bar or raw)."""
    bar = payload.get("bar") or (payload.get("payload") or {}).get("bar")
    if not bar or not isinstance(bar, dict):
        return None
    ts = bar.get("timestamp")
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            ts = datetime.now(timezone.utc)
    else:
        ts = datetime.now(timezone.utc)
    return BarLike(
        symbol=bar.get("symbol", ""),
        open=Decimal(str(bar.get("o", bar.get("open", 0)))),
        high=Decimal(str(bar.get("h", bar.get("high", 0)))),
        low=Decimal(str(bar.get("l", bar.get("low", 0)))),
        close=Decimal(str(bar.get("c", bar.get("close", 0)))),
        volume=int(bar.get("v", bar.get("volume", 0))),
        timestamp=ts,
    )


def _parse_quote_from_payload(payload: dict) -> tuple[str, Decimal, Decimal, datetime] | None:
    """Return (symbol, bid, ask, ts) or None."""
    q = payload.get("quote") or payload.get("payload", {}).get("quote")
    if not q or not isinstance(q, dict):
        return None
    ts = q.get("timestamp")
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            ts = datetime.now(timezone.utc)
    else:
        ts = datetime.now(timezone.utc)
    return (
        q.get("symbol", ""),
        Decimal(str(q.get("bp", q.get("bid_price", 0)))),
        Decimal(str(q.get("ap", q.get("ask_price", 0)))),
        ts,
    )


def _parse_news_from_payload(payload: dict) -> NewsItem | None:
    """Parse news from gateway payload."""
    raw = payload.get("raw") or payload.get("payload", {}).get("raw") or payload
    if not isinstance(raw, dict):
        return None
    headline = raw.get("headline", "")
    summary = raw.get("summary", "") or raw.get("content", "")[:500]
    created = raw.get("created_at") or raw.get("updated_at")
    try:
        published = datetime.fromisoformat(created.replace("Z", "+00:00")) if created else datetime.now(timezone.utc)
    except Exception:
        published = datetime.now(timezone.utc)
    symbols = raw.get("symbols") or []
    sym = symbols[0] if symbols else None
    return NewsItem(headline=headline, summary=summary, published_at=published, symbol=sym, raw=raw)


async def run_worker() -> None:
    settings = get_settings()
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    universe = [s.strip() for s in settings.stockbot_universe.split(",") if s.strip()]
    if not universe:
        universe = ["AAPL", "SPY"]
    slippage_bps = settings.shadow_slippage_bps
    fee_per_share = Decimal(settings.shadow_fee_per_share)
    state: dict[str, SymbolState] = {sym: SymbolState(symbol=sym) for sym in universe}
    shadow_state = ShadowState()
    last_ids = {REDIS_STREAM_BARS: "0", REDIS_STREAM_QUOTES: "0", REDIS_STREAM_NEWS: "0"}

    while True:
        try:
            stream_map = {
                REDIS_STREAM_BARS: last_ids.get(REDIS_STREAM_BARS, "0"),
                REDIS_STREAM_QUOTES: last_ids.get(REDIS_STREAM_QUOTES, "0"),
                REDIS_STREAM_NEWS: last_ids.get(REDIS_STREAM_NEWS, "0"),
            }
            result = await redis_client.xread(streams=stream_map, count=100, block=5000)
            if not result:
                continue
            for stream_name, messages in result:
                for msg_id, fields in messages:
                    last_ids[stream_name] = msg_id
                    data = fields.get("data") if isinstance(fields, dict) else None
                    if not data:
                        continue
                    try:
                        body = json.loads(data)
                    except Exception:
                        continue
                    payload = body.get("payload", body)
                    if stream_name == REDIS_STREAM_BARS:
                        bar = _parse_bar_from_payload(payload)
                        if bar and bar.symbol in state:
                            s = state[bar.symbol]
                            if not s.prev_close and s.bars:
                                s.prev_close = s.bars[0].open
                            elif not s.prev_close:
                                s.prev_close = bar.open
                            s.bars.append(bar)
                            if len(s.bars) > 200:
                                s.bars = s.bars[-100:]
                            await _on_bar(redis_client, state[bar.symbol], shadow_state, settings, fee_per_share, slippage_bps)
                    elif stream_name == REDIS_STREAM_QUOTES:
                        q = _parse_quote_from_payload(payload)
                        if q:
                            sym, bid, ask, ts = q
                            if sym in state:
                                state[sym].latest_bid = bid
                                state[sym].latest_ask = ask
                                state[sym].latest_last = (bid + ask) / 2
                                state[sym].latest_quote_ts = ts
                    elif stream_name == REDIS_STREAM_NEWS:
                        news = _parse_news_from_payload(payload)
                        if news:
                            for sym in (news.symbol,) if news.symbol else universe:
                                if sym in state:
                                    state[sym].news.append(news)
                                    if len(state[sym].news) > 200:
                                        state[sym].news = state[sym].news[-100:]
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception("worker loop error: %s", e)
            await asyncio.sleep(5)


async def _on_bar(
    redis_client: redis.Redis,
    sym_state: SymbolState,
    shadow_state: ShadowState,
    settings: object,
    fee_per_share: Decimal,
    slippage_bps: int,
) -> None:
    """On new bar: update state, check exit for open position, then evaluate entry."""
    symbol = sym_state.symbol
    entry_start = getattr(settings, "entry_start_et", "09:35")
    entry_end = getattr(settings, "entry_end_et", "11:30")
    force_flat = getattr(settings, "force_flat_et", "15:45")

    # Check exit for open shadow position
    if shadow_state.has_position(symbol):
        pos = shadow_state.get_position(symbol)
        if pos and sym_state.last_bar():
            bar = sym_state.last_bar()
            exit_price_ideal, exit_reason = resolve_exit_conservative(
                pos.side, bar.high, bar.low, pos.stop_price, pos.target_price,
            )
            if exit_reason != "open":
                exit_price_realistic = compute_exit_fill(
                    pos.side,
                    sym_state.latest_bid or bar.close,
                    sym_state.latest_ask or bar.close,
                    ShadowFillParams("realistic", slippage_bps, fee_per_share),
                )
                exit_ts = bar.timestamp
                records = close_shadow_position(pos, exit_ts, exit_price_ideal, exit_price_realistic, exit_reason)
                factory = get_session_factory()
                async with factory() as session:
                    store = LedgerStore(session)
                    for rec in records:
                        await store.insert_shadow_trade(
                            signal_uuid=UUID(rec["signal_uuid"]),
                            execution_mode=rec["execution_mode"],
                            entry_ts=rec["entry_ts"],
                            exit_ts=rec["exit_ts"],
                            entry_price=rec["entry_price"],
                            exit_price=rec["exit_price"],
                            stop_price=rec["stop_price"],
                            target_price=rec["target_price"],
                            exit_reason=rec["exit_reason"],
                            qty=rec["qty"],
                            gross_pnl=rec["gross_pnl"],
                            net_pnl=rec["net_pnl"],
                            slippage_bps=rec["slippage_bps"],
                            fee_per_share=rec["fee_per_share"],
                        )
                shadow_state.close_position(symbol)
                logger.info("shadow exit symbol=%s exit_reason=%s", symbol, exit_reason)
        return

    # One trade per symbol per day
    traded = await redis_client.smembers(TRADED_TODAY_KEY)
    if symbol in traded:
        return

    or_high, or_low = sym_state.opening_range()
    if or_high is None:
        return
    prev_close = sym_state.prev_close or sym_state.bars[0].open if sym_state.bars else None
    if prev_close is None:
        return
    last_bar = sym_state.last_bar()
    if not last_bar:
        return
    close = last_bar.close
    gap_pct = ((close - prev_close) / prev_close * 100).quantize(Decimal("0.01")) if prev_close else Decimal("0")
    spread_bps = 0
    if sym_state.latest_bid and sym_state.latest_ask and sym_state.latest_ask > 0:
        spread_bps = int((sym_state.latest_ask - sym_state.latest_bid) / sym_state.latest_ask * 10000)
    minute_dollar = (last_bar.high + last_bar.low + last_bar.close) / 3 * last_bar.volume
    rel_vol = sym_state.rel_volume_5m()
    news_side = classify_news_side(sym_state.news, within_minutes=60)
    from stockbot.strategies.intra_event_momo import news_keyword_hits
    all_pos: list[str] = []
    all_neg: list[str] = []
    for n in sym_state.news[-20:]:
        p, neg = news_keyword_hits(n.headline + " " + n.summary)
        all_pos.extend(p)
        all_neg.extend(neg)
    keyword_hits = list(set(all_pos + all_neg))

    from stockbot.strategies.intra_event_momo import FeatureSet
    features = FeatureSet(
        symbol=symbol,
        ts=last_bar.timestamp,
        prev_close=prev_close,
        gap_pct_from_prev_close=gap_pct,
        spread_bps=spread_bps,
        minute_dollar_volume=minute_dollar,
        rel_volume_5m=rel_vol,
        opening_range_high=or_high,
        opening_range_low=or_low,
        session_vwap=sym_state.session_vwap(),
        latest_bid=sym_state.latest_bid,
        latest_ask=sym_state.latest_ask,
        latest_last=sym_state.latest_last,
        latest_minute_close=close,
        news_side=news_side,
        news_keyword_hits=keyword_hits,
    )
    eval_result = evaluate(features, entry_start_et=entry_start, entry_end_et=entry_end, force_flat_et=force_flat)
    if eval_result.side is None or not eval_result.passes_filters:
        return
    bid = sym_state.latest_bid or close
    ask = sym_state.latest_ask or close
    if not bid or not ask:
        return
    signal_uuid = uuid4()
    qty = Decimal("100")
    ideal_entry = compute_entry_fill(eval_result.side, bid, ask, ShadowFillParams("ideal", 0, Decimal("0")))
    real_entry = compute_entry_fill(eval_result.side, bid, ask, ShadowFillParams("realistic", slippage_bps, fee_per_share))
    stop_price, target_price = exit_stop_target_prices(eval_result.side, or_high, or_low, real_entry, 2.0)
    factory = get_session_factory()
    async with factory() as session:
        store = LedgerStore(session)
        event = SignalEvent(
            signal_uuid=signal_uuid,
            symbol=symbol,
            side="buy" if eval_result.side == "buy" else "sell",
            qty=qty,
            strategy_id=STRATEGY_ID,
            strategy_version=STRATEGY_VERSION,
            feed="iex",
            quote_ts=last_bar.timestamp,
            ingest_ts=datetime.now(timezone.utc),
            bid=bid,
            ask=ask,
            last=sym_state.latest_last,
            spread_bps=spread_bps,
            latency_ms=None,
            reason_codes=eval_result.reason_codes,
            feature_snapshot_json=eval_result.feature_snapshot,
            quote_snapshot_json={"bid": str(bid), "ask": str(ask), "last": str(sym_state.latest_last)},
            news_snapshot_json={"news_side": news_side, "keyword_hits": keyword_hits},
        )
        await store.insert_signal(event)
    shadow_state.open_position(ShadowPosition(
        signal_uuid=signal_uuid,
        symbol=symbol,
        side="buy" if eval_result.side == "buy" else "sell",
        qty=qty,
        entry_ts=last_bar.timestamp,
        ideal_entry_price=ideal_entry,
        realistic_entry_price=real_entry,
        stop_price=stop_price,
        target_price=target_price,
        slippage_bps=slippage_bps,
        fee_per_share=fee_per_share,
    ))
    await redis_client.sadd(TRADED_TODAY_KEY, symbol)
    logger.info("signal symbol=%s side=%s signal_uuid=%s", symbol, eval_result.side, signal_uuid)


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
