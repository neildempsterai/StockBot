"""
Alpaca market gateway: single data WebSocket connection, fan-out via Redis.
Uses REST snapshots for cold start and reconnect recovery.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone

import redis.asyncio as redis

from stockbot.alpaca.client import AlpacaClient
from stockbot.alpaca.stream_client import StreamClient
from stockbot.config import get_settings

REDIS_STREAM_TRADES = "alpaca:market:trades"
REDIS_STREAM_QUOTES = "alpaca:market:quotes"
REDIS_STREAM_BARS = "alpaca:market:bars"
REDIS_STREAM_NEWS = "alpaca:market:news"


async def fan_out_handler(redis_client: redis.Redis, msg_type: str, payload: dict) -> None:
    """Push to Redis streams for downstream consumers."""
    ts = datetime.now(datetime.UTC).isoformat()
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
        elif hasattr(v, "isoformat") and callable(getattr(v, "isoformat")):
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


def _get_symbols() -> list[str]:
    raw = os.environ.get("ALPACA_SYMBOLS", "AAPL,SPY")
    return [s.strip() for s in raw.split(",") if s.strip()]


async def reseed_from_snapshots(stream_client: StreamClient, symbols: list[str]) -> None:
    """On cold start or reconnect: reseed from REST snapshots then resume stream."""
    client = AlpacaClient()
    snapshots = client.get_snapshots(symbols)
    for sym, snap in snapshots.items():
        if snap and snap.latest_quote:
            await stream_client._dispatch("quote", {"quote": snap.latest_quote, "raw": {}})
        if snap and snap.latest_trade:
            await stream_client._dispatch("trade", {"trade": snap.latest_trade, "raw": {}})


async def run_market_gateway() -> None:
    settings = get_settings()
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)

    async def handler(msg_type: str, payload: dict) -> None:
        await fan_out_handler(redis_client, msg_type, payload)

    stream = StreamClient()
    stream.add_handler(handler)

    symbols = _get_symbols()
    stream.subscribe(symbols)

    # Cold start: reseed from snapshots
    await reseed_from_snapshots(stream, symbols)

    while True:
        try:
            await stream.run()
        except Exception as e:
            # Reconnect: reseed then loop again
            await reseed_from_snapshots(stream, symbols)
            await asyncio.sleep(5)
        else:
            break


def main() -> None:
    asyncio.run(run_market_gateway())


if __name__ == "__main__":
    main()
