"""
INTRA_EVENT_MOMO / 0.1.0 — shadow-only.
Deterministic features, news tagging, entry/exit rules, reason codes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

# Default ET entry/exit; config overrides
ENTRY_START_ET = "09:35"
ENTRY_END_ET = "11:30"
FORCE_FLAT_ET = "15:45"

STRATEGY_ID = "INTRA_EVENT_MOMO"
STRATEGY_VERSION = "0.1.0"

POSITIVE_KEYWORDS = [
    "beat", "beats", "raise", "raises", "raised", "guidance", "approved", "approval",
    "partnership", "contract", "buyback", "upgrade",
]
NEGATIVE_KEYWORDS = [
    "miss", "misses", "cut", "cuts", "lowered", "downgrade", "offering", "investigation",
    "probe", "delay", "delayed", "lawsuit",
]

# Candidate filters
MIN_PRICE = Decimal("5")
MAX_PRICE = Decimal("500")
MIN_DOLLAR_VOLUME_1M = 1_000_000
MAX_SPREAD_BPS = 20
MIN_ABS_GAP_PCT = Decimal("1.0")
MIN_REL_VOLUME_5M = Decimal("1.5")


@dataclass
class NewsItem:
    """Alpaca news item (headline + summary)."""
    headline: str
    summary: str
    published_at: datetime
    symbol: str | None
    raw: dict[str, Any]


def _parse_news_published(ts: Any) -> datetime | None:
    if ts is None:
        return None
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


def classify_news_side(news_items: list[NewsItem], within_minutes: int = 60) -> str:
    """
    Deterministic rule-based classifier.
    Only consider news published within last within_minutes.
    Returns: 'long' | 'short' | 'neutral'
    """
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=within_minutes)
    positive_hits = 0
    negative_hits = 0
    for n in news_items:
        if n.published_at and n.published_at < cutoff:
            continue
        text = (n.headline or "") + " " + (n.summary or "")
        text_lower = text.lower()
        for kw in POSITIVE_KEYWORDS:
            if kw in text_lower:
                positive_hits += 1
                break
        for kw in NEGATIVE_KEYWORDS:
            if kw in text_lower:
                negative_hits += 1
                break
    if positive_hits > 0 and negative_hits == 0:
        return "long"
    if negative_hits > 0 and positive_hits == 0:
        return "short"
    return "neutral"


def news_keyword_hits(text: str) -> tuple[list[str], list[str]]:
    """Return (positive_matched, negative_matched) for given text."""
    text_lower = (text or "").lower()
    pos: list[str] = []
    neg: list[str] = []
    for kw in POSITIVE_KEYWORDS:
        if kw in text_lower:
            pos.append(kw)
    for kw in NEGATIVE_KEYWORDS:
        if kw in text_lower:
            neg.append(kw)
    return (pos, neg)


@dataclass
class FeatureSet:
    """Per-symbol per-day deterministic features."""
    symbol: str
    ts: datetime
    prev_close: Decimal
    gap_pct_from_prev_close: Decimal
    spread_bps: int
    minute_dollar_volume: Decimal
    rel_volume_5m: Decimal
    opening_range_high: Decimal | None
    opening_range_low: Decimal | None
    session_vwap: Decimal | None
    latest_bid: Decimal | None
    latest_ask: Decimal | None
    latest_last: Decimal | None
    latest_minute_close: Decimal | None
    news_side: str  # long | short | neutral
    news_keyword_hits: list[str]  # matched keywords
    # Derived for audit
    signal_reason_codes: list[str] = field(default_factory=list)


def compute_gap_pct(prev_close: Decimal, current: Decimal) -> Decimal:
    if prev_close is None or prev_close == 0:
        return Decimal("0")
    return ((current - prev_close) / prev_close * 100).quantize(Decimal("0.01"))


@dataclass
class EvalResult:
    """Result of strategy evaluation: no signal, or long/short with reason codes."""
    side: str | None  # None | "buy" | "sell"
    reason_codes: list[str]
    feature_snapshot: dict[str, Any]
    passes_filters: bool
    reject_reason: str | None


def _et_time_in_range(ts: datetime, start_et: str, end_et: str) -> bool:
    """True if ts (UTC) falls within start_et--end_et in America/New_York."""
    try:
        import zoneinfo
        et = zoneinfo.ZoneInfo("America/New_York")
        local = ts.astimezone(et)
        t_str = local.strftime("%H:%M")
        return start_et <= t_str <= end_et
    except Exception:
        return False


def _et_time_after(ts: datetime, et_time: str) -> bool:
    """True if ts (UTC) is at or after et_time in America/New_York."""
    try:
        import zoneinfo
        et = zoneinfo.ZoneInfo("America/New_York")
        local = ts.astimezone(et)
        t_str = local.strftime("%H:%M")
        return t_str >= et_time
    except Exception:
        return False


def evaluate(
    features: FeatureSet,
    *,
    entry_start_et: str = ENTRY_START_ET,
    entry_end_et: str = ENTRY_END_ET,
    force_flat_et: str = FORCE_FLAT_ET,
) -> EvalResult:
    """
    Deterministic evaluation. Returns side=None if no signal or filters not passed.
    """
    reason_codes: list[str] = []
    snapshot: dict[str, Any] = {
        "symbol": features.symbol,
        "ts": features.ts.isoformat() if features.ts else None,
        "prev_close": str(features.prev_close),
        "gap_pct_from_prev_close": str(features.gap_pct_from_prev_close),
        "spread_bps": features.spread_bps,
        "minute_dollar_volume": str(features.minute_dollar_volume),
        "rel_volume_5m": str(features.rel_volume_5m),
        "opening_range_high": str(features.opening_range_high) if features.opening_range_high is not None else None,
        "opening_range_low": str(features.opening_range_low) if features.opening_range_low is not None else None,
        "session_vwap": str(features.session_vwap) if features.session_vwap is not None else None,
        "latest_bid": str(features.latest_bid) if features.latest_bid else None,
        "latest_ask": str(features.latest_ask) if features.latest_ask else None,
        "latest_last": str(features.latest_last) if features.latest_last else None,
        "latest_minute_close": str(features.latest_minute_close) if features.latest_minute_close else None,
        "news_side": features.news_side,
        "news_keyword_hits": features.news_keyword_hits,
    }

    # Time: must be in entry window and before force flat
    if not _et_time_in_range(features.ts, entry_start_et, entry_end_et):
        return EvalResult(
            side=None,
            reason_codes=[],
            feature_snapshot=snapshot,
            passes_filters=False,
            reject_reason="outside_entry_window",
        )
    if _et_time_after(features.ts, force_flat_et):
        return EvalResult(
            side=None,
            reason_codes=[],
            feature_snapshot=snapshot,
            passes_filters=False,
            reject_reason="after_force_flat",
        )

    price = features.latest_last or features.latest_ask or features.latest_bid or Decimal("0")
    if price < MIN_PRICE or price > MAX_PRICE:
        return EvalResult(side=None, reason_codes=[], feature_snapshot=snapshot, passes_filters=False, reject_reason="price_out_of_range")
    if features.opening_range_high is None or features.opening_range_low is None:
        return EvalResult(side=None, reason_codes=[], feature_snapshot=snapshot, passes_filters=False, reject_reason="opening_range_unavailable")
    if features.minute_dollar_volume < MIN_DOLLAR_VOLUME_1M:
        return EvalResult(side=None, reason_codes=[], feature_snapshot=snapshot, passes_filters=False, reject_reason="dollar_volume_below_min")
    if features.spread_bps > MAX_SPREAD_BPS:
        return EvalResult(side=None, reason_codes=[], feature_snapshot=snapshot, passes_filters=False, reject_reason="spread_too_wide")
    if abs(features.gap_pct_from_prev_close) < MIN_ABS_GAP_PCT:
        return EvalResult(side=None, reason_codes=[], feature_snapshot=snapshot, passes_filters=False, reject_reason="gap_too_small")
    if features.rel_volume_5m < MIN_REL_VOLUME_5M:
        return EvalResult(side=None, reason_codes=[], feature_snapshot=snapshot, passes_filters=False, reject_reason="rel_volume_below_min")
    if features.news_side == "neutral":
        return EvalResult(side=None, reason_codes=[], feature_snapshot=snapshot, passes_filters=False, reject_reason="news_neutral")

    close = features.latest_minute_close or price
    vwap = features.session_vwap
    or_high = features.opening_range_high
    or_low = features.opening_range_low

    # Long entry
    if features.news_side == "long":
        if close > or_high and vwap is not None and price > vwap:
            reason_codes.extend(["breakout_above_or_high", "above_vwap", "news_long"])
            snapshot["signal_reason_codes"] = reason_codes
            return EvalResult(side="buy", reason_codes=reason_codes, feature_snapshot=snapshot, passes_filters=True, reject_reason=None)
        # no long signal this bar
        return EvalResult(side=None, reason_codes=[], feature_snapshot=snapshot, passes_filters=True, reject_reason="long_conditions_not_met")

    # Short entry
    if features.news_side == "short":
        if close < or_low and vwap is not None and price < vwap:
            reason_codes.extend(["breakdown_below_or_low", "below_vwap", "news_short"])
            snapshot["signal_reason_codes"] = reason_codes
            return EvalResult(side="sell", reason_codes=reason_codes, feature_snapshot=snapshot, passes_filters=True, reject_reason=None)
        return EvalResult(side=None, reason_codes=[], feature_snapshot=snapshot, passes_filters=True, reject_reason="short_conditions_not_met")

    return EvalResult(side=None, reason_codes=[], feature_snapshot=snapshot, passes_filters=False, reject_reason="news_neutral")


def exit_stop_target_prices(side: str, or_high: Decimal, or_low: Decimal, entry_price: Decimal, r_mult: float = 2.0) -> tuple[Decimal, Decimal]:
    """Long: stop=or_low, target=entry + r*(entry - or_low). Short: stop=or_high, target=entry - r*(or_high - entry)."""
    if side == "buy":
        stop = or_low
        r = entry_price - or_low
        if r <= 0:
            r = entry_price * Decimal("0.01")
        target = entry_price + Decimal(str(r_mult)) * r
        return (stop, target)
    else:
        stop = or_high
        r = or_high - entry_price
        if r <= 0:
            r = entry_price * Decimal("0.01")
        target = entry_price - Decimal(str(r_mult)) * r
        return (stop, target)
