"""
Market regime detection from SPY intraday data.
Classifies current market environment to adapt strategy behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from stockbot.strategies.state import SymbolState
from stockbot.strategies.daily_context import DailyContext, _compute_ema


@dataclass
class MarketRegime:
    """Current market regime classification."""
    label: str  # trending_up | trending_down | choppy | unknown
    spy_above_vwap: bool
    spy_trend_5m: str  # up | down | flat
    spy_atr: Decimal | None
    confidence: float  # 0.0 - 1.0

    @property
    def is_trending(self) -> bool:
        return self.label in ("trending_up", "trending_down")

    @property
    def trailing_stop_multiplier(self) -> Decimal:
        """Regime-adjusted trailing stop multiplier.

        Trending: standard (1.0x) -- let winners run.
        Counter-trend: tighter (0.7x) -- take profits faster.
        Choppy: tightest (0.6x) -- quick profits, tight trails.
        """
        if self.label == "trending_up":
            return Decimal("1.0")
        if self.label == "trending_down":
            return Decimal("0.85")
        if self.label == "choppy":
            return Decimal("0.6")
        return Decimal("0.8")

    def quality_score_adjustment(self, side: str) -> int:
        """Score adjustment based on regime alignment with trade direction."""
        if side == "buy":
            if self.label == "trending_up":
                return 10
            if self.label == "trending_down":
                return -10
            if self.label == "choppy":
                return -5
        elif side == "sell":
            if self.label == "trending_down":
                return 10
            if self.label == "trending_up":
                return -10
            if self.label == "choppy":
                return -5
        return 0


def detect_regime(
    spy_state: SymbolState | None,
    spy_daily: DailyContext | None,
) -> MarketRegime:
    """Classify market regime from SPY intraday and daily data."""
    if spy_state is None or not spy_state.bars:
        return MarketRegime(
            label="unknown", spy_above_vwap=False, spy_trend_5m="flat",
            spy_atr=None, confidence=0.0,
        )

    vwap = spy_state.session_vwap()
    current_price = spy_state.bars[-1].close
    spy_above_vwap = current_price > vwap if vwap else False

    trend_5m = _compute_5m_trend(spy_state)
    spy_atr = spy_daily.atr_14 if spy_daily else None

    signals_up = 0
    signals_down = 0
    signals_total = 0

    if spy_above_vwap:
        signals_up += 1
    else:
        signals_down += 1
    signals_total += 1

    if trend_5m == "up":
        signals_up += 1
    elif trend_5m == "down":
        signals_down += 1
    signals_total += 1

    if spy_daily and spy_daily.ema_9 and spy_daily.ema_20:
        if spy_daily.ema_9 > spy_daily.ema_20:
            signals_up += 1
        else:
            signals_down += 1
        signals_total += 1

    if len(spy_state.bars) >= 30:
        recent_range = max(b.high for b in spy_state.bars[-30:]) - min(b.low for b in spy_state.bars[-30:])
        if spy_atr and spy_atr > 0:
            range_vs_atr = recent_range / spy_atr
            if range_vs_atr < Decimal("0.3"):
                label = "choppy"
                confidence = 0.7
                return MarketRegime(
                    label=label, spy_above_vwap=spy_above_vwap,
                    spy_trend_5m=trend_5m, spy_atr=spy_atr, confidence=confidence,
                )

    if signals_total == 0:
        label = "unknown"
        confidence = 0.0
    elif signals_up >= 2 and signals_down == 0:
        label = "trending_up"
        confidence = min(1.0, signals_up / signals_total)
    elif signals_down >= 2 and signals_up == 0:
        label = "trending_down"
        confidence = min(1.0, signals_down / signals_total)
    elif abs(signals_up - signals_down) <= 1:
        label = "choppy"
        confidence = 0.5
    else:
        label = "trending_up" if signals_up > signals_down else "trending_down"
        confidence = max(signals_up, signals_down) / signals_total

    return MarketRegime(
        label=label, spy_above_vwap=spy_above_vwap,
        spy_trend_5m=trend_5m, spy_atr=spy_atr, confidence=confidence,
    )


def _compute_5m_trend(sym_state: SymbolState) -> str:
    """Compute 5-minute trend direction from 9 vs 20 EMA on 5m bars."""
    bars_5m = sym_state.bars_5m()
    if len(bars_5m) < 20:
        return "flat"
    closes = [b.close for b in bars_5m]
    ema9 = _compute_ema(closes, 9)
    ema20 = _compute_ema(closes, 20)
    if ema9 is None or ema20 is None:
        return "flat"
    diff_pct = (ema9 - ema20) / ema20 * 100
    if diff_pct > Decimal("0.05"):
        return "up"
    elif diff_pct < Decimal("-0.05"):
        return "down"
    return "flat"
