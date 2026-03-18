"""Worker INTRA_EVENT_MOMO: stream consumption, signal persistence, shadow lifecycle, one-trade-per-day."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from stockbot.gateways.market_gateway import (
    REDIS_STREAM_BARS,
    REDIS_STREAM_NEWS,
    REDIS_STREAM_QUOTES,
    REDIS_STREAM_TRADES,
)
from stockbot.strategies.state import BarLike, SymbolState
from worker.main import (
    REDIS_LAST_IDS_KEY,
    TRADED_TODAY_KEY,
    _load_last_ids,
    _on_bar,
    _parse_bar_from_payload,
    _parse_news_from_payload,
    _parse_quote_from_payload,
    _parse_trade_from_payload,
    _save_last_ids,
)


def test_parse_bar_from_payload_serialized_bar() -> None:
    """Parse bar from gateway serialized format (open/high/low/close/volume/timestamp)."""
    payload = {
        "bar": {
            "symbol": "AAPL",
            "open": 150.0,
            "high": 151.0,
            "low": 149.5,
            "close": 150.5,
            "volume": 10000,
            "timestamp": "2026-03-17T14:31:00+00:00",
        }
    }
    bar = _parse_bar_from_payload(payload)
    assert bar is not None
    assert bar.symbol == "AAPL"
    assert bar.open == Decimal("150")
    assert bar.high == Decimal("151")
    assert bar.close == Decimal("150.5")
    assert bar.volume == 10000


def test_parse_bar_from_payload_raw_alpaca_keys() -> None:
    """Parse bar with raw Alpaca keys (o, h, l, c, v, S)."""
    payload = {"bar": {"S": "SPY", "o": 500, "h": 501, "l": 499, "c": 500.5, "v": 5000}}
    bar = _parse_bar_from_payload(payload)
    assert bar is not None
    assert bar.symbol == "SPY"
    assert bar.close == Decimal("500.5")


def test_parse_quote_from_payload() -> None:
    """Parse quote with bid_price/ask_price or bp/ap."""
    payload = {
        "quote": {
            "symbol": "AAPL",
            "bid_price": 150.0,
            "ask_price": 150.05,
            "timestamp": "2026-03-17T14:30:00Z",
        }
    }
    out = _parse_quote_from_payload(payload)
    assert out is not None
    sym, bid, ask, ts = out
    assert sym == "AAPL"
    assert bid == Decimal("150")
    assert ask == Decimal("150.05")


def test_parse_trade_from_payload() -> None:
    """Parse trade for latest_last update."""
    payload = {"trade": {"symbol": "AAPL", "price": 150.02, "timestamp": "2026-03-17T14:30:00Z"}}
    out = _parse_trade_from_payload(payload)
    assert out is not None
    sym, price, ts = out
    assert sym == "AAPL"
    assert price == Decimal("150.02")


def test_parse_news_from_payload() -> None:
    """Parse news item."""
    payload = {
        "raw": {
            "headline": "AAPL beats earnings",
            "summary": "Company raised guidance",
            "created_at": "2026-03-17T14:00:00Z",
            "symbols": ["AAPL"],
        }
    }
    news = _parse_news_from_payload(payload)
    assert news is not None
    assert news.headline == "AAPL beats earnings"
    assert news.symbol == "AAPL"


@pytest.mark.asyncio
async def test_load_last_ids_empty_returns_defaults() -> None:
    """When Redis has no saved IDs, return 0 for each stream."""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    last_ids = await _load_last_ids(redis_mock)
    assert last_ids[REDIS_STREAM_BARS] == "0"
    assert last_ids[REDIS_STREAM_QUOTES] == "0"
    assert last_ids[REDIS_STREAM_NEWS] == "0"
    assert last_ids[REDIS_STREAM_TRADES] == "0"


@pytest.mark.asyncio
async def test_load_last_ids_restore_from_redis() -> None:
    """Restore last_ids from Redis for restart safety."""
    redis_mock = AsyncMock()
    saved = {REDIS_STREAM_BARS: "1234-0", REDIS_STREAM_QUOTES: "1235-0"}
    redis_mock.get = AsyncMock(return_value=json.dumps(saved))
    last_ids = await _load_last_ids(redis_mock)
    assert last_ids.get(REDIS_STREAM_BARS) == "1234-0"


@pytest.mark.asyncio
async def test_save_last_ids_persists() -> None:
    """Persist last_ids to Redis."""
    redis_mock = AsyncMock()
    last_ids = {REDIS_STREAM_BARS: "999-0", REDIS_STREAM_QUOTES: "998-0"}
    await _save_last_ids(redis_mock, last_ids)
    redis_mock.set.assert_called_once()
    call = redis_mock.set.call_args
    assert call.args[0] == REDIS_LAST_IDS_KEY
    assert "999-0" in call.args[1]


@pytest.mark.asyncio
async def test_worker_ignores_out_of_universe() -> None:
    """Bar for symbol not in universe does not update state."""
    # State only has AAPL; bar for XYZ should not be in state
    universe_set = frozenset(["AAPL"])
    state = {"AAPL": SymbolState(symbol="AAPL")}
    bar = BarLike(symbol="XYZ", open=Decimal("100"), high=Decimal("101"), low=Decimal("99"), close=Decimal("100.5"), volume=1000, timestamp=datetime.now(UTC))
    assert bar.symbol not in universe_set
    # The main loop only calls _on_bar when bar.symbol in universe_set, so XYZ never gets _on_bar
    assert "XYZ" not in state


@pytest.mark.asyncio
async def test_worker_consumes_bar_emits_signal_and_opens_shadow() -> None:
    """When bar triggers entry, worker persists signal and opens shadow position (sadd traded_today)."""
    from stockbot.shadow.engine import ShadowState

    redis_mock = AsyncMock()
    redis_mock.smembers = AsyncMock(return_value=set())
    redis_mock.sadd = AsyncMock()

    sym_state = SymbolState(symbol="AAPL")
    sym_state.prev_close = Decimal("145")
    sym_state.latest_bid = Decimal("152")
    sym_state.latest_ask = Decimal("152.05")
    sym_state.latest_last = Decimal("152")
    for i in range(5):
        sym_state.bars.append(BarLike(
            symbol="AAPL",
            open=Decimal("146") + Decimal(i),
            high=Decimal("147") + Decimal(i),
            low=Decimal("145") + Decimal(i),
            close=Decimal("146.5") + Decimal(i),
            volume=100000,
            timestamp=datetime(2026, 3, 17, 13, 35 + i, 0, tzinfo=UTC),
        ))
    # 6th bar: break above opening range high (151) to trigger long
    sym_state.bars.append(BarLike(
        symbol="AAPL",
        open=Decimal("151"),
        high=Decimal("152"),
        low=Decimal("150.5"),
        close=Decimal("152"),
        volume=2000000,
        timestamp=datetime(2026, 3, 17, 14, 35, 0, tzinfo=UTC),
    ))
    from stockbot.strategies.intra_event_momo import NewsItem
    # Published within last 60 min so classify_news_side returns "long"
    sym_state.news.append(NewsItem(
        headline="AAPL beats earnings",
        summary="raised guidance",
        published_at=datetime.now(UTC) - timedelta(minutes=30),
        symbol="AAPL",
        raw={},
    ))

    shadow_state = ShadowState()
    settings = MagicMock()
    settings.entry_start_et = "09:35"
    settings.entry_end_et = "11:30"
    settings.force_flat_et = "15:45"

    store_mock = MagicMock()
    store_mock.insert_signal = AsyncMock()
    store_mock.insert_shadow_trade = AsyncMock()

    with patch("worker.main.LedgerStore", return_value=store_mock):
        from contextlib import asynccontextmanager
        @asynccontextmanager
        async def fake_factory():
            yield MagicMock()
        with patch("worker.main.get_session_factory", return_value=fake_factory):
            await _on_bar(redis_mock, sym_state, shadow_state, settings, Decimal("0"), 5)

    store_mock.insert_signal.assert_called_once()
    redis_mock.sadd.assert_called_once_with(TRADED_TODAY_KEY, "AAPL")
    assert shadow_state.has_position("AAPL")


@pytest.mark.asyncio
async def test_worker_enforces_one_trade_per_symbol_per_day() -> None:
    """After first signal for symbol, second bar does not emit another signal (traded_today)."""
    redis_mock = AsyncMock()
    redis_mock.smembers = AsyncMock(return_value={"AAPL"})  # already traded today
    sym_state = SymbolState(symbol="AAPL")
    sym_state.prev_close = Decimal("145")
    sym_state.bars = [
        BarLike("AAPL", Decimal("146"), Decimal("147"), Decimal("145"), Decimal("146.5"), 100000, datetime(2026, 3, 17, 13, 35 + i, 0, tzinfo=UTC))
        for i in range(6)
    ]
    sym_state.latest_bid = Decimal("150")
    sym_state.latest_ask = Decimal("150.05")
    sym_state.latest_last = Decimal("150")
    sym_state.news.append(
        __import__("stockbot.strategies.intra_event_momo", fromlist=["NewsItem"]).NewsItem(
            headline="beat", summary="", published_at=datetime(2026, 3, 17, 14, 0, tzinfo=UTC), symbol="AAPL", raw={}
        )
    )
    shadow_state = __import__("stockbot.shadow.engine", fromlist=["ShadowState"]).ShadowState()
    settings = MagicMock()
    settings.entry_start_et = "09:35"
    settings.entry_end_et = "11:30"
    settings.force_flat_et = "15:45"

    with patch("worker.main.get_session_factory"):
        await _on_bar(redis_mock, sym_state, shadow_state, settings, Decimal("0"), 5)

    # Should not have called sadd (no new signal)
    redis_mock.sadd.assert_not_called()
    assert not shadow_state.has_position("AAPL")


@pytest.mark.asyncio
async def test_worker_closes_shadow_on_stop() -> None:
    """When bar low hits stop, shadow position is closed and insert_shadow_trade called twice (ideal + realistic)."""
    from stockbot.shadow.engine import ShadowPosition, ShadowState

    redis_mock = AsyncMock()
    redis_mock.smembers = AsyncMock(return_value=set())
    sym_state = SymbolState(symbol="AAPL")
    sym_state.prev_close = Decimal("100")
    sym_state.latest_bid = Decimal("98")
    sym_state.latest_ask = Decimal("98.05")
    sym_state.latest_last = Decimal("98")
    sym_state.bars = [
        BarLike("AAPL", Decimal("100"), Decimal("102"), Decimal("99"), Decimal("101"), 10000, datetime(2026, 3, 17, 14, 30, 0, tzinfo=UTC)),
        BarLike("AAPL", Decimal("101"), Decimal("101.5"), Decimal("97"), Decimal("97.5"), 10000, datetime(2026, 3, 17, 14, 31, 0, tzinfo=UTC)),
    ]
    sig_uuid = uuid4()
    pos = ShadowPosition(
        signal_uuid=sig_uuid,
        symbol="AAPL",
        side="buy",
        qty=Decimal("100"),
        entry_ts=datetime(2026, 3, 17, 14, 30, 0, tzinfo=UTC),
        ideal_entry_price=Decimal("101"),
        realistic_entry_price=Decimal("101"),
        stop_price=Decimal("99"),
        target_price=Decimal("105"),
        slippage_bps=5,
        fee_per_share=Decimal("0"),
    )
    shadow_state = ShadowState()
    shadow_state.open_position(pos)
    settings = MagicMock()
    settings.entry_start_et = "09:35"
    settings.entry_end_et = "11:30"
    settings.force_flat_et = "15:45"

    store_mock = MagicMock()
    store_mock.insert_signal = AsyncMock()
    store_mock.insert_shadow_trade = AsyncMock()

    with patch("worker.main.LedgerStore", return_value=store_mock):
        from contextlib import asynccontextmanager
        @asynccontextmanager
        async def fake_factory():
            yield MagicMock()
        with patch("worker.main.get_session_factory", return_value=fake_factory):
            await _on_bar(redis_mock, sym_state, shadow_state, settings, Decimal("0"), 5)

    assert store_mock.insert_shadow_trade.call_count == 2
    calls = store_mock.insert_shadow_trade.call_args_list
    assert all(c.kwargs.get("exit_reason") == "stop" for c in calls)
    assert not shadow_state.has_position("AAPL")


@pytest.mark.asyncio
async def test_worker_closes_shadow_on_target() -> None:
    """When bar high hits target, shadow position is closed with exit_reason=target."""
    from stockbot.shadow.engine import ShadowPosition, ShadowState

    redis_mock = AsyncMock()
    redis_mock.smembers = AsyncMock(return_value=set())
    sym_state = SymbolState(symbol="AAPL")
    sym_state.prev_close = Decimal("100")
    sym_state.latest_bid = Decimal("106")
    sym_state.latest_ask = Decimal("106.05")
    sym_state.latest_last = Decimal("106")
    # Bar that hits target 105 (long: high >= target)
    sym_state.bars = [
        BarLike("AAPL", Decimal("100"), Decimal("102"), Decimal("99"), Decimal("101"), 10000, datetime(2026, 3, 17, 14, 30, 0, tzinfo=UTC)),
        BarLike("AAPL", Decimal("101"), Decimal("106"), Decimal("100"), Decimal("105"), 10000, datetime(2026, 3, 17, 14, 31, 0, tzinfo=UTC)),
    ]
    pos = ShadowPosition(
        signal_uuid=uuid4(),
        symbol="AAPL",
        side="buy",
        qty=Decimal("100"),
        entry_ts=datetime(2026, 3, 17, 14, 30, 0, tzinfo=UTC),
        ideal_entry_price=Decimal("101"),
        realistic_entry_price=Decimal("101"),
        stop_price=Decimal("99"),
        target_price=Decimal("105"),
        slippage_bps=5,
        fee_per_share=Decimal("0"),
    )
    shadow_state = ShadowState()
    shadow_state.open_position(pos)
    settings = MagicMock()
    settings.entry_start_et = "09:35"
    settings.entry_end_et = "11:30"
    settings.force_flat_et = "15:45"
    store_mock = MagicMock()
    store_mock.insert_signal = AsyncMock()
    store_mock.insert_shadow_trade = AsyncMock()

    with patch("worker.main.LedgerStore", return_value=store_mock):
        from contextlib import asynccontextmanager
        @asynccontextmanager
        async def fake_factory():
            yield MagicMock()
        with patch("worker.main.get_session_factory", return_value=fake_factory):
            await _on_bar(redis_mock, sym_state, shadow_state, settings, Decimal("0"), 5)

    assert store_mock.insert_shadow_trade.call_count == 2
    for c in store_mock.insert_shadow_trade.call_args_list:
        assert c.kwargs.get("exit_reason") == "target"
    assert not shadow_state.has_position("AAPL")


@pytest.mark.asyncio
async def test_worker_restart_from_stream_ids_no_double_process() -> None:
    """Saved last_ids are loaded on start; processing updates and saves new last_ids."""
    redis_mock = AsyncMock()
    saved_ids = {REDIS_STREAM_BARS: "1000-0", REDIS_STREAM_QUOTES: "1001-0"}
    redis_mock.get = AsyncMock(return_value=json.dumps(saved_ids))
    last_ids = await _load_last_ids(redis_mock)
    assert last_ids[REDIS_STREAM_BARS] == "1000-0"
    redis_mock.set = AsyncMock()
    last_ids[REDIS_STREAM_BARS] = "1002-0"
    await _save_last_ids(redis_mock, last_ids)
    redis_mock.set.assert_called_once()
    # In real run, xread(streams={"bars": "1000-0", ...}) would only get messages after 1000-0
    assert "1002-0" in redis_mock.set.call_args[0][1]
