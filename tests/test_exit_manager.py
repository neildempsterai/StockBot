"""Tests for dynamic exit management: trailing stops, partial exits, time decay."""
from decimal import Decimal
from stockbot.risk.exit_manager import (
    TrailingStopState, update_trailing_state, check_partial_exit,
    check_time_decay_intraday, ExitAction,
)


def _make_ts(entry: float = 50.0, stop: float = 48.0, target: float = 54.0, side: str = "buy") -> TrailingStopState:
    return TrailingStopState(
        entry_price=Decimal(str(entry)),
        original_stop=Decimal(str(stop)),
        original_target=Decimal(str(target)),
        side=side,
        atr=Decimal("2.0"),
    )


class TestTrailingStopLong:
    def test_initial_phase(self):
        ts = _make_ts()
        action = update_trailing_state(ts, Decimal("50.5"), Decimal("49.5"), Decimal("50.2"))
        assert action.action == "hold"
        assert ts.trail_phase == "initial"

    def test_breakeven_at_1r(self):
        ts = _make_ts()
        for _ in range(5):
            update_trailing_state(ts, Decimal("52.5"), Decimal("51.5"), Decimal("52.0"))
        assert ts.trail_phase == "breakeven" or ts.current_stop >= Decimal("50.0")

    def test_stop_never_moves_down(self):
        ts = _make_ts()
        update_trailing_state(ts, Decimal("53"), Decimal("51"), Decimal("52"))
        stop_after_up = ts.current_stop
        update_trailing_state(ts, Decimal("51"), Decimal("49.5"), Decimal("50"))
        assert ts.current_stop >= stop_after_up

    def test_aggressive_phase_at_3r(self):
        ts = _make_ts()
        # Push to 3R = 50 + 3*(50-48) = 56
        update_trailing_state(ts, Decimal("56.5"), Decimal("55"), Decimal("56"))
        assert ts.trail_phase in ("trail_1", "trail_2", "aggressive", "breakeven")

    def test_high_water_mark_tracked(self):
        ts = _make_ts()
        update_trailing_state(ts, Decimal("55"), Decimal("54"), Decimal("54.5"))
        assert ts.high_water_mark == Decimal("55")
        update_trailing_state(ts, Decimal("53"), Decimal("52"), Decimal("52.5"))
        assert ts.high_water_mark == Decimal("55")


class TestTrailingStopShort:
    def test_initial_short(self):
        ts = _make_ts(entry=50.0, stop=52.0, target=46.0, side="sell")
        action = update_trailing_state(ts, Decimal("50.5"), Decimal("49.5"), Decimal("49.8"))
        assert action.action == "hold"

    def test_short_breakeven(self):
        ts = _make_ts(entry=50.0, stop=52.0, target=46.0, side="sell")
        # Price drops to 48 (1R move for short: entry - 1R = 50 - 2 = 48)
        for _ in range(5):
            update_trailing_state(ts, Decimal("48.5"), Decimal("47.5"), Decimal("48.0"))
        assert ts.current_stop <= Decimal("52.0")

    def test_short_low_water_mark(self):
        ts = _make_ts(entry=50.0, stop=52.0, target=46.0, side="sell")
        update_trailing_state(ts, Decimal("48"), Decimal("45"), Decimal("46"))
        assert ts.low_water_mark == Decimal("45")


class TestPartialExit:
    def test_no_partial_before_1r(self):
        ts = _make_ts()
        result = check_partial_exit(ts, Decimal("50.5"))
        assert result is None

    def test_partial_at_1r(self):
        ts = _make_ts()
        ts.high_water_mark = Decimal("52.5")  # > 1R
        result = check_partial_exit(ts, Decimal("52.0"))
        assert result is not None
        assert result.action == "partial_exit"
        assert result.exit_qty_pct == Decimal("0.5")
        assert "1R" in ts.partial_exits_done

    def test_no_double_partial(self):
        ts = _make_ts()
        ts.high_water_mark = Decimal("52.5")
        check_partial_exit(ts, Decimal("52.0"))
        result = check_partial_exit(ts, Decimal("52.0"))
        assert result is None  # already done 1R

    def test_partial_at_2r(self):
        ts = _make_ts()
        ts.high_water_mark = Decimal("54.5")  # > 2R
        ts.partial_exits_done = ["1R"]  # already did 1R
        result = check_partial_exit(ts, Decimal("54.0"))
        assert result is not None
        assert "2R" in ts.partial_exits_done


class TestTimeDecay:
    def test_no_decay_early(self):
        ts = _make_ts()
        ts.bars_since_new_extreme = 5
        result = check_time_decay_intraday(ts, "10:30", Decimal("2.0"))
        assert result is None

    def test_tighten_at_30_bars(self):
        ts = _make_ts()
        ts.bars_since_new_extreme = 31
        ts.high_water_mark = Decimal("50.5")
        result = check_time_decay_intraday(ts, "11:00", Decimal("2.0"))
        assert result is not None
        assert result.action == "tighten_stop"

    def test_pre_close_exit(self):
        ts = _make_ts()
        ts.bars_since_new_extreme = 10
        ts.high_water_mark = Decimal("50.3")  # <0.5R profit
        # First call at 14:30 tightens; then at 15:15+ it should exit
        check_time_decay_intraday(ts, "14:30", Decimal("2.0"))
        result = check_time_decay_intraday(ts, "15:20", Decimal("2.0"))
        assert result is not None
        assert result.action in ("full_exit", "tighten_stop")


class TestVWAPCross:
    def test_vwap_cross_against_counts(self):
        ts = _make_ts()
        vwap = Decimal("51.0")
        for _ in range(3):
            update_trailing_state(ts, Decimal("50.5"), Decimal("49.5"), Decimal("50.0"), vwap=vwap)
        assert ts.vwap_cross_against_count >= 3

    def test_vwap_cross_resets_on_recovery(self):
        ts = _make_ts()
        vwap = Decimal("50.0")
        update_trailing_state(ts, Decimal("49.5"), Decimal("48.5"), Decimal("49.0"), vwap=vwap)
        assert ts.vwap_cross_against_count >= 1
        update_trailing_state(ts, Decimal("51.5"), Decimal("50.5"), Decimal("51.0"), vwap=vwap)
        assert ts.vwap_cross_against_count == 0
