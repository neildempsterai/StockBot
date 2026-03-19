"""Market gateway: dynamic symbol refresh, fallback when Redis empty, resolve symbols cap."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from stockbot.gateways.market_gateway import (
    _get_symbols,
    _get_symbols_from_redis,
    _resolve_gateway_symbols,
)


@pytest.mark.asyncio
async def test_get_symbols_from_redis_returns_list() -> None:
    """When Redis has valid JSON list, return symbol list."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=json.dumps(["AAPL", "SPY", "TSLA"]))
    out = await _get_symbols_from_redis(redis)
    assert out == ["AAPL", "SPY", "TSLA"]


@pytest.mark.asyncio
async def test_get_symbols_from_redis_empty_key_returns_none() -> None:
    """When Redis key is missing, return None (fallback to static)."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    out = await _get_symbols_from_redis(redis)
    assert out is None


@pytest.mark.asyncio
async def test_resolve_gateway_symbols_dynamic_caps_max() -> None:
    """Resolve from Redis and cap at market_gateway_max_symbols."""
    redis = AsyncMock()
    settings = MagicMock()
    settings.market_gateway_max_symbols = 25
    settings.scanner_top_stale_sec = 900
    redis.get = AsyncMock(side_effect=[None, json.dumps([f"S{i}" for i in range(100)])])
    symbols, source, fallback_reason = await _resolve_gateway_symbols(redis, settings)
    assert source == "dynamic"
    assert fallback_reason is None
    assert len(symbols) == 25
    assert symbols[0] == "S0"


@pytest.mark.asyncio
async def test_resolve_gateway_symbols_fallback_static_when_empty() -> None:
    """When Redis returns None, fall back to static list."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    settings = MagicMock()
    settings.market_gateway_max_symbols = 50
    settings.scanner_top_stale_sec = 900
    redis.get = AsyncMock(side_effect=[None, None])
    symbols, source, fallback_reason = await _resolve_gateway_symbols(redis, settings)
    assert source == "static"
    assert fallback_reason == "no_live_top_symbols"
    assert "AAPL" in symbols or "SPY" in symbols
    assert len(symbols) <= 50


@pytest.mark.asyncio
async def test_resolve_gateway_symbols_fallback_when_stale() -> None:
    """When Redis top timestamp is stale, force static fallback."""
    redis = AsyncMock()
    redis.get = AsyncMock(side_effect=["2020-01-01T00:00:00+00:00", json.dumps(["AAPL", "MSFT"])])
    settings = MagicMock()
    settings.market_gateway_max_symbols = 50
    settings.scanner_top_stale_sec = 60
    symbols, source, fallback_reason = await _resolve_gateway_symbols(redis, settings)
    assert source == "static"
    assert fallback_reason == "dynamic_symbols_stale"
    assert len(symbols) >= 1


def test_get_symbols_static_fallback() -> None:
    """Static fallback returns non-empty list from env or default."""
    out = _get_symbols()
    assert isinstance(out, list)
    assert len(out) >= 1
    assert all(isinstance(s, str) and s for s in out)


@pytest.mark.asyncio
async def test_stream_client_get_subscribed_and_set() -> None:
    """StreamClient get_subscribed and set_subscriptions for refresh comparison."""
    from stockbot.alpaca.stream_client import StreamClient

    stream = StreamClient()
    stream.subscribe(["AAPL", "SPY"])
    assert set(stream.get_subscribed()) == {"AAPL", "SPY"}
    stream.set_subscriptions(["TSLA", "NVDA"])
    assert set(stream.get_subscribed()) == {"TSLA", "NVDA"}