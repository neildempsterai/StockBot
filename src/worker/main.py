"""
Worker: INTRA_EVENT_MOMO / 0.1.0 end-to-end strategy runtime.
Consumes Redis streams (bars, quotes, trades, news), maintains per-symbol state,
evaluates on completed minute bars, persists signals and shadow trades.
Shadow-only: no Alpaca orders. One trade max per symbol per day. Force flat by 15:45 ET.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import redis.asyncio as redis
from stockbot.config import get_settings
from stockbot.db.session import get_session_factory
from stockbot.ledger.events import SignalEvent
from stockbot.ledger.store import LedgerStore
from stockbot.shadow.engine import (
    ShadowFillParams,
    ShadowPosition,
    ShadowState,
    close_shadow_position,
    compute_entry_fill,
    compute_exit_fill,
    resolve_exit_conservative,
)
from stockbot.strategies.intra_event_momo import (
    STRATEGY_ID,
    STRATEGY_VERSION,
    NewsItem,
    classify_news_side,
    evaluate,
    exit_stop_target_prices,
    news_keyword_hits,
)
from stockbot.strategies.intra_event_momo import FeatureSet
from stockbot.strategies.state import BarLike, SymbolState
from stockbot.gateways.market_gateway import (
    REDIS_STREAM_BARS,
    REDIS_STREAM_QUOTES,
    REDIS_STREAM_TRADES,
    REDIS_STREAM_NEWS,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TRADED_TODAY_KEY = "stockbot:strategies:intra_event_momo:traded_today"
REDIS_LAST_IDS_KEY = "stockbot:worker:intra_event_momo:last_ids"
HEARTBEAT_KEY = "stockbot:worker:heartbeat"
HEARTBEAT_TTL_SEC = 60
HEARTBEAT_INTERVAL_SEC = 30
EVENT_COUNTS_LOG_INTERVAL = 500


def scrappy_gate_check(
    snapshot_row: Any,
    side: str,
    scrappy_mode: str,
) -> str | None:
    """
    Deterministic Scrappy gate: returns rejection reason_code or None if allowed.
    Used by _on_bar; testable in isolation.
    """
    mode = (scrappy_mode or "advisory").strip().lower()
    if mode == "off":
        return None
    if side != "buy" and side != "sell":
        return None
    if mode == "required" and snapshot_row is None:
        return "scrappy_missing"
    if snapshot_row and getattr(snapshot_row, "stale_flag", False):
        return "scrappy_stale"
    if snapshot_row and getattr(snapshot_row, "conflict_flag", False):
        return "scrappy_conflict"
    direction = getattr(snapshot_row, "catalyst_direction", "neutral") if snapshot_row else "neutral"
    if side == "buy" and direction == "negative":
        return "scrappy_negative"
    if side == "sell" and direction == "positive":
        return "scrappy_positive"
    return None


def _et_time_after(ts: datetime, et_time: str) -> bool:
    """True if ts (UTC) is at or after et_time in America/New_York."""
    try:
        import zoneinfo
        et = zoneinfo.ZoneInfo("America/New_York")
        local = ts.astimezone(et)
        t_str = local.strftime("%H:%M")
        return t_str >= et_time
    except Exception:
        return False


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
    q = payload.get("quote") or (payload.get("payload") or {}).get("quote")
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
    bid = q.get("bp") if "bp" in q else q.get("bid_price", 0)
    ask = q.get("ap") if "ap" in q else q.get("ask_price", 0)
    return (
        q.get("symbol", ""),
        Decimal(str(bid)),
        Decimal(str(ask)),
        ts,
    )


def _parse_trade_from_payload(payload: dict) -> tuple[str, Decimal, datetime] | None:
    """Return (symbol, price, ts) or None."""
    t = payload.get("trade") or (payload.get("payload") or {}).get("trade")
    if not t or not isinstance(t, dict):
        return None
    ts = t.get("timestamp")
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            ts = datetime.now(timezone.utc)
    else:
        ts = datetime.now(timezone.utc)
    return (
        t.get("symbol", ""),
        Decimal(str(t.get("price", t.get("p", 0)))),
        ts,
    )


def _parse_news_from_payload(payload: dict) -> NewsItem | None:
    """Parse news from gateway payload."""
    raw = payload.get("raw") or (payload.get("payload") or {}).get("raw") or payload
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


async def _load_last_ids(redis_client: redis.Redis) -> dict[str, str]:
    """Load last stream IDs from Redis for restart safety."""
    try:
        raw = await redis_client.get(REDIS_LAST_IDS_KEY)
        if raw:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {
        REDIS_STREAM_BARS: "0",
        REDIS_STREAM_QUOTES: "0",
        REDIS_STREAM_TRADES: "0",
        REDIS_STREAM_NEWS: "0",
    }


async def _save_last_ids(redis_client: redis.Redis, last_ids: dict[str, str]) -> None:
    """Persist last stream IDs so restarts do not double-process."""
    try:
        await redis_client.set(REDIS_LAST_IDS_KEY, json.dumps(last_ids), ex=86400 * 7)
    except Exception:
        pass


async def run_worker() -> None:
    settings = get_settings()
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    universe = [s.strip() for s in settings.stockbot_universe.split(",") if s.strip()]
    if not universe:
        universe = ["AAPL", "SPY"]
    universe_set = frozenset(universe)

    logger.info(
        "worker_connected strategy=%s version=%s universe_size=%s feed=iex",
        STRATEGY_ID, STRATEGY_VERSION, len(universe),
    )

    slippage_bps = settings.shadow_slippage_bps
    fee_per_share = Decimal(settings.shadow_fee_per_share)
    state: dict[str, SymbolState] = {sym: SymbolState(symbol=sym) for sym in universe}
    shadow_state = ShadowState()
    last_ids = await _load_last_ids(redis_client)
    event_counts: dict[str, int] = {"bars": 0, "quotes": 0, "trades": 0, "news": 0}
    last_heartbeat = 0.0
    total_events = 0

    while True:
        try:
            if time.monotonic() - last_heartbeat >= HEARTBEAT_INTERVAL_SEC:
                try:
                    await redis_client.set(
                        HEARTBEAT_KEY,
                        datetime.now(timezone.utc).isoformat(),
                        ex=HEARTBEAT_TTL_SEC,
                    )
                    last_heartbeat = time.monotonic()
                except Exception:
                    pass

            stream_map = {
                REDIS_STREAM_BARS: last_ids.get(REDIS_STREAM_BARS, "0"),
                REDIS_STREAM_QUOTES: last_ids.get(REDIS_STREAM_QUOTES, "0"),
                REDIS_STREAM_TRADES: last_ids.get(REDIS_STREAM_TRADES, "0"),
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
                        event_counts["bars"] += 1
                        bar = _parse_bar_from_payload(payload)
                        if bar and bar.symbol in universe_set:
                            s = state[bar.symbol]
                            if not s.prev_close and s.bars:
                                s.prev_close = s.bars[0].open
                            elif not s.prev_close:
                                s.prev_close = bar.open
                            s.bars.append(bar)
                            if len(s.bars) > 200:
                                s.bars = s.bars[-100:]
                            await _on_bar(
                                redis_client, state[bar.symbol], shadow_state,
                                settings, fee_per_share, slippage_bps,
                            )
                    elif stream_name == REDIS_STREAM_QUOTES:
                        event_counts["quotes"] += 1
                        q = _parse_quote_from_payload(payload)
                        if q:
                            sym, bid, ask, ts = q
                            if sym in universe_set:
                                state[sym].latest_bid = bid
                                state[sym].latest_ask = ask
                                state[sym].latest_last = (bid + ask) / 2
                                state[sym].latest_quote_ts = ts
                    elif stream_name == REDIS_STREAM_TRADES:
                        event_counts["trades"] += 1
                        t = _parse_trade_from_payload(payload)
                        if t:
                            sym, price, ts = t
                            if sym in universe_set:
                                state[sym].latest_last = price
                    elif stream_name == REDIS_STREAM_NEWS:
                        event_counts["news"] += 1
                        news = _parse_news_from_payload(payload)
                        if news:
                            for sym in (news.symbol,) if news.symbol else universe:
                                if sym in universe_set:
                                    state[sym].news.append(news)
                                    if len(state[sym].news) > 200:
                                        state[sym].news = state[sym].news[-100:]

            total_events += sum(len(m) for _, m in result)
            if total_events >= EVENT_COUNTS_LOG_INTERVAL:
                logger.info(
                    "event_counts bars=%s quotes=%s trades=%s news=%s",
                    event_counts["bars"], event_counts["quotes"], event_counts["trades"], event_counts["news"],
                )
                total_events = 0

            await _save_last_ids(redis_client, last_ids)

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
    """On completed minute bar: force-flat check, exit check, then entry evaluation."""
    symbol = sym_state.symbol
    entry_start = getattr(settings, "entry_start_et", "09:35")
    entry_end = getattr(settings, "entry_end_et", "11:30")
    force_flat = getattr(settings, "force_flat_et", "15:45")

    last_bar = sym_state.last_bar()
    if not last_bar:
        return

    # Force flat at or after force_flat_et: close any open position at market
    if _et_time_after(last_bar.timestamp, force_flat) and shadow_state.has_position(symbol):
        pos = shadow_state.get_position(symbol)
        if pos:
            bid = sym_state.latest_bid or last_bar.close
            ask = sym_state.latest_ask or last_bar.close
            exit_price_ideal = compute_exit_fill(pos.side, bid, ask, ShadowFillParams("ideal", 0, Decimal("0")))
            exit_price_realistic = compute_exit_fill(
                pos.side, bid, ask, ShadowFillParams("realistic", slippage_bps, fee_per_share),
            )
            exit_ts = last_bar.timestamp
            records = close_shadow_position(pos, exit_ts, exit_price_ideal, exit_price_realistic, "force_flat")
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
            logger.info(
                "shadow_closed symbol=%s exit_reason=force_flat signal_uuid=%s",
                symbol, str(pos.signal_uuid),
            )
        return

    # Check stop/target exit for open shadow position
    if shadow_state.has_position(symbol):
        pos = shadow_state.get_position(symbol)
        if pos and last_bar:
            exit_price_ideal, exit_reason = resolve_exit_conservative(
                pos.side, last_bar.high, last_bar.low, pos.stop_price, pos.target_price,
            )
            if exit_reason != "open":
                exit_price_realistic = compute_exit_fill(
                    pos.side,
                    sym_state.latest_bid or last_bar.close,
                    sym_state.latest_ask or last_bar.close,
                    ShadowFillParams("realistic", slippage_bps, fee_per_share),
                )
                exit_ts = last_bar.timestamp
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
                logger.info(
                    "shadow_closed symbol=%s exit_reason=%s signal_uuid=%s",
                    symbol, exit_reason, str(pos.signal_uuid),
                )
        return

    # One trade per symbol per day (scheduler clears TRADED_TODAY_KEY at 04:00 ET)
    traded = await redis_client.smembers(TRADED_TODAY_KEY)
    if symbol in traded:
        return

    # Scrappy intelligence snapshot for gating (off | advisory | required)
    scrappy_mode = getattr(settings, "scrappy_mode", "advisory").strip().lower()
    snapshot_row = None
    if scrappy_mode != "off":
        try:
            from stockbot.scrappy.store import get_latest_non_stale_snapshot_by_symbol
            factory = get_session_factory()
            async with factory() as session:
                snapshot_row = await get_latest_non_stale_snapshot_by_symbol(session, symbol)
        except Exception as e:
            logger.debug("scrappy_snapshot_fetch_failed symbol=%s error=%s", symbol, e)

    or_high, or_low = sym_state.opening_range()
    if or_high is None or or_low is None:
        return
    prev_close = sym_state.prev_close or (sym_state.bars[0].open if sym_state.bars else None)
    if prev_close is None:
        return

    close = last_bar.close
    gap_pct = ((close - prev_close) / prev_close * 100).quantize(Decimal("0.01")) if prev_close else Decimal("0")
    spread_bps = 0
    if sym_state.latest_bid and sym_state.latest_ask and sym_state.latest_ask > 0:
        spread_bps = int((sym_state.latest_ask - sym_state.latest_bid) / sym_state.latest_ask * 10000)
    minute_dollar = (last_bar.high + last_bar.low + last_bar.close) / 3 * last_bar.volume
    rel_vol = sym_state.rel_volume_5m()
    news_side = classify_news_side(sym_state.news, within_minutes=60)
    all_pos: list[str] = []
    all_neg: list[str] = []
    for n in sym_state.news[-20:]:
        p, neg = news_keyword_hits(n.headline + " " + n.summary)
        all_pos.extend(p)
        all_neg.extend(neg)
    keyword_hits = list(set(all_pos + all_neg))

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
        if eval_result.reject_reason:
            logger.info(
                "candidate_rejected symbol=%s reason_code=%s",
                symbol, eval_result.reject_reason,
            )
        return

    # Scrappy gating: reject or tag
    if eval_result.side is not None:
        async def _record_rejection(reason_code: str) -> None:
            try:
                from stockbot.scrappy.store import insert_gate_rejection
                factory = get_session_factory()
                async with factory() as session:
                    await insert_gate_rejection(session, symbol, reason_code)
            except Exception as e:
                logger.debug("gate_rejection_persist_failed symbol=%s reason=%s error=%s", symbol, reason_code, e)

        reject_reason = scrappy_gate_check(snapshot_row, eval_result.side, scrappy_mode)
        if reject_reason:
            await _record_rejection(reject_reason)
            logger.info("candidate_rejected symbol=%s reason_code=%s", symbol, reject_reason)
            return
        direction = getattr(snapshot_row, "catalyst_direction", "neutral") if snapshot_row else "neutral"
        if snapshot_row:
            if direction == "positive":
                eval_result.reason_codes.append("scrappy_positive")
            elif direction == "negative":
                eval_result.reason_codes.append("scrappy_negative")
            else:
                eval_result.reason_codes.append("scrappy_neutral")

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
            intelligence_snapshot_id=snapshot_row.id if snapshot_row else None,
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

    logger.info(
        "signal_emitted symbol=%s side=%s signal_uuid=%s reason_codes=%s",
        symbol, eval_result.side, str(signal_uuid), eval_result.reason_codes,
    )
    logger.info(
        "shadow_opened symbol=%s side=%s signal_uuid=%s stop=%s target=%s",
        symbol, eval_result.side, str(signal_uuid), str(stop_price), str(target_price),
    )


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
