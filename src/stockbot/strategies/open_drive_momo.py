"""
OPEN_DRIVE_MOMO / 0.2.0 — aggressive opening momentum strategy.
Differentiated from INTRA_EVENT_MOMO: tighter window (09:35-10:00),
higher conviction thresholds (gap >2%, RVol >2.0x), aggressive OR breakout
with 0.5% buffer. Pure opening-drive scalp play.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

ENTRY_START_ET = "09:35"
ENTRY_END_ET = "10:00"
FORCE_FLAT_ET = "15:45"

STRATEGY_ID = "OPEN_DRIVE_MOMO"
STRATEGY_VERSION = "0.2.0"

from stockbot.strategies.intra_event_momo import (  # noqa: E402
    classify_news_side,
    news_keyword_hits,
    FeatureSet,
    NewsItem,
)
from stockbot.strategies.types import EvalResult
from stockbot.market_sessions import et_time_in_range as _et_time_in_range
from stockbot.market_sessions import et_time_after as _et_time_after

MIN_PRICE = Decimal("5")
MAX_PRICE = Decimal("500")
MIN_DOLLAR_VOLUME_1M = 1_500_000
MAX_SPREAD_BPS = 15
MIN_ABS_GAP_PCT = Decimal("2.0")
MIN_REL_VOLUME_5M = Decimal("2.0")
BREAKOUT_BUFFER_PCT = Decimal("0.005")


def evaluate(
    features: FeatureSet,
    *,
    entry_start_et: str = ENTRY_START_ET,
    entry_end_et: str = ENTRY_END_ET,
    force_flat_et: str = FORCE_FLAT_ET,
) -> EvalResult:
    """Aggressive opening-drive evaluation with higher conviction thresholds."""
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

    if not _et_time_in_range(features.ts, entry_start_et, entry_end_et):
        return EvalResult(side=None, reason_codes=[], feature_snapshot=snapshot, passes_filters=False, reject_reason="outside_entry_window")
    if _et_time_after(features.ts, force_flat_et):
        return EvalResult(side=None, reason_codes=[], feature_snapshot=snapshot, passes_filters=False, reject_reason="after_force_flat")

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

    close = features.latest_minute_close or price
    vwap = features.session_vwap
    or_high = features.opening_range_high
    or_low = features.opening_range_low

    breakout_long_level = or_high * (1 + BREAKOUT_BUFFER_PCT)
    breakout_short_level = or_low * (1 - BREAKOUT_BUFFER_PCT)

    # Long: aggressive breakout above OR high with buffer, above VWAP
    # News is a booster, not a hard gate -- pure volume/price can trigger
    if close > breakout_long_level and vwap is not None and price > vwap:
        reason_codes.extend(["aggressive_breakout_above_or", "above_vwap"])
        if features.news_side == "long":
            reason_codes.append("news_long")
        elif features.news_side == "short":
            return EvalResult(side=None, reason_codes=[], feature_snapshot=snapshot, passes_filters=True, reject_reason="news_conflicts_long_setup")
        snapshot["signal_reason_codes"] = reason_codes
        return EvalResult(side="buy", reason_codes=reason_codes, feature_snapshot=snapshot, passes_filters=True, reject_reason=None)

    # Short: aggressive breakdown below OR low with buffer, below VWAP
    if close < breakout_short_level and vwap is not None and price < vwap:
        reason_codes.extend(["aggressive_breakdown_below_or", "below_vwap"])
        if features.news_side == "short":
            reason_codes.append("news_short")
        elif features.news_side == "long":
            return EvalResult(side=None, reason_codes=[], feature_snapshot=snapshot, passes_filters=True, reject_reason="news_conflicts_short_setup")
        snapshot["signal_reason_codes"] = reason_codes
        return EvalResult(side="sell", reason_codes=reason_codes, feature_snapshot=snapshot, passes_filters=True, reject_reason=None)

    return EvalResult(side=None, reason_codes=[], feature_snapshot=snapshot, passes_filters=True, reject_reason="breakout_conditions_not_met")


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
