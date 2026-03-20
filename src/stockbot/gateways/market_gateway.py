"""
Alpaca market gateway: single data WebSocket connection, fan-out via Redis.
Uses REST snapshots for cold start and reconnect recovery.
Backfills today's minute bars from the Alpaca data API before starting the live stream.
Reads stockbot:scanner:top_symbols from Redis when present; falls back to ALPACA_SYMBOLS/env.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from zoneinfo import ZoneInfo

import redis.asyncio as redis

logger = logging.getLogger(__name__)

from stockbot.alpaca.client import AlpacaClient
from stockbot.alpaca.stream_client import StreamClient
from stockbot.alpaca.types import Bar
from stockbot.config import get_settings

REDIS_STREAM_TRADES = "alpaca:market:trades"
REDIS_STREAM_QUOTES = "alpaca:market:quotes"
REDIS_STREAM_BARS = "alpaca:market:bars"
REDIS_STREAM_NEWS = "alpaca:market:news"
HEARTBEAT_KEY = "stockbot:gateway:market:heartbeat"
HEARTBEAT_TTL_SEC = 60
HEARTBEAT_INTERVAL_SEC = 30


async def fan_out_handler(redis_client: redis.Redis, msg_type: str, payload: dict) -> None:
    """Push to Redis streams for downstream consumers."""
    ts = datetime.now(timezone.utc).isoformat()
    body = {"type": msg_type, "payload": _serialize_payload(payload), "ingest_ts": ts}
    if msg_type == "trade":
        await redis_client.xadd(REDIS_STREAM_TRADES, {"data": json.dumps(body)}, maxlen=10000)
    elif msg_type == "quote":
        await redis_client.xadd(REDIS_STREAM_QUOTES, {"data": json.dumps(body)}, maxlen=10000)
    elif msg_type == "bar":
        await redis_client.xadd(REDIS_STREAM_BARS, {"data": json.dumps(body)}, maxlen=5000)
    elif msg_type == "news":
        await redis_client.xadd(REDIS_STREAM_NEWS, {"data": json.dumps(body)}, maxlen=5000)


def _serialize_payload(payload: dict) -> dict:
    """Convert decimals/datetimes/dataclasses for JSON."""
    out = {}
    for k, v in payload.items():
        if v is None:
            out[k] = None
        elif hasattr(v, "isoformat") and callable(v.isoformat):
            out[k] = v.isoformat()
        elif hasattr(v, "__float__") and not isinstance(v, (int, float, bool)):
            try:
                out[k] = float(v)
            except (TypeError, ValueError):
                out[k] = str(v)
        elif isinstance(v, dict):
            out[k] = _serialize_payload(v)
        elif hasattr(v, "__dataclass_fields__"):
            out[k] = _serialize_payload({f: getattr(v, f) for f in v.__dataclass_fields__})
        else:
            out[k] = v
    return out


REDIS_KEY_SCANNER_TOP = "stockbot:scanner:top_symbols"
REDIS_KEY_SCANNER_TOP_TS = "stockbot:scanner:top_updated_at"
REDIS_KEY_GATEWAY_SYMBOL_REFRESH_TS = "stockbot:gateway:market:symbol_refresh_ts"
REDIS_KEY_GATEWAY_SYMBOL_COUNT = "stockbot:gateway:market:symbol_count"
REDIS_KEY_GATEWAY_SYMBOL_SOURCE = "stockbot:gateway:market:symbol_source"
REDIS_KEY_GATEWAY_FALLBACK_REASON = "stockbot:gateway:market:fallback_reason"
GATEWAY_REDIS_TTL_SEC = 300  # 5 minutes to prevent expiration during reconnects


def _get_symbols() -> list[str]:
    """Static env fallback."""
    raw = os.environ.get("ALPACA_SYMBOLS", "AAPL,SPY")
    return [s.strip() for s in raw.split(",") if s.strip()]


async def _get_symbols_from_redis(redis_client: redis.Redis) -> list[str] | None:
    """When scanner is used, worker subscribes to scanner top; gateway should stream same symbols."""
    try:
        raw = await redis_client.get(REDIS_KEY_SCANNER_TOP)
        if not raw:
            return None
        data = json.loads(raw)
        if isinstance(data, list) and data:
            return [str(s).strip() for s in data if s]
    except Exception:
        pass
    return None


def _is_iso_stale(updated_at_iso: str, stale_after_sec: int) -> bool:
    """True when updated_at is older than stale_after_sec."""
    try:
        updated = datetime.fromisoformat(updated_at_iso.replace("Z", "+00:00"))
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - updated).total_seconds()
        return age > stale_after_sec
    except Exception:
        return True


async def _resolve_gateway_symbols(
    redis_client: redis.Redis,
    settings: Any,
) -> tuple[list[str], str, str | None]:
    """Resolve symbols for gateway with explicit fallback reason."""
    max_syms = getattr(settings, "market_gateway_max_symbols", 50)
    stale_after_sec = getattr(settings, "scanner_top_stale_sec", 900)
    try:
        top_ts = await redis_client.get(REDIS_KEY_SCANNER_TOP_TS)
        if top_ts and _is_iso_stale(top_ts, stale_after_sec):
            static = _get_symbols()
            return (static[:max_syms], "static", "dynamic_symbols_stale")
        dynamic = await _get_symbols_from_redis(redis_client)
        if dynamic:
            out = dynamic[:max_syms]
            return (out, "dynamic", None)
        static = _get_symbols()
        return (static[:max_syms], "static", "no_live_top_symbols")
    except Exception:
        static = _get_symbols()
        return (static[:max_syms], "static", "dynamic_symbols_unavailable")


def _market_open_end_utc() -> tuple[datetime | None, datetime | None]:
    """Return (open_utc, end_utc) for today's regular session, or (None, None) if before open."""
    et = ZoneInfo("America/New_York")
    now_utc = datetime.now(timezone.utc)
    now_et = now_utc.astimezone(et)
    today = now_et.date()
    open_et = datetime(today.year, today.month, today.day, 9, 30, 0, tzinfo=et)
    close_et = datetime(today.year, today.month, today.day, 16, 0, 0, tzinfo=et)
    open_utc = open_et.astimezone(timezone.utc)
    close_utc = close_et.astimezone(timezone.utc)
    if now_utc < open_utc:
        return (None, None)
    end_utc = close_utc if now_utc >= close_utc else now_utc
    return (open_utc, end_utc)


async def backfill_today_bars(
    symbols: list[str],
    handler: Callable[[str, dict], Awaitable[None]],
) -> None:
    """Pull today's minute bars from Alpaca data API and push via handler."""
    start_utc, end_utc = _market_open_end_utc()
    if start_utc is None or end_utc is None or start_utc >= end_utc:
        return
    end_utc = end_utc.replace(second=0, microsecond=0)
    if start_utc >= end_utc:
        return
    client = AlpacaClient()
    all_bars: list[Bar] = []
    page_token: str | None = None
    while True:
        bars, page_token = client.get_bars(
            symbols,
            start=start_utc,
            end=end_utc,
            timeframe="1Min",
            limit=10000,
            page_token=page_token,
        )
        all_bars.extend(bars)
        if not page_token:
            break
    all_bars.sort(key=lambda b: b.timestamp)
    for bar in all_bars:
        await handler("bar", {"bar": bar, "raw": {}})
    if all_bars:
        last_ts = all_bars[-1].timestamp.isoformat() if all_bars[-1].timestamp else ""
        print(f"backfill: pushed {len(all_bars)} bars, last={last_ts}")


async def reseed_from_snapshots(stream_client: StreamClient, symbols: list[str]) -> None:
    """On cold start or reconnect: reseed from REST snapshots then resume stream."""
    client = AlpacaClient()
    snapshots = client.get_snapshots(symbols)
    for _sym, snap in snapshots.items():
        if snap and snap.latest_quote:
            await stream_client._dispatch("quote", {"quote": snap.latest_quote, "raw": {}})
        if snap and snap.latest_trade:
            await stream_client._dispatch("trade", {"trade": snap.latest_trade, "raw": {}})


async def _heartbeat_loop(redis_client: redis.Redis, symbols: list[str], source: str, fallback_reason: str | None = None) -> None:
    """Write heartbeat and symbol state to Redis so API health can report gateway status."""
    while True:
        try:
            await redis_client.set(
                HEARTBEAT_KEY,
                datetime.now(timezone.utc).isoformat(),
                ex=HEARTBEAT_TTL_SEC,
            )
            # Refresh symbol state periodically to prevent expiration
            await _write_gateway_symbol_state(redis_client, symbols, source, fallback_reason)
        except Exception:
            pass
        await asyncio.sleep(HEARTBEAT_INTERVAL_SEC)


async def _symbol_refresh_loop(
    redis_client: redis.Redis,
    stream: StreamClient,
    settings: Any,
    refresh_sec: int,
) -> None:
    """Periodically check Redis top symbols; if changed, close stream so main loop reconnects with new list."""
    force_reconnect = getattr(settings, "market_gateway_force_reconnect_on_symbol_change", True)
    if not force_reconnect:
        return
    while True:
        await asyncio.sleep(refresh_sec)
        try:
            new_symbols, _, _ = await _resolve_gateway_symbols(redis_client, settings)
            current = set(stream.get_subscribed())
            new_set = set(new_symbols)
            if new_set != current:
                added = new_set - current
                removed = current - new_set
                logger.info(
                    "market_gateway symbol_refresh triggering reconnect old_count=%s new_count=%s added=%s removed=%s",
                    len(current),
                    len(new_set),
                    len(added),
                    len(removed),
                )
                await stream.close()
                break
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug("market_gateway symbol_refresh check failed: %s", e)


async def _write_gateway_symbol_state(
    redis_client: redis.Redis,
    symbols: list[str],
    source: str,
    fallback_reason: str | None = None,
) -> None:
    """Write current gateway symbol state to Redis for API health."""
    try:
        ts = datetime.now(timezone.utc).isoformat()
        await redis_client.set(REDIS_KEY_GATEWAY_SYMBOL_REFRESH_TS, ts, ex=GATEWAY_REDIS_TTL_SEC)
        await redis_client.set(REDIS_KEY_GATEWAY_SYMBOL_COUNT, str(len(symbols)), ex=GATEWAY_REDIS_TTL_SEC)
        await redis_client.set(REDIS_KEY_GATEWAY_SYMBOL_SOURCE, source, ex=GATEWAY_REDIS_TTL_SEC)
        await redis_client.set(
            REDIS_KEY_GATEWAY_FALLBACK_REASON,
            fallback_reason or "",
            ex=GATEWAY_REDIS_TTL_SEC,
        )
    except Exception:
        pass


async def run_market_gateway() -> None:
    settings = get_settings()
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    refresh_sec = getattr(settings, "market_gateway_symbol_refresh_sec", 60)

    while True:
        try:
            symbols, source, fallback_reason = await _resolve_gateway_symbols(redis_client, settings)
            if not symbols:
                symbols = _get_symbols()
                source = "static"
                fallback_reason = "no_symbols_resolved"

            await _write_gateway_symbol_state(redis_client, symbols, source, fallback_reason)
            if source == "static":
                logger.info(
                    "market_gateway using static fallback because %s; count=%s",
                    fallback_reason or "no_live_top_symbols",
                    len(symbols),
                )
            else:
                logger.info("market_gateway symbols source=dynamic count=%s", len(symbols))
        except Exception as e:
            logger.error("market_gateway symbol resolution failed: %s", e, exc_info=True)
            symbols = _get_symbols()
            source = "static"
            fallback_reason = "symbol_resolution_error"
            await _write_gateway_symbol_state(redis_client, symbols, source, fallback_reason)

        try:
            await redis_client.set(
                HEARTBEAT_KEY,
                datetime.now(timezone.utc).isoformat(),
                ex=HEARTBEAT_TTL_SEC,
            )
        except Exception:
            pass

        async def handler(msg_type: str, payload: dict) -> None:
            await fan_out_handler(redis_client, msg_type, payload)

        stream = StreamClient()
        stream.add_handler(handler)
        stream.subscribe(symbols)

        await reseed_from_snapshots(stream, symbols)

        try:
            await backfill_today_bars(symbols, handler)
        except Exception as e:
            logger.debug("backfill skipped: %s", e)

        heartbeat_task = asyncio.create_task(_heartbeat_loop(redis_client, symbols, source, fallback_reason))
        refresh_task = asyncio.create_task(
            _symbol_refresh_loop(redis_client, stream, settings, refresh_sec),
        )

        try:
            await stream.run()
        except Exception as e:
            # Log connection errors but don't crash - let the loop reconnect
            logger.warning("market_gateway stream connection error: %s (reconnecting)", e)
        finally:
            refresh_task.cancel()
            heartbeat_task.cancel()
            try:
                await refresh_task
            except asyncio.CancelledError:
                pass
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

        logger.info("market_gateway stream ended; reconnecting in 5s")
        await asyncio.sleep(5)


def main() -> None:
    asyncio.run(run_market_gateway())


if __name__ == "__main__":
    main()
