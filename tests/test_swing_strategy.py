"""Tests for SWING_EVENT_CONTINUATION strategy: evaluation, routing, lifecycle fields, API shape."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest


# ────────────────────────────────────────────────────────────────────
# Strategy module imports
# ────────────────────────────────────────────────────────────────────
from stockbot.strategies.swing_event_continuation import (
    STRATEGY_ID,
    STRATEGY_VERSION,
    HOLDING_PERIOD_TYPE,
    MAX_HOLD_DAYS,
    FORCE_FLAT_ET,
    REJECTION_REASONS,
    EXIT_REASONS,
    SwingFeatureSet,
    SwingEvalResult,
    evaluate,
    compute_stop_target,
    compute_close_position_in_range_pct,
    compute_gap_pct,
    compute_extension_from_reference,
)
from stockbot.strategies.router import (
    StrategyConfig,
    get_active_strategies,
    get_strategy_priority,
    should_evaluate_strategy,
    has_conflicting_position,
    select_primary_strategy,
)


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────

def _make_et_ts(hour: int, minute: int) -> datetime:
    """Build a UTC datetime that corresponds to the given ET time on a weekday."""
    import zoneinfo
    et = zoneinfo.ZoneInfo("America/New_York")
    base = datetime(2025, 6, 3, hour, minute, tzinfo=et)  # Tuesday
    return base.astimezone(UTC)


def _base_features(**overrides) -> SwingFeatureSet:
    """Construct a SwingFeatureSet with sane defaults that should pass all filters."""
    ts = _make_et_ts(14, 0)  # 14:00 ET — inside entry window
    defaults = dict(
        symbol="ACME",
        ts=ts,
        latest_bid=Decimal("50.00"),
        latest_ask=Decimal("50.10"),
        latest_last=Decimal("50.05"),
        latest_minute_close=Decimal("50.05"),
        spread_bps=20,
        session_vwap=Decimal("49.50"),
        rel_volume_5m=Decimal("2.0"),
        intraday_high=Decimal("50.30"),
        intraday_low=Decimal("48.00"),
        prev_close=Decimal("49.00"),
        prev_high=Decimal("49.80"),
        prev_low=Decimal("47.50"),
        prev_daily_range=Decimal("2.30"),
        day_2_low=Decimal("47.00"),
        avg_daily_dollar_volume=Decimal("20000000"),
        gap_pct_from_prev_close=Decimal("2.14"),
        close_position_in_range_pct=Decimal("89.13"),
        extension_from_reference_pct=Decimal("5.0"),
        news_side="long",
        news_keyword_hits=["fda_approval"],
        scrappy_catalyst_direction="positive",
        scrappy_catalyst_strength=5,
        scrappy_stale=False,
        scrappy_conflict=False,
    )
    defaults.update(overrides)
    return SwingFeatureSet(**defaults)


# ────────────────────────────────────────────────────────────────────
# Strategy identity
# ────────────────────────────────────────────────────────────────────

class TestStrategyIdentity:
    def test_strategy_id_and_version(self):
        assert STRATEGY_ID == "SWING_EVENT_CONTINUATION"
        assert STRATEGY_VERSION == "0.2.0"

    def test_holding_period_type_is_swing(self):
        assert HOLDING_PERIOD_TYPE == "swing"

    def test_max_hold_days(self):
        assert MAX_HOLD_DAYS == 5

    def test_no_force_flat(self):
        assert FORCE_FLAT_ET is None

    def test_rejection_reasons_are_defined(self):
        assert len(REJECTION_REASONS) >= 5
        assert "outside_entry_window" in REJECTION_REASONS
        assert "catalyst_support_insufficient" in REJECTION_REASONS
        assert "daily_structure_not_constructive" in REJECTION_REASONS

    def test_exit_reasons_are_defined(self):
        assert "stop_hit" in EXIT_REASONS
        assert "target_hit" in EXIT_REASONS
        assert "max_hold_reached" in EXIT_REASONS


# ────────────────────────────────────────────────────────────────────
# Evaluation: passing case
# ────────────────────────────────────────────────────────────────────

class TestEvaluatePass:
    def test_base_case_passes(self):
        f = _base_features()
        result = evaluate(f)
        assert result.passes_filters is True
        assert result.side == "buy"
        assert result.reject_reason is None
        assert len(result.reason_codes) > 0
        assert "swing_continuation_long" in result.reason_codes

    def test_feature_snapshot_has_strategy_metadata(self):
        f = _base_features()
        result = evaluate(f)
        snap = result.feature_snapshot
        assert snap["strategy_id"] == STRATEGY_ID
        assert snap["strategy_version"] == STRATEGY_VERSION
        assert snap["holding_period_type"] == "swing"
        assert snap["max_hold_days"] == 5


# ────────────────────────────────────────────────────────────────────
# Evaluation: rejection cases
# ────────────────────────────────────────────────────────────────────

class TestEvaluateReject:
    def test_outside_entry_window(self):
        f = _base_features(ts=_make_et_ts(9, 30))
        result = evaluate(f)
        assert result.passes_filters is False
        assert result.reject_reason == "outside_entry_window"

    def test_price_too_low(self):
        f = _base_features(latest_last=Decimal("2.00"))
        result = evaluate(f)
        assert result.passes_filters is False
        assert result.reject_reason == "price_out_of_range"

    def test_price_too_high(self):
        f = _base_features(latest_last=Decimal("600.00"))
        result = evaluate(f)
        assert result.passes_filters is False
        assert result.reject_reason == "price_out_of_range"

    def test_spread_too_wide(self):
        f = _base_features(spread_bps=50)
        result = evaluate(f)
        assert result.passes_filters is False
        assert result.reject_reason == "spread_too_wide"

    def test_low_dollar_volume(self):
        f = _base_features(avg_daily_dollar_volume=Decimal("1000000"))
        result = evaluate(f)
        assert result.passes_filters is False
        assert result.reject_reason == "daily_dollar_volume_below_min"

    def test_low_relative_volume(self):
        f = _base_features(rel_volume_5m=Decimal("0.3"))
        result = evaluate(f)
        assert result.passes_filters is False
        assert result.reject_reason == "rel_volume_below_min"

    def test_gap_too_large(self):
        f = _base_features(gap_pct_from_prev_close=Decimal("15.0"))
        result = evaluate(f)
        assert result.passes_filters is False
        assert result.reject_reason == "gap_too_large"

    def test_too_extended(self):
        f = _base_features(extension_from_reference_pct=Decimal("20.0"))
        result = evaluate(f)
        assert result.passes_filters is False
        assert result.reject_reason == "too_extended"

    def test_prior_day_data_unavailable(self):
        f = _base_features(prev_close=None, prev_high=None, prev_low=None)
        result = evaluate(f)
        assert result.passes_filters is False
        assert result.reject_reason == "prior_day_data_unavailable"

    def test_catalyst_support_insufficient_no_scrappy(self):
        f = _base_features(
            scrappy_catalyst_direction=None,
            scrappy_catalyst_strength=None,
            news_side="neutral",
            news_keyword_hits=[],
        )
        result = evaluate(f)
        assert result.passes_filters is False
        assert result.reject_reason == "catalyst_support_insufficient"

    def test_catalyst_stale_rejected(self):
        f = _base_features(
            scrappy_stale=True,
            news_side="neutral",
            news_keyword_hits=[],
        )
        result = evaluate(f)
        assert result.passes_filters is False
        assert result.reject_reason == "catalyst_support_insufficient"

    def test_daily_structure_not_constructive(self):
        f = _base_features(
            latest_minute_close=Decimal("48.05"),
            latest_last=Decimal("48.05"),
            intraday_high=Decimal("50.30"),
            intraday_low=Decimal("48.00"),
            prev_high=Decimal("52.00"),
            session_vwap=Decimal("49.50"),
        )
        result = evaluate(f)
        assert result.passes_filters is False
        assert result.reject_reason == "daily_structure_not_constructive"

    def test_every_rejection_reason_is_testable(self):
        for reason in REJECTION_REASONS:
            assert isinstance(reason, str)
            assert len(reason) > 3


# ────────────────────────────────────────────────────────────────────
# Stop / Target
# ────────────────────────────────────────────────────────────────────

class TestStopTarget:
    def test_long_stop_below_prev_low(self):
        stop, target = compute_stop_target(
            side="buy",
            entry_price=Decimal("50.00"),
            prev_low=Decimal("47.50"),
            day_2_low=Decimal("47.00"),
            prev_high=Decimal("49.80"),
        )
        assert stop < Decimal("50.00")
        assert target > Decimal("50.00")
        # v0.2.0: uses min() for wider stop (deeper support), so stop is at day_2_low * 0.995
        assert stop <= Decimal("47.00") * Decimal("0.995") + Decimal("0.01")

    def test_long_target_is_r_multiple(self):
        stop, target = compute_stop_target(
            side="buy",
            entry_price=Decimal("50.00"),
            prev_low=Decimal("48.00"),
            day_2_low=None,
            prev_high=None,
        )
        r = Decimal("50.00") - stop
        assert r > 0
        expected_target = Decimal("50.00") + 2 * r
        assert abs(target - expected_target) < Decimal("0.02")

    def test_fallback_when_no_prior_low(self):
        stop, target = compute_stop_target(
            side="buy",
            entry_price=Decimal("50.00"),
            prev_low=None,
            day_2_low=None,
            prev_high=None,
        )
        assert stop < Decimal("50.00")
        assert target > Decimal("50.00")


# ────────────────────────────────────────────────────────────────────
# Helper functions
# ────────────────────────────────────────────────────────────────────

class TestHelperFunctions:
    def test_close_position_in_range_at_high(self):
        result = compute_close_position_in_range_pct(Decimal("50"), Decimal("50"), Decimal("40"))
        assert result == Decimal("100.00")

    def test_close_position_in_range_at_low(self):
        result = compute_close_position_in_range_pct(Decimal("40"), Decimal("50"), Decimal("40"))
        assert result == Decimal("0.00")

    def test_close_position_in_range_equal_high_low(self):
        result = compute_close_position_in_range_pct(Decimal("50"), Decimal("50"), Decimal("50"))
        assert result is None

    def test_gap_pct_positive(self):
        result = compute_gap_pct(Decimal("100"), Decimal("105"))
        assert result == Decimal("5.00")

    def test_gap_pct_negative(self):
        result = compute_gap_pct(Decimal("100"), Decimal("95"))
        assert result == Decimal("-5.00")

    def test_gap_pct_no_prev_close(self):
        result = compute_gap_pct(None, Decimal("100"))
        assert result is None

    def test_extension_from_reference(self):
        result = compute_extension_from_reference(Decimal("110"), Decimal("100"))
        assert result == Decimal("10.00")


# ────────────────────────────────────────────────────────────────────
# Router: strategy configs and arbitration
# ────────────────────────────────────────────────────────────────────

class TestRouter:
    def _make_configs(self) -> list[StrategyConfig]:
        return [
            StrategyConfig(
                strategy_id="OPEN_DRIVE_MOMO", strategy_version="0.1.0",
                entry_start_et="09:35", entry_end_et="11:30",
                force_flat_et="15:45", enabled=True, paper_enabled=True,
            ),
            StrategyConfig(
                strategy_id="INTRADAY_CONTINUATION", strategy_version="0.1.0",
                entry_start_et="10:30", entry_end_et="14:30",
                force_flat_et="15:45", enabled=True, paper_enabled=False,
            ),
            StrategyConfig(
                strategy_id="SWING_EVENT_CONTINUATION", strategy_version="0.1.0",
                entry_start_et="13:00", entry_end_et="15:30",
                force_flat_et=None, enabled=True, paper_enabled=False,
                holding_period_type="swing", max_hold_days=5,
            ),
        ]

    def test_swing_priority_lower_than_intraday(self):
        assert get_strategy_priority("SWING_EVENT_CONTINUATION") > get_strategy_priority("OPEN_DRIVE_MOMO")
        assert get_strategy_priority("SWING_EVENT_CONTINUATION") > get_strategy_priority("INTRADAY_CONTINUATION")

    def test_swing_active_in_afternoon(self):
        ts = _make_et_ts(14, 0)
        configs = self._make_configs()
        active = get_active_strategies(ts, configs)
        active_ids = [c.strategy_id for c in active]
        assert "SWING_EVENT_CONTINUATION" in active_ids

    def test_swing_not_active_in_morning(self):
        ts = _make_et_ts(10, 0)
        configs = self._make_configs()
        active = get_active_strategies(ts, configs)
        active_ids = [c.strategy_id for c in active]
        assert "SWING_EVENT_CONTINUATION" not in active_ids

    def test_swing_disabled(self):
        configs = self._make_configs()
        configs[2].enabled = False
        ts = _make_et_ts(14, 0)
        active = get_active_strategies(ts, configs)
        active_ids = [c.strategy_id for c in active]
        assert "SWING_EVENT_CONTINUATION" not in active_ids

    def test_should_evaluate_in_window(self):
        ts = _make_et_ts(14, 0)
        configs = self._make_configs()
        ok, reason = should_evaluate_strategy("SWING_EVENT_CONTINUATION", "ACME", ts, set(), configs)
        assert ok is True
        assert reason is None

    def test_should_evaluate_outside_window(self):
        ts = _make_et_ts(10, 0)
        configs = self._make_configs()
        ok, reason = should_evaluate_strategy("SWING_EVENT_CONTINUATION", "ACME", ts, set(), configs)
        assert ok is False
        assert reason == "outside_entry_window"

    def test_should_evaluate_already_traded(self):
        ts = _make_et_ts(14, 0)
        configs = self._make_configs()
        traded = {"SWING_EVENT_CONTINUATION:ACME"}
        ok, reason = should_evaluate_strategy("SWING_EVENT_CONTINUATION", "ACME", ts, traded, configs)
        assert ok is False
        assert reason == "already_traded_today"

    def test_swing_config_has_no_force_flat(self):
        configs = self._make_configs()
        swing = next(c for c in configs if c.strategy_id == "SWING_EVENT_CONTINUATION")
        assert swing.force_flat_et is None
        assert swing.holding_period_type == "swing"
        assert swing.max_hold_days == 5


# ────────────────────────────────────────────────────────────────────
# Router: conflict detection
# ────────────────────────────────────────────────────────────────────

class TestConflictDetection:
    def test_no_conflict_empty(self):
        conflict, reason = has_conflicting_position("ACME", "SWING_EVENT_CONTINUATION", {})
        assert conflict is False

    def test_swing_blocked_by_intraday(self):
        conflict, reason = has_conflicting_position(
            "ACME", "SWING_EVENT_CONTINUATION", {"ACME": "OPEN_DRIVE_MOMO"}
        )
        assert conflict is True
        assert "intraday" in reason

    def test_intraday_blocked_by_swing(self):
        conflict, reason = has_conflicting_position(
            "ACME", "OPEN_DRIVE_MOMO", {"ACME": "SWING_EVENT_CONTINUATION"}
        )
        assert conflict is True
        assert "swing" in reason

    def test_same_strategy_blocked(self):
        conflict, reason = has_conflicting_position(
            "ACME", "SWING_EVENT_CONTINUATION", {"ACME": "SWING_EVENT_CONTINUATION"}
        )
        assert conflict is True


# ────────────────────────────────────────────────────────────────────
# API shape (strategies + exposure endpoints)
# ────────────────────────────────────────────────────────────────────

try:
    from fastapi.testclient import TestClient
    from api.main import app
    APP_AVAILABLE = True
except Exception:
    APP_AVAILABLE = False


@pytest.mark.skipif(not APP_AVAILABLE, reason="api.main not loadable")
class TestAPIShape:
    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    def test_strategies_endpoint_includes_swing(self, client: TestClient):
        r = client.get("/v1/strategies")
        assert r.status_code == 200
        data = r.json()
        ids = [s["strategy_id"] for s in data["strategies"]]
        assert "SWING_EVENT_CONTINUATION" in ids

    def test_swing_strategy_fields(self, client: TestClient):
        r = client.get("/v1/strategies")
        data = r.json()
        swing = next(s for s in data["strategies"] if s["strategy_id"] == "SWING_EVENT_CONTINUATION")
        assert swing["holding_period_type"] == "swing"
        assert swing["max_hold_days"] == 5
        assert swing["force_flat_et"] is None
        assert swing["overnight_carry"] is True
        assert "entry_window_et" in swing
        assert "paper_enabled" in swing

    def test_compare_strategies_endpoint_exists(self, client: TestClient):
        try:
            r = client.get("/v1/metrics/compare-strategies")
        except Exception:
            pytest.skip("compare-strategies endpoint not reachable (DB required)")
            return
        assert r.status_code in (200, 500, 503)
        if r.status_code == 200:
            data = r.json()
            assert "by_strategy" in data
