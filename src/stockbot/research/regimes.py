"""Simple regime classification from SPY rolling trend (deterministic)."""
from __future__ import annotations

from decimal import Decimal
from typing import Literal

from stockbot.strategies.state import BarLike

RegimeLabel = Literal["bull", "bear", "sideways"]


def classify_regime_spy(
    bars: list[BarLike],
    *,
    symbol: str = "SPY",
    lookback_bars: int = 20,
) -> RegimeLabel:
    """
    Classify regime from SPY close series: rolling return over lookback_bars.
    bull if return > 1%, bear if < -1%, else sideways.
    """
    spy_bars = [b for b in bars if b.symbol == symbol]
    if len(spy_bars) < lookback_bars:
        return "sideways"
    recent = spy_bars[-lookback_bars:]
    start_close = recent[0].close
    end_close = recent[-1].close
    if start_close is None or start_close <= 0:
        return "sideways"
    ret_pct = (end_close - start_close) / start_close * 100
    if ret_pct >= Decimal("1"):
        return "bull"
    if ret_pct <= Decimal("-1"):
        return "bear"
    return "sideways"
