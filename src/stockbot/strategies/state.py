"""Per-symbol intraday state for INTRA_EVENT_MOMO: bars, vwap, opening range, news."""
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
