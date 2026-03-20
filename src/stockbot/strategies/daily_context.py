"""
Historical daily bar context: ATR, daily EMAs, average volume.
Fetched once on startup / universe refresh, then updated incrementally.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import logging

logger = logging.getLogger(__name__)


@dataclass
class DailyBar:
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


@dataclass
class DailyContext:
    """Per-symbol daily context computed from historical daily bars."""
    symbol: str
    daily_bars: list[DailyBar] = field(default_factory=list)
    atr_14: Decimal | None = None
    ema_9: Decimal | None = None
    ema_20: Decimal | None = None
    ema_50: Decimal | None = None
    avg_daily_volume: int = 0
    avg_daily_dollar_volume: Decimal = Decimal("0")

    def compute(self) -> None:
        """Recompute all derived values from daily_bars."""
        if not self.daily_bars:
            return
        self.atr_14 = _compute_atr(self.daily_bars, 14)
        closes = [b.close for b in self.daily_bars]
        self.ema_9 = _compute_ema(closes, 9)
        self.ema_20 = _compute_ema(closes, 20)
        self.ema_50 = _compute_ema(closes, 50)
        n = len(self.daily_bars)
        self.avg_daily_volume = sum(b.volume for b in self.daily_bars) // max(n, 1)
        self.avg_daily_dollar_volume = sum(
            (b.high + b.low + b.close) / 3 * b.volume for b in self.daily_bars
        ) / max(n, 1)


def _compute_atr(bars: list[DailyBar], period: int = 14) -> Decimal | None:
    """Standard ATR: average of true ranges over period."""
    if len(bars) < 2:
        return None
    true_ranges: list[Decimal] = []
    for i in range(1, len(bars)):
        high_low = bars[i].high - bars[i].low
        high_prev_close = abs(bars[i].high - bars[i - 1].close)
        low_prev_close = abs(bars[i].low - bars[i - 1].close)
        true_ranges.append(max(high_low, high_prev_close, low_prev_close))
    if not true_ranges:
        return None
    window = true_ranges[-period:] if len(true_ranges) >= period else true_ranges
    return (sum(window) / len(window)).quantize(Decimal("0.0001"))


def _compute_ema(values: list[Decimal], period: int) -> Decimal | None:
    """Exponential moving average on a list of values."""
    if len(values) < period:
        return None
    multiplier = Decimal(2) / (Decimal(period) + 1)
    ema = sum(values[:period]) / period
    for val in values[period:]:
        ema = (val - ema) * multiplier + ema
    return ema.quantize(Decimal("0.01"))


async def fetch_daily_context(symbol: str, lookback_days: int = 25) -> DailyContext:
    """Fetch daily bars from Alpaca and build DailyContext."""
    import asyncio
    ctx = DailyContext(symbol=symbol)
    try:
        from stockbot.alpaca.client import AlpacaClient

        def _fetch() -> list[dict[str, Any]]:
            client = AlpacaClient()
            from datetime import datetime, timedelta, UTC
            end = datetime.now(UTC)
            start = end - timedelta(days=lookback_days + 10)
            return client.get_bars(
                symbol,
                timeframe="1Day",
                start=start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                end=end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                limit=lookback_days,
                feed="iex",
            )

        raw_bars = await asyncio.to_thread(_fetch)
        for b in raw_bars:
            ctx.daily_bars.append(DailyBar(
                open=Decimal(str(b.get("o", b.get("open", 0)))),
                high=Decimal(str(b.get("h", b.get("high", 0)))),
                low=Decimal(str(b.get("l", b.get("low", 0)))),
                close=Decimal(str(b.get("c", b.get("close", 0)))),
                volume=int(b.get("v", b.get("volume", 0))),
            ))
        ctx.compute()
    except Exception as e:
        logger.debug("fetch_daily_context_failed symbol=%s error=%s", symbol, e)
    return ctx
