"""
SWING_EVENT_CONTINUATION / 0.1.0 — 1–5 day event-driven continuation strategy.
Deterministic: catalyst-supported symbols with strong close / reclaim behavior,
acceptable liquidity, and constructive daily structure.
Entry window: 13:00–15:30 ET (assess full-day action before entering).
No intraday force-flat. Overnight carry is explicit and expected.
Shadow-only by default.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

STRATEGY_ID = "SWING_EVENT_CONTINUATION"
STRATEGY_VERSION = "0.1.0"

ENTRY_START_ET = "13:00"
ENTRY_END_ET = "15:30"
# No force-flat for swing — positions carry overnight
FORCE_FLAT_ET: str | None = None

MAX_HOLD_DAYS = 5
HOLDING_PERIOD_TYPE = "swing"

# --- Candidate filters ---
MIN_PRICE = Decimal("5")
MAX_PRICE = Decimal("500")
MIN_AVG_DAILY_DOLLAR_VOLUME = Decimal("5000000")
MAX_SPREAD_BPS = 30
MAX_GAP_FROM_PREV_CLOSE_PCT = Decimal("10.0")
MAX_EXTENSION_FROM_REFERENCE_PCT = Decimal("15.0")
MIN_REL_VOLUME_5M = Decimal("1.0")
MIN_CATALYST_STRENGTH = 3

# --- Daily structure thresholds ---
STRONG_CLOSE_TOP_PCT = Decimal("25")
RECLAIM_TOLERANCE_PCT = Decimal("0.5")

# --- Stop / target ---
DEFAULT_STOP_PCT = Decimal("3.0")
DEFAULT_R_MULT = Decimal("2.0")

# Reuse news classification from open_drive_momo
from stockbot.strategies.open_drive_momo import (
    NewsItem,
    classify_news_side,
    news_keyword_hits as _news_keyword_hits,
)


@dataclass
class DailyBar:
    """Prior-day or multi-day daily bar for swing features."""
    date: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


@dataclass
class SwingFeatureSet:
    """Per-symbol deterministic features for swing evaluation."""
    symbol: str
    ts: datetime

    # Current intraday state
    latest_bid: Decimal | None
    latest_ask: Decimal | None
    latest_last: Decimal | None
    latest_minute_close: Decimal | None
    spread_bps: int
    session_vwap: Decimal | None
    rel_volume_5m: Decimal
    intraday_high: Decimal | None
    intraday_low: Decimal | None

    # Daily / multi-day context
    prev_close: Decimal | None
    prev_high: Decimal | None
    prev_low: Decimal | None
    prev_daily_range: Decimal | None
    day_2_low: Decimal | None
    avg_daily_dollar_volume: Decimal | None
    gap_pct_from_prev_close: Decimal | None
    close_position_in_range_pct: Decimal | None
    extension_from_reference_pct: Decimal | None

    # Catalyst / research
    news_side: str
    news_keyword_hits: list[str]
    scrappy_catalyst_direction: str | None
    scrappy_catalyst_strength: int | None
    scrappy_stale: bool
    scrappy_conflict: bool

    signal_reason_codes: list[str] = field(default_factory=list)


@dataclass
class SwingEvalResult:
    """Result of swing strategy evaluation."""
    side: str | None
    reason_codes: list[str]
    feature_snapshot: dict[str, Any]
    passes_filters: bool
    reject_reason: str | None


def _et_time_in_range(ts: datetime, start_et: str, end_et: str) -> bool:
    try:
        import zoneinfo
        et = zoneinfo.ZoneInfo("America/New_York")
        local = ts.astimezone(et)
        t_str = local.strftime("%H:%M")
        return start_et <= t_str <= end_et
    except Exception:
        return False


def compute_close_position_in_range_pct(
    close: Decimal, high: Decimal, low: Decimal
) -> Decimal | None:
    """Where close sits in the day's range: 100 = closed at high, 0 = closed at low."""
    if high is None or low is None or high == low:
        return None
    return ((close - low) / (high - low) * 100).quantize(Decimal("0.01"))


def compute_gap_pct(prev_close: Decimal | None, current: Decimal) -> Decimal | None:
    if prev_close is None or prev_close == 0:
        return None
    return ((current - prev_close) / prev_close * 100).quantize(Decimal("0.01"))


def compute_extension_from_reference(
    price: Decimal, reference: Decimal | None
) -> Decimal | None:
    if reference is None or reference == 0:
        return None
    return (abs(price - reference) / reference * 100).quantize(Decimal("0.01"))


def _build_snapshot(features: SwingFeatureSet) -> dict[str, Any]:
    return {
        "symbol": features.symbol,
        "ts": features.ts.isoformat() if features.ts else None,
        "prev_close": str(features.prev_close) if features.prev_close else None,
        "prev_high": str(features.prev_high) if features.prev_high else None,
        "prev_low": str(features.prev_low) if features.prev_low else None,
        "gap_pct": str(features.gap_pct_from_prev_close) if features.gap_pct_from_prev_close else None,
        "spread_bps": features.spread_bps,
        "avg_daily_dollar_volume": str(features.avg_daily_dollar_volume) if features.avg_daily_dollar_volume else None,
        "rel_volume_5m": str(features.rel_volume_5m),
        "close_position_in_range_pct": str(features.close_position_in_range_pct) if features.close_position_in_range_pct else None,
        "extension_from_reference_pct": str(features.extension_from_reference_pct) if features.extension_from_reference_pct else None,
        "session_vwap": str(features.session_vwap) if features.session_vwap else None,
        "intraday_high": str(features.intraday_high) if features.intraday_high else None,
        "intraday_low": str(features.intraday_low) if features.intraday_low else None,
        "latest_bid": str(features.latest_bid) if features.latest_bid else None,
        "latest_ask": str(features.latest_ask) if features.latest_ask else None,
        "latest_last": str(features.latest_last) if features.latest_last else None,
        "latest_minute_close": str(features.latest_minute_close) if features.latest_minute_close else None,
        "news_side": features.news_side,
        "news_keyword_hits": features.news_keyword_hits,
        "scrappy_catalyst_direction": features.scrappy_catalyst_direction,
        "scrappy_catalyst_strength": features.scrappy_catalyst_strength,
        "scrappy_stale": features.scrappy_stale,
        "scrappy_conflict": features.scrappy_conflict,
        "day_2_low": str(features.day_2_low) if features.day_2_low else None,
        "strategy_id": STRATEGY_ID,
        "strategy_version": STRATEGY_VERSION,
        "holding_period_type": HOLDING_PERIOD_TYPE,
        "max_hold_days": MAX_HOLD_DAYS,
    }


def _reject(snapshot: dict, reason: str) -> SwingEvalResult:
    return SwingEvalResult(
        side=None, reason_codes=[], feature_snapshot=snapshot,
        passes_filters=False, reject_reason=reason,
    )


def evaluate(
    features: SwingFeatureSet,
    *,
    entry_start_et: str = ENTRY_START_ET,
    entry_end_et: str = ENTRY_END_ET,
) -> SwingEvalResult:
    """
    Deterministic swing entry evaluation.
    Long only in v0.1.0 — short swing carries additional overnight risk and is deferred.
    """
    snapshot = _build_snapshot(features)
    reason_codes: list[str] = []

    # --- Time window ---
    if not _et_time_in_range(features.ts, entry_start_et, entry_end_et):
        return _reject(snapshot, "outside_entry_window")

    price = features.latest_last or features.latest_ask or features.latest_bid or Decimal("0")

    # --- Price filter ---
    if price < MIN_PRICE or price > MAX_PRICE:
        return _reject(snapshot, "price_out_of_range")

    # --- Spread filter ---
    if features.spread_bps > MAX_SPREAD_BPS:
        return _reject(snapshot, "spread_too_wide")

    # --- Liquidity filter ---
    if features.avg_daily_dollar_volume is not None and features.avg_daily_dollar_volume < MIN_AVG_DAILY_DOLLAR_VOLUME:
        return _reject(snapshot, "daily_dollar_volume_below_min")

    # --- Relative volume ---
    if features.rel_volume_5m < MIN_REL_VOLUME_5M:
        return _reject(snapshot, "rel_volume_below_min")

    # --- Gap filter (avoid chasing) ---
    if features.gap_pct_from_prev_close is not None and abs(features.gap_pct_from_prev_close) > MAX_GAP_FROM_PREV_CLOSE_PCT:
        return _reject(snapshot, "gap_too_large")

    # --- Extension filter ---
    if features.extension_from_reference_pct is not None and features.extension_from_reference_pct > MAX_EXTENSION_FROM_REFERENCE_PCT:
        return _reject(snapshot, "too_extended")

    # --- Prior day data required ---
    if features.prev_close is None or features.prev_high is None or features.prev_low is None:
        return _reject(snapshot, "prior_day_data_unavailable")

    # --- Catalyst / research support required ---
    has_catalyst = False
    catalyst_reasons: list[str] = []

    if features.scrappy_catalyst_direction == "positive" and not features.scrappy_stale and not features.scrappy_conflict:
        strength = features.scrappy_catalyst_strength or 0
        if strength >= MIN_CATALYST_STRENGTH:
            has_catalyst = True
            catalyst_reasons.append("scrappy_positive")
            catalyst_reasons.append(f"catalyst_strength_{strength}")

    if features.news_side == "long" and features.news_keyword_hits:
        has_catalyst = True
        catalyst_reasons.append("news_long")

    if not has_catalyst:
        return _reject(snapshot, "catalyst_support_insufficient")

    # --- Daily structure: strong close or reclaim ---
    close = features.latest_minute_close or price
    structure_ok = False
    structure_reasons: list[str] = []

    # Check 1: Strong close — current price in top 25% of today's range
    if features.intraday_high is not None and features.intraday_low is not None:
        today_range_pos = compute_close_position_in_range_pct(close, features.intraday_high, features.intraday_low)
        if today_range_pos is not None:
            snapshot["today_close_position_pct"] = str(today_range_pos)
            threshold = 100 - STRONG_CLOSE_TOP_PCT
            if today_range_pos >= threshold:
                structure_ok = True
                structure_reasons.append("strong_close_near_highs")

    # Check 2: Reclaim of prior day high — price above prior high (within tolerance)
    if not structure_ok and features.prev_high is not None:
        reclaim_level = features.prev_high * (1 - RECLAIM_TOLERANCE_PCT / 100)
        if close >= reclaim_level:
            structure_ok = True
            structure_reasons.append("reclaim_prior_day_high")

    # Check 3: Holding above VWAP in constructive trend
    if not structure_ok and features.session_vwap is not None:
        if close > features.session_vwap and close > features.prev_close:
            structure_ok = True
            structure_reasons.append("above_vwap_above_prev_close")

    if not structure_ok:
        return _reject(snapshot, "daily_structure_not_constructive")

    # --- All filters passed: emit long signal ---
    reason_codes.extend(catalyst_reasons)
    reason_codes.extend(structure_reasons)
    reason_codes.append("swing_continuation_long")
    snapshot["signal_reason_codes"] = reason_codes

    return SwingEvalResult(
        side="buy",
        reason_codes=reason_codes,
        feature_snapshot=snapshot,
        passes_filters=True,
        reject_reason=None,
    )


def compute_stop_target(
    side: str,
    entry_price: Decimal,
    prev_low: Decimal | None,
    day_2_low: Decimal | None,
    prev_high: Decimal | None,
    r_mult: Decimal = DEFAULT_R_MULT,
) -> tuple[Decimal, Decimal]:
    """
    Swing stop/target.
    Long: stop below prior day low (or 2-day low if tighter). Target at R-multiple.
    """
    if side == "buy":
        # Stop: tighter of prior-day-low and 2-day-low
        stop_candidates = []
        if prev_low is not None:
            stop_candidates.append(prev_low * Decimal("0.995"))
        if day_2_low is not None:
            stop_candidates.append(day_2_low * Decimal("0.995"))

        if stop_candidates:
            stop = max(stop_candidates)
        else:
            stop = entry_price * (1 - DEFAULT_STOP_PCT / 100)

        r = entry_price - stop
        if r <= 0:
            r = entry_price * Decimal("0.01")
        target = entry_price + r_mult * r
        return (stop.quantize(Decimal("0.01")), target.quantize(Decimal("0.01")))
    else:
        # Short swing deferred in v0.1.0 — fallback stop/target
        stop = entry_price * (1 + DEFAULT_STOP_PCT / 100)
        if prev_high is not None:
            stop = max(stop, prev_high * Decimal("1.005"))
        r = stop - entry_price
        if r <= 0:
            r = entry_price * Decimal("0.01")
        target = entry_price - r_mult * r
        return (stop.quantize(Decimal("0.01")), target.quantize(Decimal("0.01")))


# --- Rejection reason catalog ---
REJECTION_REASONS = [
    "outside_entry_window",
    "price_out_of_range",
    "spread_too_wide",
    "daily_dollar_volume_below_min",
    "rel_volume_below_min",
    "gap_too_large",
    "too_extended",
    "prior_day_data_unavailable",
    "catalyst_support_insufficient",
    "daily_structure_not_constructive",
]

# --- Exit reasons ---
EXIT_REASONS = [
    "stop_hit",
    "target_hit",
    "max_hold_reached",
    "thesis_failure",
    "gap_and_fail",
    "manual_exit",
]
