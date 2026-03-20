"""Tests for market regime detection."""
from decimal import Decimal
from datetime import datetime, UTC
from stockbot.strategies.regime import detect_regime, MarketRegime
from stockbot.strategies.state import SymbolState, BarLike
from stockbot.strategies.daily_context import DailyContext, DailyBar


def _make_spy_state(prices: list[float], rising: bool = True) -> SymbolState:
    s = SymbolState(symbol="SPY")
    for i, p in enumerate(prices):
        s.bars.append(BarLike(
            symbol="SPY",
            open=Decimal(str(p - 0.5)),
            high=Decimal(str(p + 1)),
            low=Decimal(str(p - 1)),
            close=Decimal(str(p)),
            volume=100000,
            timestamp=datetime(2026, 3, 20, 14, i, tzinfo=UTC),
        ))
    return s


class TestRegimeDetection:
    def test_no_spy_returns_unknown(self):
        regime = detect_regime(None, None)
        assert regime.label == "unknown"
        assert regime.confidence == 0.0

    def test_empty_spy_returns_unknown(self):
        regime = detect_regime(SymbolState(symbol="SPY"), None)
        assert regime.label == "unknown"

    def test_basic_bullish(self):
        prices = [float(400 + i * 0.5) for i in range(40)]
        spy = _make_spy_state(prices)
        regime = detect_regime(spy, None)
        assert regime.label in ("trending_up", "choppy", "unknown")
        assert regime.spy_above_vwap is not None

    def test_trailing_multiplier_trending_up(self):
        r = MarketRegime(label="trending_up", spy_above_vwap=True, spy_trend_5m="up", spy_atr=Decimal("5"), confidence=0.9)
        assert r.trailing_stop_multiplier == Decimal("1.0")

    def test_trailing_multiplier_choppy(self):
        r = MarketRegime(label="choppy", spy_above_vwap=False, spy_trend_5m="flat", spy_atr=Decimal("5"), confidence=0.5)
        assert r.trailing_stop_multiplier == Decimal("0.6")

    def test_quality_score_adjustment_long_bullish(self):
        r = MarketRegime(label="trending_up", spy_above_vwap=True, spy_trend_5m="up", spy_atr=Decimal("5"), confidence=0.9)
        assert r.quality_score_adjustment("buy") == 10
        assert r.quality_score_adjustment("sell") == -10

    def test_is_trending(self):
        r = MarketRegime(label="trending_down", spy_above_vwap=False, spy_trend_5m="down", spy_atr=Decimal("5"), confidence=0.8)
        assert r.is_trending is True
        r2 = MarketRegime(label="choppy", spy_above_vwap=False, spy_trend_5m="flat", spy_atr=Decimal("5"), confidence=0.5)
        assert r2.is_trending is False
