"""
Replay helper: feed deterministic bar/quote/news and snapshot into worker e2e tests.
Redis stream format matches market_gateway fan-out.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from stockbot.gateways.market_gateway import (
    REDIS_STREAM_BARS,
    REDIS_STREAM_NEWS,
    REDIS_STREAM_QUOTES,
    REDIS_STREAM_TRADES,
)


def _iso(ts: datetime) -> str:
    return ts.isoformat().replace("+00:00", "Z") if ts.tzinfo else ts.replace(tzinfo=UTC).isoformat()


async def push_bar(
    redis_client: Any,
    symbol: str,
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: int,
    timestamp: datetime | None = None,
) -> str:
    """Push one minute bar to Redis; returns stream id."""
    ts = timestamp or datetime.now(UTC)
    body = {
        "type": "bar",
        "payload": {
            "bar": {
                "symbol": symbol,
                "o": open_price,
                "h": high,
                "l": low,
                "c": close,
                "v": volume,
                "timestamp": _iso(ts),
            },
        },
        "ingest_ts": _iso(datetime.now(UTC)),
    }
    return await redis_client.xadd(REDIS_STREAM_BARS, {"data": json.dumps(body)}, maxlen=5000)


async def push_quote(
    redis_client: Any,
    symbol: str,
    bid: float,
    ask: float,
    timestamp: datetime | None = None,
) -> str:
    """Push one quote to Redis; returns stream id."""
    ts = timestamp or datetime.now(UTC)
    body = {
        "type": "quote",
        "payload": {
            "quote": {
                "symbol": symbol,
                "bp": bid,
                "ap": ask,
                "timestamp": _iso(ts),
            },
        },
        "ingest_ts": _iso(datetime.now(UTC)),
    }
    return await redis_client.xadd(REDIS_STREAM_QUOTES, {"data": json.dumps(body)}, maxlen=10000)


async def push_news(
    redis_client: Any,
    headline: str,
    summary: str,
    symbols: list[str] | None = None,
    published_at: datetime | None = None,
) -> str:
    """Push one news item to Redis; returns stream id."""
    ts = published_at or datetime.now(UTC)
    raw = {
        "headline": headline,
        "summary": summary,
        "symbols": symbols or [],
        "created_at": _iso(ts),
        "updated_at": _iso(ts),
    }
    body = {"type": "news", "payload": {"raw": raw}, "ingest_ts": _iso(datetime.now(UTC))}
    return await redis_client.xadd(REDIS_STREAM_NEWS, {"data": json.dumps(body)}, maxlen=5000)


async def push_trade(
    redis_client: Any,
    symbol: str,
    price: float,
    timestamp: datetime | None = None,
) -> str:
    """Push one trade to Redis; returns stream id."""
    ts = timestamp or datetime.now(UTC)
    body = {
        "type": "trade",
        "payload": {
            "trade": {
                "symbol": symbol,
                "p": price,
                "timestamp": _iso(ts),
            },
        },
        "ingest_ts": _iso(datetime.now(UTC)),
    }
    return await redis_client.xadd(REDIS_STREAM_TRADES, {"data": json.dumps(body)}, maxlen=10000)


async def create_snapshot_in_db(
    session: Any,
    symbol: str,
    catalyst_direction: str,
    *,
    stale_flag: bool = False,
    conflict_flag: bool = False,
    freshness_minutes: int = 30,
    scrappy_run_id: str | None = None,
) -> int:
    """Insert symbol_intelligence_snapshots row; returns id. Use from async test."""
    from datetime import datetime

    from stockbot.scrappy.store import insert_intelligence_snapshot
    return await insert_intelligence_snapshot(
        session,
        symbol=symbol,
        snapshot_ts=datetime.now(UTC),
        freshness_minutes=freshness_minutes if not stale_flag else 200,
        catalyst_direction=catalyst_direction,
        catalyst_strength=50,
        sentiment_label=catalyst_direction if catalyst_direction != "conflicting" else "mixed",
        evidence_count=1,
        source_count=1,
        source_domains_json=["test"],
        thesis_tags_json=[],
        headline_set_json=[],
        stale_flag=stale_flag,
        conflict_flag=conflict_flag,
        raw_evidence_refs_json=[],
        scrappy_run_id=scrappy_run_id,
        scrappy_version="0.1.0",
    )
