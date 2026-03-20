"""Per-symbol intraday state: bars, vwap, opening range, news, multi-timeframe."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from stockbot.strategies.intra_event_momo import NewsItem


@dataclass
class BarLike:
    symbol: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    timestamp: datetime


@dataclass
class SymbolState:
    symbol: str
    bars: list[BarLike] = field(default_factory=list)
    latest_bid: Decimal | None = None
    latest_ask: Decimal | None = None
    latest_last: Decimal | None = None
    latest_quote_ts: datetime | None = None
    news: list[NewsItem] = field(default_factory=list)
    prev_close: Decimal | None = None
    latest_bid_size: int | None = None
    latest_ask_size: int | None = None

    def session_open(self) -> Decimal | None:
        """Session open price: first bar's open."""
        if not self.bars:
            return None
        return self.bars[0].open

    def gap_pct(self) -> Decimal:
        """True gap: (session_open - prev_close) / prev_close * 100."""
        s_open = self.session_open()
        if s_open is None or self.prev_close is None or self.prev_close == 0:
            return Decimal("0")
        return ((s_open - self.prev_close) / self.prev_close * 100).quantize(Decimal("0.01"))

    def opening_range(self) -> tuple[Decimal | None, Decimal | None]:
        """First 5 minutes: high and low. Returns (or_high, or_low) or (None, None)."""
        if len(self.bars) < 5:
            return (None, None)
        first5 = self.bars[:5]
        or_high = max(b.high for b in first5)
        or_low = min(b.low for b in first5)
        return (or_high, or_low)

    def session_vwap(self) -> Decimal | None:
        """VWAP so far: sum(typical*vol)/sum(vol)."""
        if not self.bars:
            return None
        total_tp = Decimal("0")
        total_vol = 0
        for b in self.bars:
            typical = (b.high + b.low + b.close) / 3
            total_tp += typical * b.volume
            total_vol += b.volume
        if total_vol == 0:
            return None
        return (total_tp / total_vol).quantize(Decimal("0.01"))

    def dollar_volume_5m(self) -> Decimal:
        """Sum of (typical_price * volume) for last 5 bars."""
        last5 = self.bars[-5:] if len(self.bars) >= 5 else self.bars
        total = Decimal("0")
        for b in last5:
            typical = (b.high + b.low + b.close) / 3
            total += typical * b.volume
        return total

    def rel_volume_5m(self) -> Decimal:
        """Intraday relative volume: last-5-bar avg dollar volume vs session avg.

        Compares recent activity to today's average per-bar dollar volume.
        Returns ratio (>1 means recent bars are busier than today's average).
        Falls back to 1.0 if insufficient data.
        """
        if len(self.bars) < 6:
            return Decimal("1")
        recent_bars = self.bars[-5:]
        recent_dv = Decimal("0")
        for b in recent_bars:
            typical = (b.high + b.low + b.close) / 3
            recent_dv += typical * b.volume
        recent_avg = recent_dv / 5

        all_dv = Decimal("0")
        for b in self.bars:
            typical = (b.high + b.low + b.close) / 3
            all_dv += typical * b.volume
        session_avg = all_dv / len(self.bars)

        if session_avg == 0:
            return Decimal("1")
        return (recent_avg / session_avg).quantize(Decimal("0.01"))

    def last_bar(self) -> BarLike | None:
        return self.bars[-1] if self.bars else None

    # --- Multi-timeframe aggregation ---

    def bars_5m(self) -> list[BarLike]:
        """Aggregate 1-minute bars into 5-minute candles."""
        return self._aggregate_bars(5)

    def bars_15m(self) -> list[BarLike]:
        """Aggregate 1-minute bars into 15-minute candles."""
        return self._aggregate_bars(15)

    def _aggregate_bars(self, period: int) -> list[BarLike]:
        if len(self.bars) < period:
            return []
        result: list[BarLike] = []
        for i in range(0, len(self.bars) - period + 1, period):
            chunk = self.bars[i:i + period]
            result.append(BarLike(
                symbol=self.symbol,
                open=chunk[0].open,
                high=max(b.high for b in chunk),
                low=min(b.low for b in chunk),
                close=chunk[-1].close,
                volume=sum(b.volume for b in chunk),
                timestamp=chunk[-1].timestamp,
            ))
        return result

    def ema_on_bars(self, bars: list[BarLike], period: int) -> Decimal | None:
        """EMA on a list of bars' close prices."""
        if len(bars) < period:
            return None
        closes = [b.close for b in bars]
        multiplier = Decimal(2) / (Decimal(period) + 1)
        ema = sum(closes[:period]) / period
        for val in closes[period:]:
            ema = (val - ema) * multiplier + ema
        return ema.quantize(Decimal("0.01"))

    def trend_direction_5m(self) -> str:
        """5-minute trend: 'up' if 9 EMA > 20 EMA, 'down' if <, 'flat' otherwise."""
        bars = self.bars_5m()
        if len(bars) < 20:
            return "flat"
        ema9 = self.ema_on_bars(bars, 9)
        ema20 = self.ema_on_bars(bars, 20)
        if ema9 is None or ema20 is None:
            return "flat"
        diff_pct = (ema9 - ema20) / ema20 * 100
        if diff_pct > Decimal("0.05"):
            return "up"
        elif diff_pct < Decimal("-0.05"):
            return "down"
        return "flat"

    def bid_ask_imbalance(self) -> Decimal | None:
        """Order imbalance from bid/ask sizes. Range [-1, +1].

        Positive = more bid pressure (bullish).
        Negative = more ask pressure (bearish).
        """
        if self.latest_bid_size is None or self.latest_ask_size is None:
            return None
        total = self.latest_bid_size + self.latest_ask_size
        if total == 0:
            return Decimal("0")
        return (Decimal(self.latest_bid_size - self.latest_ask_size) / total).quantize(Decimal("0.01"))

    def morning_move_strength(self, atr: Decimal | None) -> Decimal | None:
        """How far price has traveled from open relative to ATR.

        Returns ratio: (session_high - session_open) / ATR for bullish,
        (session_open - session_low) / ATR for bearish.
        Uses the larger of the two moves.
        """
        if not self.bars or atr is None or atr <= 0:
            return None
        s_open = self.bars[0].open
        s_high = max(b.high for b in self.bars)
        s_low = min(b.low for b in self.bars)
        up_move = (s_high - s_open) / atr
        down_move = (s_open - s_low) / atr
        return max(up_move, down_move).quantize(Decimal("0.01"))
