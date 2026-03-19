"""Worker universe selection: dynamic source, stale fallback, static fallback."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from worker.main import _resolve_worker_universe


@pytest.mark.asyncio
async def test_worker_universe_dynamic_source() -> None:
    """Dynamic scanner top symbols should be used when present and fresh."""
    redis = AsyncMock()
    redis.get = AsyncMock(side_effect=["2099-01-01T00:00:00+00:00", json.dumps(["AAPL", "MSFT", "NVDA"])])
    settings = MagicMock()
    settings.stockbot_universe = "SPY,QQQ"
    settings.scanner_mode = "dynamic"
    settings.scanner_max_worker_symbols = 10
    settings.scanner_top_stale_sec = 900
    symbols, source, fallback_reason = await _resolve_worker_universe(redis, settings)
    assert symbols == ["AAPL", "MSFT", "NVDA"]
    assert source == "dynamic"
    assert fallback_reason is None


@pytest.mark.asyncio
async def test_worker_universe_stale_fallback_to_static() -> None:
    """Stale dynamic timestamp must force static fallback."""
    redis = AsyncMock()
    redis.get = AsyncMock(side_effect=["2020-01-01T00:00:00+00:00", json.dumps(["AAPL", "MSFT", "NVDA"])])
    settings = MagicMock()
    settings.stockbot_universe = "SPY,QQQ"
    settings.scanner_mode = "dynamic"
    settings.scanner_max_worker_symbols = 10
    settings.scanner_top_stale_sec = 60
    symbols, source, fallback_reason = await _resolve_worker_universe(redis, settings)
    assert symbols == ["SPY", "QQQ"]
    assert source == "static"
    assert fallback_reason == "dynamic_symbols_stale"


@pytest.mark.asyncio
async def test_worker_universe_refresh_includes_new_dynamic_symbols() -> None:
    """When scanner top updates, resolved universe should reflect refreshed symbols."""
    settings = MagicMock()
    settings.stockbot_universe = "SPY,QQQ"
    settings.scanner_mode = "dynamic"
    settings.scanner_max_worker_symbols = 10
    settings.scanner_top_stale_sec = 900

    redis_first = AsyncMock()
    redis_first.get = AsyncMock(side_effect=["2099-01-01T00:00:00+00:00", json.dumps(["AAPL", "MSFT"])])
    first, first_source, _ = await _resolve_worker_universe(redis_first, settings)
    assert first == ["AAPL", "MSFT"]
    assert first_source == "dynamic"

    redis_second = AsyncMock()
    redis_second.get = AsyncMock(side_effect=["2099-01-01T00:05:00+00:00", json.dumps(["TSLA", "NVDA"])])
    second, second_source, _ = await _resolve_worker_universe(redis_second, settings)
    assert second == ["TSLA", "NVDA"]
    assert second_source == "dynamic"
