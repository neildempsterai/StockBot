"""INTRA_EVENT_MOMO signal generation and filters."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from stockbot.strategies.intra_event_momo import (
    FeatureSet,
    evaluate,
    MIN_PRICE,
    MAX_PRICE,
    MIN_DOLLAR_VOLUME_1M,
    MAX_SPREAD_BPS,
    MIN_ABS_GAP_PCT,
    MIN_REL_VOLUME_5M,
)


def _features(
    symbol: str = "AAPL",
    news_side: str = "long",
    close_above_or_high: bool = True,
    price_above_vwap: bool = True,
    spread_bps: int = 10,
    gap_pct: Decimal = Decimal("1.5"),
    minute_dollar_volume: Decimal = Decimal("2000000"),
    rel_volume_5m: Decimal = Decimal("2.0"),
    price: Decimal = Decimal("150"),
) -> FeatureSet:
    or_high = Decimal("148")
    or_low = Decimal("146")
    vwap = Decimal("147")
    return FeatureSet(
        symbol=symbol,
        ts=datetime(2026, 3, 17, 14, 35, 0, tzinfo=timezone.utc),
        prev_close=Decimal("145"),
        gap_pct_from_prev_close=gap_pct,
        spread_bps=spread_bps,
        minute_dollar_volume=minute_dollar_volume,
        rel_volume_5m=rel_volume_5m,
        opening_range_high=or_high,
        opening_range_low=or_low,
        session_vwap=vwap,
        latest_bid=price - Decimal("0.01"),
        latest_ask=price + Decimal("0.01"),
        latest_last=price,
        latest_minute_close=or_high + Decimal("1") if close_above_or_high else or_high - Decimal("1"),
        news_side=news_side,
        news_keyword_hits=[],
    )


def test_long_signal_generation() -> None:
    f = _features(news_side="long", close_above_or_high=True, price_above_vwap=True)
    r = evaluate(f)
    assert r.passes_filters
    assert r.side == "buy"


def test_short_signal_generation() -> None:
    or_high = Decimal("152")
    or_low = Decimal("150")
    vwap = Decimal("151")
    f = FeatureSet(
        symbol="AAPL",
        ts=datetime(2026, 3, 17, 14, 35, 0, tzinfo=timezone.utc),
        prev_close=Decimal("155"),
        gap_pct_from_prev_close=Decimal("-1.5"),
        spread_bps=10,
        minute_dollar_volume=Decimal("2000000"),
        rel_volume_5m=Decimal("2.0"),
        opening_range_high=or_high,
        opening_range_low=or_low,
        session_vwap=vwap,
        latest_bid=Decimal("149"),
        latest_ask=Decimal("149.02"),
        latest_last=Decimal("149"),
        latest_minute_close=or_low - Decimal("1"),
        news_side="short",
        news_keyword_hits=[],
    )
    r = evaluate(f)
    assert r.passes_filters
    assert r.side == "sell"


def test_reject_spread_too_wide() -> None:
    f = _features(spread_bps=50)
    r = evaluate(f)
    assert not r.passes_filters
    assert r.reject_reason == "spread_too_wide"


def test_reject_news_neutral() -> None:
    f = _features(news_side="neutral")
    r = evaluate(f)
    assert not r.passes_filters
    assert r.reject_reason == "news_neutral"


def test_reject_gap_too_small() -> None:
    f = _features(gap_pct=Decimal("0.5"))
    r = evaluate(f)
    assert not r.passes_filters
    assert r.reject_reason == "gap_too_small"
