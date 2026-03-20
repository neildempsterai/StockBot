"""
INTRADAY_CONTINUATION / 0.1.0 — later-session continuation strategy.
Deterministic continuation/reclaim/retest logic for symbols that remain liquid and directional after opening burst.
Optimized for 10:30-14:30 ET window.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

# Default ET entry/exit; config overrides
ENTRY_START_ET = "10:30"
ENTRY_END_ET = "14:30"
FORCE_FLAT_ET = "15:45"

STRATEGY_ID = "INTRADAY_CONTINUATION"
STRATEGY_VERSION = "0.1.0"

# Reuse news classification from open_drive_momo
from stockbot.strategies.open_drive_momo import (
    NewsItem,
    classify_news_side,
    news_keyword_hits,
    FeatureSet as BaseFeatureSet,
)

# Candidate filters (slightly relaxed for later session)
MIN_PRICE = Decimal("5")
MAX_PRICE = Decimal("500")
MIN_DOLLAR_VOLUME_1M = 750_000  # Slightly lower than open-drive
MAX_SPREAD_BPS = 25  # Slightly wider than open-drive
MIN_ABS_GAP_PCT = Decimal("0.5")  # Lower gap requirement
MIN_REL_VOLUME_5M = Decimal("1.2")  # Lower relative volume requirement

# Continuation-specific thresholds
MAX_VWAP_DISTANCE_PCT = Decimal("3.0")  # Price should not be too far from VWAP
MIN_PULLBACK_DEPTH_PCT = Decimal("0.5")  # Minimum pullback from session high/low
MAX_PULLBACK_DEPTH_PCT = Decimal("5.0")  # Maximum pullback (too deep = trend broken)


@dataclass
class FeatureSet(BaseFeatureSet):
    """Extended feature set for continuation strategy."""
    # Additional fields for continuation logic
    session_high: Decimal | None = None  # Session high so far
    session_low: Decimal | None = None  # Session low so far
    pullback_from_high_pct: Decimal | None = None  # % pullback from session high
    pullback_from_low_pct: Decimal | None = None  # % pullback from session low
    vwap_distance_pct: Decimal | None = None  # % distance from VWAP


@dataclass
class EvalResult:
    """Result of strategy evaluation: no signal, or long/short with reason codes."""
    side: str | None  # None | "buy" | "sell"
    reason_codes: list[str]
    feature_snapshot: dict[str, Any]
    passes_filters: bool
    reject_reason: str | None


from stockbot.market_sessions import et_time_in_range as _et_time_in_range  # noqa: E402
from stockbot.market_sessions import et_time_after as _et_time_after  # noqa: E402


def _compute_session_extremes(bars: list) -> tuple[Decimal | None, Decimal | None]:
    """Compute session high and low from bars."""
    if not bars:
        return (None, None)
    session_high = max(b.high for b in bars)
    session_low = min(b.low for b in bars)
    return (session_high, session_low)


def _compute_pullback_pct(current: Decimal, extreme: Decimal, is_high: bool) -> Decimal | None:
    """Compute pullback % from session extreme."""
    if extreme is None or current is None:
        return None
    if is_high:
        # Pullback from high: (high - current) / high * 100
        if extreme == 0:
            return None
        return ((extreme - current) / extreme * 100).quantize(Decimal("0.01"))
    else:
        # Pullback from low: (current - low) / low * 100
        if extreme == 0:
            return None
        return ((current - extreme) / extreme * 100).quantize(Decimal("0.01"))


def _compute_vwap_distance_pct(price: Decimal, vwap: Decimal | None) -> Decimal | None:
    """Compute % distance from VWAP."""
    if vwap is None or price is None or vwap == 0:
        return None
    return abs((price - vwap) / vwap * 100).quantize(Decimal("0.01"))


def evaluate(
    features: FeatureSet,
    *,
    entry_start_et: str = ENTRY_START_ET,
    entry_end_et: str = ENTRY_END_ET,
    force_flat_et: str = FORCE_FLAT_ET,
    session_bars: list | None = None,  # All session bars for computing extremes
) -> EvalResult:
    """
    Deterministic continuation strategy evaluation.
    Looks for pullback/retest/reclaim setups in later session.
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
    if features.minute_dollar_volume < MIN_DOLLAR_VOLUME_1M:
        return EvalResult(side=None, reason_codes=[], feature_snapshot=snapshot, passes_filters=False, reject_reason="dollar_volume_below_min")
    if features.spread_bps > MAX_SPREAD_BPS:
        return EvalResult(side=None, reason_codes=[], feature_snapshot=snapshot, passes_filters=False, reject_reason="spread_too_wide")
    if abs(features.gap_pct_from_prev_close) < MIN_ABS_GAP_PCT:
        return EvalResult(side=None, reason_codes=[], feature_snapshot=snapshot, passes_filters=False, reject_reason="gap_too_small")
    if features.rel_volume_5m < MIN_REL_VOLUME_5M:
        return EvalResult(side=None, reason_codes=[], feature_snapshot=snapshot, passes_filters=False, reject_reason="rel_volume_below_min")

    # Compute session extremes if bars provided
    session_high = features.session_high
    session_low = features.session_low
    if session_high is None or session_low is None:
        if session_bars:
            session_high, session_low = _compute_session_extremes(session_bars)
            snapshot["session_high"] = str(session_high) if session_high else None
            snapshot["session_low"] = str(session_low) if session_low else None
        else:
            # Fallback: use opening range if available
            session_high = features.opening_range_high
            session_low = features.opening_range_low
            snapshot["session_high"] = str(session_high) if session_high else None
            snapshot["session_low"] = str(session_low) if session_low else None

    if session_high is None or session_low is None:
        return EvalResult(side=None, reason_codes=[], feature_snapshot=snapshot, passes_filters=False, reject_reason="session_extremes_unavailable")

    # Compute VWAP distance
    vwap = features.session_vwap
    vwap_distance = _compute_vwap_distance_pct(price, vwap)
    snapshot["vwap_distance_pct"] = str(vwap_distance) if vwap_distance else None

    if vwap_distance is not None and vwap_distance > MAX_VWAP_DISTANCE_PCT:
        return EvalResult(side=None, reason_codes=[], feature_snapshot=snapshot, passes_filters=False, reject_reason="too_far_from_vwap")

    # Compute pullbacks
    pullback_from_high = _compute_pullback_pct(price, session_high, is_high=True)
    pullback_from_low = _compute_pullback_pct(price, session_low, is_high=False)
    snapshot["pullback_from_high_pct"] = str(pullback_from_high) if pullback_from_high else None
    snapshot["pullback_from_low_pct"] = str(pullback_from_low) if pullback_from_low else None

    close = features.latest_minute_close or price

    # Long continuation: price pulled back from session high, now reclaiming
    # News should be long or neutral (not short)
    if features.news_side != "short":
        # Check for pullback then reclaim
        if pullback_from_high is not None:
            if MIN_PULLBACK_DEPTH_PCT <= pullback_from_high <= MAX_PULLBACK_DEPTH_PCT:
                # Price has pulled back from high, check for reclaim
                if close > session_high * Decimal("0.995"):  # Reclaiming within 0.5% of session high
                    if vwap is not None and price > vwap * Decimal("0.998"):  # Near or above VWAP
                        reason_codes.extend(["continuation_long", "reclaim_session_high", "above_vwap"])
                        if features.news_side == "long":
                            reason_codes.append("news_long")
                        snapshot["signal_reason_codes"] = reason_codes
                        return EvalResult(side="buy", reason_codes=reason_codes, feature_snapshot=snapshot, passes_filters=True, reject_reason=None)
                # Or check for VWAP reclaim after pullback
                if vwap is not None and close > vwap and pullback_from_high <= Decimal("2.0"):
                    reason_codes.extend(["continuation_long", "vwap_reclaim", "pullback_from_high"])
                    if features.news_side == "long":
                        reason_codes.append("news_long")
                    snapshot["signal_reason_codes"] = reason_codes
                    return EvalResult(side="buy", reason_codes=reason_codes, feature_snapshot=snapshot, passes_filters=True, reject_reason=None)

    # Short continuation: price pulled back from session low, now breaking down further
    # News should be short or neutral (not long)
    if features.news_side != "long":
        # Check for pullback then breakdown
        if pullback_from_low is not None:
            if MIN_PULLBACK_DEPTH_PCT <= pullback_from_low <= MAX_PULLBACK_DEPTH_PCT:
                # Price has pulled back from low, check for breakdown
                if close < session_low * Decimal("1.005"):  # Breaking down within 0.5% of session low
                    if vwap is not None and price < vwap * Decimal("1.002"):  # Near or below VWAP
                        reason_codes.extend(["continuation_short", "breakdown_session_low", "below_vwap"])
                        if features.news_side == "short":
                            reason_codes.append("news_short")
                        snapshot["signal_reason_codes"] = reason_codes
                        return EvalResult(side="sell", reason_codes=reason_codes, feature_snapshot=snapshot, passes_filters=True, reject_reason=None)
                # Or check for VWAP breakdown after pullback
                if vwap is not None and close < vwap and pullback_from_low <= Decimal("2.0"):
                    reason_codes.extend(["continuation_short", "vwap_breakdown", "pullback_from_low"])
                    if features.news_side == "short":
                        reason_codes.append("news_short")
                    snapshot["signal_reason_codes"] = reason_codes
                    return EvalResult(side="sell", reason_codes=reason_codes, feature_snapshot=snapshot, passes_filters=True, reject_reason=None)

    # No continuation signal
    return EvalResult(side=None, reason_codes=[], feature_snapshot=snapshot, passes_filters=True, reject_reason="continuation_conditions_not_met")


def exit_stop_target_prices(
    side: str,
    entry_price: Decimal,
    session_high: Decimal | None,
    session_low: Decimal | None,
    vwap: Decimal | None,
    r_mult: float = 2.0,
) -> tuple[Decimal, Decimal]:
    """
    Continuation strategy stop/target logic.
    Long: stop at recent pullback low or below VWAP, target at session high extension
    Short: stop at recent pullback high or above VWAP, target at session low extension
    """
    if side == "buy":
        # Stop: use session low or VWAP as reference
        if session_low is not None and session_low < entry_price:
            stop = session_low * Decimal("0.995")  # Slightly below session low
        elif vwap is not None:
            stop = vwap * Decimal("0.995")  # Slightly below VWAP
        else:
            stop = entry_price * Decimal("0.98")  # Fallback: 2% stop
        
        r = entry_price - stop
        if r <= 0:
            r = entry_price * Decimal("0.01")
        
        # Target: session high extension or R multiple
        if session_high is not None and session_high > entry_price:
            target = max(entry_price + Decimal(str(r_mult)) * r, session_high * Decimal("1.01"))
        else:
            target = entry_price + Decimal(str(r_mult)) * r
        
        return (stop, target)
    else:
        # Stop: use session high or VWAP as reference
        if session_high is not None and session_high > entry_price:
            stop = session_high * Decimal("1.005")  # Slightly above session high
        elif vwap is not None:
            stop = vwap * Decimal("1.005")  # Slightly above VWAP
        else:
            stop = entry_price * Decimal("1.02")  # Fallback: 2% stop
        
        r = stop - entry_price
        if r <= 0:
            r = entry_price * Decimal("0.01")
        
        # Target: session low extension or R multiple
        if session_low is not None and session_low < entry_price:
            target = min(entry_price - Decimal(str(r_mult)) * r, session_low * Decimal("0.99"))
        else:
            target = entry_price - Decimal(str(r_mult)) * r
        
        return (stop, target)
