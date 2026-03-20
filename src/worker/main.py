"""
Worker: INTRA_EVENT_MOMO / 0.1.0 end-to-end strategy runtime.
Consumes Redis streams (bars, quotes, trades, news), maintains per-symbol state,
evaluates on completed minute bars, persists signals and shadow trades.
Shadow-only by default; when EXECUTION_MODE=paper and PAPER_EXECUTION_ENABLED=true, places paper orders.
One trade max per symbol per day. Force flat by 15:45 ET (shadow close + paper close when paper mode).
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import redis.asyncio as redis

from stockbot.config import get_settings
from stockbot.risk.sizing import compute_sizing
from stockbot.db.session import get_session_factory
from stockbot.gateways.market_gateway import (
    REDIS_KEY_GATEWAY_FALLBACK_REASON,
    REDIS_KEY_GATEWAY_SYMBOL_SOURCE,
    REDIS_STREAM_BARS,
    REDIS_STREAM_NEWS,
    REDIS_STREAM_QUOTES,
    REDIS_STREAM_TRADES,
)
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
    FeatureSet,
    NewsItem,
    classify_news_side,
    evaluate,
    exit_stop_target_prices,
    news_keyword_hits,
)

# Paper execution: sync Alpaca calls run in thread
def _submit_paper_order(
    signal_uuid: str,
    symbol: str,
    side: str,
    qty: Decimal,
    order_type: str,
) -> tuple[bool, str | None, str | None]:
    """
    Submit paper order. Returns (success, order_id_or_none, reason_code).
    Reason codes: paper_order_submitted | paper_order_rejected | paper_order_not_enabled |
    paper_order_blocked_by_risk | paper_order_skipped_no_account_state | paper_order_skipped_broker_unavailable
    """
    try:
        from stockbot.alpaca.client import AlpacaClient
        client = AlpacaClient()
        order = client.create_order(
            symbol=symbol,
            qty=float(qty),
            side=side,
            client_order_id=signal_uuid,
            time_in_force="day",
            order_type=order_type or "market",
        )
        return (True, order.get("id"), "paper_order_submitted")
    except Exception as e:
        err = str(e).lower()
        if "403" in err or "forbidden" in err or "not allowed" in err:
            return (False, None, "paper_order_rejected")
        return (False, None, "paper_order_skipped_broker_unavailable")


def _paper_force_flat_close(symbol: str) -> None:
    """Submit market close order(s) for symbol positions (force-flat in paper mode)."""
    try:
        from stockbot.alpaca.client import AlpacaClient
        client = AlpacaClient()
        positions = client.list_positions()
        for p in positions:
            if (p.get("symbol") or "").upper() != symbol.upper():
                continue
            qty_val = p.get("qty")
            if qty_val is None:
                continue
            try:
                qty_float = float(qty_val)
            except (TypeError, ValueError):
                continue
            if qty_float == 0:
                continue


def _submit_paper_exit_order(
    signal_uuid: str,
    symbol: str,
    side: str,
    qty: Decimal,
    exit_reason: str,
) -> tuple[bool, str | None, str | None]:
    """
    Submit paper exit order (close long or cover short).
    Returns (success, order_id_or_none, reason_code).
    Reason codes: paper_exit_submitted | paper_exit_rejected | paper_exit_skipped_broker_unavailable
    """
    try:
        from stockbot.alpaca.client import AlpacaClient
        client = AlpacaClient()
        # Determine exit side: long -> sell, short -> buy
        exit_side = "sell" if side.lower() == "buy" else "buy"
        # Use signal_uuid as client_order_id for idempotency
        client_order_id = f"{signal_uuid}_exit_{exit_reason}"
        order = client.create_order(
            symbol=symbol,
            qty=float(qty),
            side=exit_side,
            client_order_id=client_order_id,
            time_in_force="day",
            order_type="market",
        )
        return (True, order.get("id"), "paper_exit_submitted")
    except Exception as e:
        err = str(e).lower()
        if "403" in err or "forbidden" in err or "not allowed" in err:
            return (False, None, "paper_exit_rejected")
        return (False, None, "paper_exit_skipped_broker_unavailable")
            side = "sell" if qty_float > 0 else "buy"
            close_qty = abs(qty_float)
            client.create_order(
                symbol=symbol,
                qty=close_qty,
                side=side,
                client_order_id=f"force_flat_{symbol}_{uuid4()}",
                time_in_force="day",
                order_type="market",
            )
            logger.info("paper_force_flat_close symbol=%s side=%s qty=%s", symbol, side, close_qty)
            break
    except Exception as e:
        logger.warning("paper_force_flat_close failed symbol=%s error=%s", symbol, e)
from stockbot.strategies.state import BarLike, SymbolState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TRADED_TODAY_KEY = "stockbot:strategies:intra_event_momo:traded_today"
REDIS_LAST_IDS_KEY = "stockbot:worker:intra_event_momo:last_ids"
HEARTBEAT_KEY = "stockbot:worker:heartbeat"
HEARTBEAT_TTL_SEC = 60
HEARTBEAT_INTERVAL_SEC = 30
EVENT_COUNTS_LOG_INTERVAL = 500
REDIS_KEY_SCANNER_TOP = "stockbot:scanner:top_symbols"
REDIS_KEY_SCANNER_TOP_TS = "stockbot:scanner:top_updated_at"
REDIS_KEY_WORKER_UNIVERSE_REFRESH_TS = "stockbot:worker:universe_refresh_ts"
REDIS_KEY_WORKER_UNIVERSE_SOURCE = "stockbot:worker:universe_source"
REDIS_KEY_WORKER_UNIVERSE_COUNT = "stockbot:worker:universe_count"
REDIS_KEY_WORKER_FALLBACK_REASON = "stockbot:worker:universe_fallback_reason"
PAPER_ARMED_REDIS_KEY = "stockbot:paper:armed"
UNIVERSE_REFRESH_INTERVAL_SEC = 60


async def _paper_allowed_universe(redis_client: redis.Redis) -> tuple[bool, str | None]:
    """In paper mode, block submission if gateway or worker is on static fallback.
    Returns (True, None) if allowed, (False, reason) if blocked."""
    try:
        worker_source = await redis_client.get(REDIS_KEY_WORKER_UNIVERSE_SOURCE)
        worker_reason = await redis_client.get(REDIS_KEY_WORKER_FALLBACK_REASON)
        gateway_source = await redis_client.get(REDIS_KEY_GATEWAY_SYMBOL_SOURCE)
        gateway_reason = await redis_client.get(REDIS_KEY_GATEWAY_FALLBACK_REASON)
    except Exception as e:
        return (False, f"paper_blocked_universe_check_failed:{e!s}"[:80])
    if worker_source == "static":
        return (False, f"paper_blocked_worker_static_fallback:{worker_reason or 'unknown'}"[:80])
    if gateway_source == "static":
        return (False, f"paper_blocked_gateway_static_fallback:{gateway_reason or 'unknown'}"[:80])
    return (True, None)
WORKER_UNIVERSE_STATE_TTL_SEC = 120


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
            ts = datetime.now(UTC)
    else:
        ts = datetime.now(UTC)
    return BarLike(
        symbol=bar.get("symbol", bar.get("S", "")),
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
            ts = datetime.now(UTC)
    else:
        ts = datetime.now(UTC)
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
            ts = datetime.now(UTC)
    else:
        ts = datetime.now(UTC)
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
        published = datetime.fromisoformat(created.replace("Z", "+00:00")) if created else datetime.now(UTC)
    except Exception:
        published = datetime.now(UTC)
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
    with contextlib.suppress(Exception):
        await redis_client.set(REDIS_LAST_IDS_KEY, json.dumps(last_ids), ex=86400 * 7)


async def _resolve_worker_universe(redis_client: redis.Redis, settings: Any) -> tuple[list[str], str, str | None]:
    """
    Resolve worker universe: static | dynamic | hybrid from SCANNER_MODE.
    Returns (symbols, source, fallback_reason) for consistency logging with gateway.
    """
    static = [s.strip() for s in (settings.stockbot_universe or "AAPL,SPY").split(",") if s.strip()]
    if not static:
        static = ["AAPL", "SPY"]
    scanner_mode = getattr(settings, "scanner_mode", "static")
    if scanner_mode == "static":
        logger.debug("worker_universe source=static count=%s", len(static))
        return (static, "static", None)
    max_worker = getattr(settings, "scanner_max_worker_symbols", 50)
    stale_after_sec = getattr(settings, "scanner_top_stale_sec", 900)
    try:
        top_ts = await redis_client.get(REDIS_KEY_SCANNER_TOP_TS)
        if top_ts:
            ts = datetime.fromisoformat(top_ts.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            if (datetime.now(UTC) - ts).total_seconds() > stale_after_sec:
                return (static[:max_worker], "static", "dynamic_symbols_stale")
        raw = await redis_client.get(REDIS_KEY_SCANNER_TOP)
        if not raw:
            logger.info(
                "worker_universe dynamic list empty (no Redis key), using fallback source=%s count=%s",
                scanner_mode, len(static[:max_worker]),
            )
            out = static[:max_worker] if scanner_mode == "dynamic" else (static + [])[:max_worker]
            return (out, "static", "no_live_top_symbols")
        dynamic = json.loads(raw)
        if not isinstance(dynamic, list):
            logger.info(
                "worker_universe dynamic invalid type, using fallback source=%s count=%s",
                scanner_mode, len(static[:max_worker]),
            )
            return (static[:max_worker] if scanner_mode == "dynamic" else (static + [])[:max_worker], "static", "invalid_dynamic_payload")
        dynamic = [str(s).strip() for s in dynamic if s]
        if not dynamic and scanner_mode == "dynamic":
            logger.info(
                "worker_universe dynamic candidate list empty, using fallback source=static count=%s",
                len(static[:max_worker]),
            )
            return (static[:max_worker], "static", "no_live_top_symbols")
        if scanner_mode == "dynamic":
            out = dynamic[:max_worker]
            logger.debug("worker_universe source=dynamic count=%s", len(out))
            return (out, "dynamic", None)
        # hybrid: union, static first then dynamic, cap
        seen = set(static)
        out = list(static)
        for s in dynamic:
            if s not in seen and len(out) < max_worker:
                seen.add(s)
                out.append(s)
        out = out[:max_worker]
        logger.debug("worker_universe source=hybrid count=%s", len(out))
        return (out, "hybrid", None)
    except Exception as e:
        logger.warning("worker_universe Redis read failed, using fallback: %s", e)
        return (static[:max_worker], "static", "dynamic_symbols_unavailable")


async def run_worker() -> None:
    settings = get_settings()
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    universe, universe_source, fallback_reason = await _resolve_worker_universe(redis_client, settings)
    universe_set = frozenset(universe)
    last_universe_refresh = time.monotonic()
    try:
        ts = datetime.now(UTC).isoformat()
        await redis_client.set(REDIS_KEY_WORKER_UNIVERSE_REFRESH_TS, ts, ex=WORKER_UNIVERSE_STATE_TTL_SEC)
        await redis_client.set(REDIS_KEY_WORKER_UNIVERSE_SOURCE, universe_source, ex=WORKER_UNIVERSE_STATE_TTL_SEC)
        await redis_client.set(REDIS_KEY_WORKER_UNIVERSE_COUNT, str(len(universe)), ex=WORKER_UNIVERSE_STATE_TTL_SEC)
        await redis_client.set(REDIS_KEY_WORKER_FALLBACK_REASON, fallback_reason or "", ex=WORKER_UNIVERSE_STATE_TTL_SEC)
    except Exception:
        pass

    if universe_source == "static":
        logger.info(
            "worker_universe using static fallback (no live top symbols); count=%s",
            len(universe),
        )
    else:
        logger.info(
            "worker_connected strategy=%s version=%s universe_size=%s source=%s feed=iex",
            STRATEGY_ID, STRATEGY_VERSION, len(universe), universe_source,
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
                        datetime.now(UTC).isoformat(),
                        ex=HEARTBEAT_TTL_SEC,
                    )
                    last_heartbeat = time.monotonic()
                except Exception:
                    pass
            if time.monotonic() - last_universe_refresh >= UNIVERSE_REFRESH_INTERVAL_SEC:
                new_universe, new_source, new_fallback_reason = await _resolve_worker_universe(redis_client, settings)
                last_universe_refresh = time.monotonic()
                try:
                    ts = datetime.now(UTC).isoformat()
                    await redis_client.set(REDIS_KEY_WORKER_UNIVERSE_REFRESH_TS, ts, ex=WORKER_UNIVERSE_STATE_TTL_SEC)
                    await redis_client.set(REDIS_KEY_WORKER_UNIVERSE_SOURCE, new_source, ex=WORKER_UNIVERSE_STATE_TTL_SEC)
                    await redis_client.set(REDIS_KEY_WORKER_UNIVERSE_COUNT, str(len(new_universe)), ex=WORKER_UNIVERSE_STATE_TTL_SEC)
                    await redis_client.set(
                        REDIS_KEY_WORKER_FALLBACK_REASON,
                        new_fallback_reason or "",
                        ex=WORKER_UNIVERSE_STATE_TTL_SEC,
                    )
                except Exception:
                    pass
                if set(new_universe) != universe_set:
                    for sym in new_universe:
                        if sym not in state:
                            state[sym] = SymbolState(symbol=sym)
                    universe_set = frozenset(new_universe)
                    universe = new_universe
                    logger.info("worker_universe_refresh size=%s source=%s", len(universe), new_source)

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
    scrappy_mode = getattr(settings, "scrappy_mode", "advisory").strip().lower()

    last_bar = sym_state.last_bar()
    if not last_bar:
        return

    # Force flat at or after force_flat_et: close any open position at market
    if _et_time_after(last_bar.timestamp, force_flat) and shadow_state.has_position(symbol):
        pos = shadow_state.get_position(symbol)
        if pos:
            # Paper mode: submit close order to Alpaca (requires config + Redis armed; no static fallback)
            execution_mode = getattr(settings, "execution_mode", "shadow")
            paper_enabled = getattr(settings, "paper_execution_enabled", False)
            paper_armed_config = getattr(settings, "paper_trading_armed", False)
            try:
                paper_armed_redis = (await redis_client.get(PAPER_ARMED_REDIS_KEY)) == "1"
            except Exception:
                paper_armed_redis = False
            paper_armed = paper_armed_config and paper_armed_redis
            exit_order_id_force_flat: str | None = None
            if execution_mode == "paper" and paper_enabled and paper_armed:
                allow, block_reason = await _paper_allowed_universe(redis_client)
                if allow:
                    # Submit paper exit order for force-flat
                    ok, exit_order_id_force_flat, exit_reason_code = await asyncio.to_thread(
                        _submit_paper_exit_order,
                        str(pos.signal_uuid),
                        symbol,
                        pos.side,
                        pos.qty,
                        "force_flat",
                    )
                    if ok and exit_order_id_force_flat:
                        logger.info(
                            "paper_force_flat_submitted symbol=%s exit_order_id=%s signal_uuid=%s",
                            symbol, exit_order_id_force_flat, str(pos.signal_uuid),
                        )
                    else:
                        logger.warning(
                            "paper_force_flat_failed symbol=%s reason=%s signal_uuid=%s",
                            symbol, exit_reason_code, str(pos.signal_uuid),
                        )
                    # Also call legacy force-flat function for compatibility
                    await asyncio.to_thread(_paper_force_flat_close, symbol)
                else:
                    logger.warning("paper_force_flat_skipped symbol=%s reason=%s", symbol, block_reason)
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
                        scrappy_mode=scrappy_mode,
                    )
                # Update lifecycle for force-flat exit
                if execution_mode == "paper" and paper_enabled and paper_armed and exit_order_id_force_flat:
                    await store.update_paper_lifecycle_exit_order(
                        pos.signal_uuid, exit_order_id_force_flat, "force_flat", "exit_submitted"
                    )
                    await store.update_paper_lifecycle_exited(pos.signal_uuid, exit_ts, "exited")
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
                            scrappy_mode=scrappy_mode,
                        )
                shadow_state.close_position(symbol)
                logger.info(
                    "shadow_closed symbol=%s exit_reason=%s signal_uuid=%s",
                    symbol, exit_reason, str(pos.signal_uuid),
                )
                # Mirror stop/target exit to paper if in paper mode
                execution_mode_val = getattr(settings, "execution_mode", "shadow")
                paper_enabled = getattr(settings, "paper_execution_enabled", False)
                paper_armed_config = getattr(settings, "paper_trading_armed", False)
                try:
                    paper_armed_redis = (await redis_client.get(PAPER_ARMED_REDIS_KEY)) == "1"
                except Exception:
                    paper_armed_redis = False
                paper_armed = paper_armed_config and paper_armed_redis
                if execution_mode_val == "paper" and paper_enabled and paper_armed and exit_reason in ("stop", "target"):
                    # Check if lifecycle exists and hasn't already submitted exit
                    factory_exit = get_session_factory()
                    async with factory_exit() as session_exit:
                        store_exit = LedgerStore(session_exit)
                        lifecycle = await store_exit.get_paper_lifecycle_by_signal_uuid(pos.signal_uuid)
                        if lifecycle and lifecycle.exit_order_id is None:
                            # Submit paper exit order
                            ok, exit_order_id, exit_reason_code = await asyncio.to_thread(
                                _submit_paper_exit_order,
                                str(pos.signal_uuid),
                                symbol,
                                pos.side,
                                pos.qty,
                                exit_reason,
                            )
                            if ok and exit_order_id:
                                await store_exit.update_paper_lifecycle_exit_order(
                                    pos.signal_uuid, exit_order_id, exit_reason, "exit_submitted"
                                )
                                logger.info(
                                    "paper_exit_submitted symbol=%s exit_reason=%s exit_order_id=%s signal_uuid=%s",
                                    symbol, exit_reason, exit_order_id, str(pos.signal_uuid),
                                )
                            else:
                                await store_exit.update_paper_lifecycle_error(
                                    pos.signal_uuid, exit_reason_code or "paper_exit_failed", "exit_pending"
                                )
                                logger.warning(
                                    "paper_exit_failed symbol=%s exit_reason=%s reason=%s signal_uuid=%s",
                                    symbol, exit_reason, exit_reason_code, str(pos.signal_uuid),
                                )
        return

    # One trade per symbol per day (scheduler clears TRADED_TODAY_KEY at 04:00 ET)
    traded = await redis_client.smembers(TRADED_TODAY_KEY)
    if symbol in traded:
        return

    # Scrappy intelligence snapshot for gating (off | advisory | required)
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
    news_side = classify_news_side(
        sym_state.news, within_minutes=60, reference_ts=last_bar.timestamp
    )
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
                    await insert_gate_rejection(session, symbol, reason_code, scrappy_mode=scrappy_mode)
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

    # AI_SETUP_REFEREE: bounded reasoning (off | advisory | required). No order authority.
    ai_referee_assessment_id: int | None = None
    ai_referee_mode = getattr(settings, "ai_referee_mode", "off").strip().lower()
    ai_referee_enabled = getattr(settings, "ai_referee_enabled", False)
    if ai_referee_enabled and ai_referee_mode != "off":
        try:
            from stockbot.ai_referee.service import assess_setup
            from stockbot.ai_referee.store import insert_assessment
            from stockbot.ai_referee.types import RefereeInput
            from stockbot.scrappy.store import get_recent_notes

            headlines: list[str] = []
            if snapshot_row and getattr(snapshot_row, "headline_set_json", None):
                headlines = list(snapshot_row.headline_set_json or [])[: getattr(settings, "ai_referee_max_input_headlines", 20)]
            if not headlines and sym_state.news:
                headlines = [n.headline or "" for n in sym_state.news[-20:]]

            notes_summary: list[str] = []
            try:
                factory = get_session_factory()
                async with factory() as session:
                    notes = await get_recent_notes(session, limit=getattr(settings, "ai_referee_max_input_notes", 30), symbol=symbol)
                    notes_summary = [f"{n.title or ''}: {n.summary or ''}"[:200] for n in notes]
            except Exception:
                pass

            inp = RefereeInput(
                symbol=symbol,
                strategy_id=STRATEGY_ID,
                strategy_version=STRATEGY_VERSION,
                scrappy_snapshot_id=snapshot_row.id if snapshot_row else None,
                scrappy_run_id=getattr(snapshot_row, "scrappy_run_id", None) if snapshot_row else None,
                scrappy_headlines=headlines,
                scrappy_notes_summary=notes_summary,
                feature_snapshot=eval_result.feature_snapshot or {},
                quote_snapshot={"bid": str(sym_state.latest_bid), "ask": str(sym_state.latest_ask), "last": str(sym_state.latest_last)},
                news_snapshot={"news_side": news_side, "keyword_hits": keyword_hits},
                candidate_side="buy" if eval_result.side == "buy" else "sell",
            )
            assessment = await assess_setup(
                inp,
                api_key=getattr(settings, "openai_api_key", "") or "",
                model=getattr(settings, "ai_referee_model", "gpt-4o-mini"),
                timeout_seconds=getattr(settings, "ai_referee_timeout_seconds", 15),
                max_headlines=getattr(settings, "ai_referee_max_input_headlines", 20),
                max_notes=getattr(settings, "ai_referee_max_input_notes", 30),
                base_url=getattr(settings, "openai_base_url", None),
                require_json=getattr(settings, "ai_referee_require_json", True),
                auth_mode=getattr(settings, "ai_referee_auth", "api_key"),
            )
            if assessment:
                factory = get_session_factory()
                async with factory() as session:
                    ai_referee_assessment_id = await insert_assessment(session, assessment)
                if ai_referee_mode == "required":
                    if assessment.decision_class not in ("allow", "downgrade"):
                        async def _record_ai_rejection(reason: str) -> None:
                            try:
                                from stockbot.scrappy.store import insert_gate_rejection
                                factory = get_session_factory()
                                async with factory() as session:
                                    await insert_gate_rejection(session, symbol, reason, scrappy_mode=scrappy_mode)
                            except Exception as e:
                                logger.debug("ai_referee_rejection_persist_failed symbol=%s error=%s", symbol, e)
                        await _record_ai_rejection(
                            "ai_referee_block" if assessment.decision_class == "block" else "ai_referee_review"
                        )
                        logger.info("candidate_rejected symbol=%s reason_code=%s", symbol, assessment.decision_class)
                        return
                    if assessment.decision_class == "downgrade":
                        eval_result.reason_codes.append("ai_referee_downgrade")
                    else:
                        eval_result.reason_codes.append("ai_referee_allow")
                else:
                    eval_result.reason_codes.append(
                        f"ai_referee_{assessment.decision_class}"
                    )
                if assessment.contradiction_flag:
                    eval_result.reason_codes.append("ai_referee_contradiction")
                if assessment.stale_flag:
                    eval_result.reason_codes.append("ai_referee_stale")
                if assessment.evidence_sufficiency == "low":
                    eval_result.reason_codes.append("ai_referee_low_evidence")
            else:
                if ai_referee_mode == "required":
                    try:
                        from stockbot.scrappy.store import insert_gate_rejection
                        factory = get_session_factory()
                        async with factory() as session:
                            await insert_gate_rejection(session, symbol, "ai_referee_error", scrappy_mode=scrappy_mode)
                    except Exception:
                        pass
                    logger.info("candidate_rejected symbol=%s reason_code=ai_referee_error", symbol)
                    return
                eval_result.reason_codes.append("ai_referee_error")
        except Exception as e:
            logger.debug("ai_referee_failed symbol=%s error=%s", symbol, e)
            if ai_referee_mode == "required":
                try:
                    from stockbot.scrappy.store import insert_gate_rejection
                    factory = get_session_factory()
                    async with factory() as session:
                        await insert_gate_rejection(session, symbol, "ai_referee_error", scrappy_mode=scrappy_mode)
                except Exception:
                    pass
                return
            eval_result.reason_codes.append("ai_referee_error")

    bid = sym_state.latest_bid or close
    ask = sym_state.latest_ask or close
    if not bid or not ask:
        return

    signal_uuid = uuid4()
    side_str = "buy" if eval_result.side == "buy" else "sell"
    ideal_entry = compute_entry_fill(eval_result.side, bid, ask, ShadowFillParams("ideal", 0, Decimal("0")))
    real_entry = compute_entry_fill(eval_result.side, bid, ask, ShadowFillParams("realistic", slippage_bps, fee_per_share))
    stop_price, target_price = exit_stop_target_prices(eval_result.side, or_high, or_low, real_entry, 2.0)

    qty = Decimal("100")
    execution_mode_val = getattr(settings, "execution_mode", "shadow")
    paper_enabled = getattr(settings, "paper_execution_enabled", False)
    paper_armed_config = getattr(settings, "paper_trading_armed", False)
    try:
        paper_armed_redis = (await redis_client.get(PAPER_ARMED_REDIS_KEY)) == "1"
    except Exception:
        paper_armed_redis = False
    paper_armed = paper_armed_config and paper_armed_redis
    order_type_default = getattr(settings, "order_type_default", "market") or "market"
    # Block strategy paper if gateway or worker is on static fallback
    if execution_mode_val == "paper" and paper_enabled and paper_armed:
        allow, block_reason = await _paper_allowed_universe(redis_client)
        if not allow:
            if eval_result.reason_codes is None:
                eval_result.reason_codes = []
            eval_result.reason_codes.append(block_reason or "paper_blocked_static_fallback")
            paper_armed = False  # skip paper sizing and submission below
    # Capture sizing details for lifecycle persistence (paper mode only)
    sizing_details: dict[str, Any] | None = None
    if execution_mode_val == "paper" and paper_enabled and paper_armed:
        def _get_account_positions_and_size() -> tuple[Decimal, str | None, dict[str, Any] | None]:
            from stockbot.alpaca.client import AlpacaClient
            try:
                client = AlpacaClient()
                acc = client.get_account()
                positions = client.list_positions()
                equity = Decimal(str(acc.get("equity") or 0))
                buying_power = Decimal(str(acc.get("buying_power") or 0))
                if equity <= 0:
                    return (Decimal("100"), "paper_order_skipped_no_account_state", None)
                stop_dist = abs(real_entry - stop_price)
                risk_per_trade_pct = getattr(settings, "risk_per_trade_pct_equity", 0.5)
                max_position_pct = getattr(settings, "max_position_pct_equity", 10.0)
                max_concurrent = getattr(settings, "max_concurrent_positions", 5)
                max_gross_pct = getattr(settings, "max_gross_exposure_pct_equity", 50.0)
                max_symbol_pct = getattr(settings, "max_symbol_exposure_pct_equity", 20.0)
                sizing = compute_sizing(
                    equity=equity,
                    buying_power=buying_power,
                    positions=positions,
                    symbol=symbol,
                    side=side_str,
                    stop_distance_per_share=stop_dist,
                    intended_entry_price=real_entry,
                    allow_shorts=getattr(settings, "paper_allow_shorts", False),
                    risk_per_trade_pct_equity=risk_per_trade_pct,
                    max_position_pct_equity=max_position_pct,
                    max_concurrent_positions=max_concurrent,
                    max_gross_exposure_pct_equity=max_gross_pct,
                    max_symbol_exposure_pct_equity=max_symbol_pct,
                )
                details = {
                    "equity": equity,
                    "buying_power": buying_power,
                    "stop_distance": stop_dist,
                    "risk_per_trade_pct": Decimal(str(risk_per_trade_pct)),
                    "max_position_pct": Decimal(str(max_position_pct)),
                    "max_gross_exposure_pct": Decimal(str(max_gross_pct)),
                    "max_symbol_exposure_pct": Decimal(str(max_symbol_pct)),
                    "max_concurrent_positions": max_concurrent,
                    "qty_proposed": sizing.qty,
                    "qty_approved": sizing.qty if sizing.approved else Decimal("0"),
                    "notional_approved": sizing.notional if sizing.approved else None,
                    "rejection_reason": sizing.rejection_reason,
                }
                if sizing.approved and sizing.qty > 0:
                    return (sizing.qty, None, details)
                return (Decimal("100"), sizing.rejection_reason or "paper_order_blocked_by_risk", details)
            except Exception as e:
                logger.warning("paper_sizing_failed symbol=%s error=%s", symbol, e)
                return (Decimal("100"), "paper_order_skipped_broker_unavailable", None)
        sized_qty, paper_reject, sizing_details = await asyncio.to_thread(_get_account_positions_and_size)
        qty = sized_qty
        if paper_reject:
            logger.info("paper_order_skipped symbol=%s reason=%s", symbol, paper_reject)
            eval_result.reason_codes.append(paper_reject)

    factory = get_session_factory()
    async with factory() as session:
        store = LedgerStore(session)
        event = SignalEvent(
            signal_uuid=signal_uuid,
            symbol=symbol,
            side=side_str,
            qty=qty,
            strategy_id=STRATEGY_ID,
            strategy_version=STRATEGY_VERSION,
            feed="iex",
            quote_ts=last_bar.timestamp,
            ingest_ts=datetime.now(UTC),
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
            scrappy_mode=scrappy_mode,
            ai_referee_assessment_id=ai_referee_assessment_id,
        )
        await store.insert_signal(event)

    # Persist paper lifecycle at entry time (before order submission)
    if execution_mode_val == "paper" and paper_enabled and paper_armed and "paper_order_skipped" not in (eval_result.reason_codes or []) and "paper_order_blocked" not in (eval_result.reason_codes or []):
        try:
            universe_source_val = await redis_client.get(REDIS_KEY_WORKER_UNIVERSE_SOURCE) or "dynamic"
            paper_armed_reason_val = "armed" if paper_armed else "disarmed"
            force_flat_time_val = getattr(settings, "force_flat_et", "15:45")
            protection_mode_val = "worker_mirrored"  # Alpaca paper doesn't support bracket orders easily, use worker-mirrored
            factory_lifecycle = get_session_factory()
            async with factory_lifecycle() as session_lifecycle:
                store_lifecycle = LedgerStore(session_lifecycle)
                await store_lifecycle.insert_paper_lifecycle(
                    signal_uuid=signal_uuid,
                    symbol=symbol,
                    side=side_str,
                    qty=qty,
                    strategy_id=STRATEGY_ID,
                    strategy_version=STRATEGY_VERSION,
                    entry_ts=last_bar.timestamp,
                    entry_price=real_entry,
                    stop_price=stop_price,
                    target_price=target_price,
                    force_flat_time=force_flat_time_val,
                    protection_mode=protection_mode_val,
                    intelligence_snapshot_id=snapshot_row.id if snapshot_row else None,
                    ai_referee_assessment_id=ai_referee_assessment_id,
                    sizing_equity=sizing_details.get("equity") if sizing_details else None,
                    sizing_buying_power=sizing_details.get("buying_power") if sizing_details else None,
                    sizing_stop_distance=sizing_details.get("stop_distance") if sizing_details else None,
                    sizing_risk_per_trade_pct=sizing_details.get("risk_per_trade_pct") if sizing_details else None,
                    sizing_max_position_pct=sizing_details.get("max_position_pct") if sizing_details else None,
                    sizing_max_gross_exposure_pct=sizing_details.get("max_gross_exposure_pct") if sizing_details else None,
                    sizing_max_symbol_exposure_pct=sizing_details.get("max_symbol_exposure_pct") if sizing_details else None,
                    sizing_max_concurrent_positions=sizing_details.get("max_concurrent_positions") if sizing_details else None,
                    sizing_qty_proposed=sizing_details.get("qty_proposed") if sizing_details else None,
                    sizing_qty_approved=sizing_details.get("qty_approved") if sizing_details else qty,
                    sizing_notional_approved=sizing_details.get("notional_approved") if sizing_details else None,
                    sizing_rejection_reason=sizing_details.get("rejection_reason") if sizing_details else None,
                    universe_source=universe_source_val,
                    paper_armed=paper_armed,
                    paper_armed_reason=paper_armed_reason_val,
                    lifecycle_status="planned",
                )
            logger.info("paper_lifecycle_persisted symbol=%s signal_uuid=%s", symbol, str(signal_uuid))
        except Exception as e:
            logger.warning("paper_lifecycle_persist_failed symbol=%s error=%s", symbol, e)

    # Paper order submission after signal persisted (client_order_id = signal_uuid). Requires paper_trading_armed.
    if execution_mode_val == "paper" and paper_enabled and paper_armed and "paper_order_skipped" not in (eval_result.reason_codes or []) and "paper_order_blocked" not in (eval_result.reason_codes or []):
        ok, order_id, reason = await asyncio.to_thread(
            _submit_paper_order, str(signal_uuid), symbol, side_str, qty, order_type_default
        )
        if ok and order_id:
            factory2 = get_session_factory()
            async with factory2() as session2:
                store2 = LedgerStore(session2)
                await store2.update_signal_paper_order(signal_uuid, order_id, "paper")
                await store2.update_paper_lifecycle_entry_order(signal_uuid, order_id, "entry_submitted")
            logger.info("paper_order_submitted symbol=%s order_id=%s signal_uuid=%s", symbol, order_id, str(signal_uuid))
        else:
            logger.info("paper_order_failed symbol=%s reason=%s", symbol, reason)
            if eval_result.reason_codes is None:
                eval_result.reason_codes = []
            eval_result.reason_codes.append(reason or "paper_order_rejected")
            # Update lifecycle with error
            try:
                factory_err = get_session_factory()
                async with factory_err() as session_err:
                    store_err = LedgerStore(session_err)
                    await store_err.update_paper_lifecycle_error(signal_uuid, reason or "paper_order_rejected", "blocked")
            except Exception:
                pass

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
