"""
Dynamic exit management: trailing stops, partial profit taking,
time-based tightening, VWAP-relative management, regime-aware exits.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ExitAction:
    """Result of exit manager evaluation."""
    action: str  # "hold" | "update_stop" | "partial_exit" | "full_exit" | "tighten_stop"
    new_stop: Decimal | None = None
    new_target: Decimal | None = None
    exit_qty_pct: Decimal | None = None  # fraction of position to exit (0.25, 0.5, etc.)
    reason: str = ""
    trail_phase: str = ""  # initial | breakeven | trail_1 | trail_2 | aggressive


class TrailingStopState:
    """Per-position trailing stop state."""

    def __init__(
        self,
        entry_price: Decimal,
        original_stop: Decimal,
        original_target: Decimal,
        side: str,
        atr: Decimal | None = None,
    ) -> None:
        self.entry_price = entry_price
        self.original_stop = original_stop
        self.original_target = original_target
        self.current_stop = original_stop
        self.side = side
        self.atr = atr or abs(entry_price - original_stop)

        self.high_water_mark = entry_price
        self.low_water_mark = entry_price
        self.trail_phase = "initial"
        self.bars_since_entry = 0
        self.bars_since_new_extreme = 0
        self.partial_exits_done: list[str] = []
        self.total_qty_exited_pct = Decimal("0")
        self.vwap_cross_against_count = 0

    @property
    def risk_per_share(self) -> Decimal:
        return abs(self.entry_price - self.original_stop)

    @property
    def current_r_multiple(self) -> Decimal:
        r = self.risk_per_share
        if r == 0:
            return Decimal("0")
        if self.side == "buy":
            return (self.high_water_mark - self.entry_price) / r
        return (self.entry_price - self.low_water_mark) / r

    @property
    def unrealized_r(self) -> Decimal:
        """Current unrealized R based on last price vs entry."""
        r = self.risk_per_share
        if r == 0:
            return Decimal("0")
        if self.side == "buy":
            return (self.high_water_mark - self.entry_price) / r
        return (self.entry_price - self.low_water_mark) / r


def update_trailing_state(
    state: TrailingStopState,
    bar_high: Decimal,
    bar_low: Decimal,
    bar_close: Decimal,
    vwap: Decimal | None = None,
    regime_multiplier: Decimal = Decimal("1.0"),
) -> ExitAction:
    """Update trailing stop state with new bar data. Returns exit action.

    Trail progression (longs):
      initial -> breakeven (at 1R) -> trail_1 (at 1.5R, trail 1.5 ATR)
      -> trail_2 (at 2R, trail 1.0 ATR) -> aggressive (at 3R+, trail 0.75 ATR)
    """
    state.bars_since_entry += 1

    if state.side == "buy":
        if bar_high > state.high_water_mark:
            state.high_water_mark = bar_high
            state.bars_since_new_extreme = 0
        else:
            state.bars_since_new_extreme += 1
    else:
        if bar_low < state.low_water_mark:
            state.low_water_mark = bar_low
            state.bars_since_new_extreme = 0
        else:
            state.bars_since_new_extreme += 1

    r = state.risk_per_share
    if r <= 0:
        return ExitAction(action="hold", trail_phase=state.trail_phase)

    current_r = state.current_r_multiple
    atr = state.atr
    adj_atr = atr * regime_multiplier

    new_stop = state.current_stop
    new_phase = state.trail_phase
    reason = ""

    if state.side == "buy":
        if current_r >= Decimal("3") and state.trail_phase != "aggressive":
            new_phase = "aggressive"
            trail_distance = adj_atr * Decimal("0.75")
            candidate = (state.high_water_mark - trail_distance).quantize(Decimal("0.01"))
            if candidate > new_stop:
                new_stop = candidate
                reason = "aggressive_trail_3R"
        elif current_r >= Decimal("2") and state.trail_phase not in ("aggressive", "trail_2"):
            new_phase = "trail_2"
            trail_distance = adj_atr * Decimal("1.0")
            candidate = (state.high_water_mark - trail_distance).quantize(Decimal("0.01"))
            if candidate > new_stop:
                new_stop = candidate
                reason = "trail_2_at_2R"
        elif current_r >= Decimal("1.5") and state.trail_phase not in ("aggressive", "trail_2", "trail_1"):
            new_phase = "trail_1"
            trail_distance = adj_atr * Decimal("1.5")
            candidate = (state.high_water_mark - trail_distance).quantize(Decimal("0.01"))
            if candidate > new_stop:
                new_stop = candidate
                reason = "trail_1_at_1_5R"
        elif current_r >= Decimal("1") and state.trail_phase == "initial":
            new_phase = "breakeven"
            candidate = state.entry_price
            if candidate > new_stop:
                new_stop = candidate
                reason = "breakeven_at_1R"

        if state.trail_phase in ("trail_1", "trail_2", "aggressive"):
            phase_atr_mult = {"trail_1": Decimal("1.5"), "trail_2": Decimal("1.0"), "aggressive": Decimal("0.75")}
            trail_dist = adj_atr * phase_atr_mult.get(state.trail_phase, Decimal("1.5"))
            candidate = (state.high_water_mark - trail_dist).quantize(Decimal("0.01"))
            if candidate > new_stop:
                new_stop = candidate
                reason = f"trail_update_{state.trail_phase}"

    else:  # short
        if current_r >= Decimal("3") and state.trail_phase != "aggressive":
            new_phase = "aggressive"
            trail_distance = adj_atr * Decimal("0.75")
            candidate = (state.low_water_mark + trail_distance).quantize(Decimal("0.01"))
            if candidate < new_stop:
                new_stop = candidate
                reason = "aggressive_trail_3R"
        elif current_r >= Decimal("2") and state.trail_phase not in ("aggressive", "trail_2"):
            new_phase = "trail_2"
            trail_distance = adj_atr * Decimal("1.0")
            candidate = (state.low_water_mark + trail_distance).quantize(Decimal("0.01"))
            if candidate < new_stop:
                new_stop = candidate
                reason = "trail_2_at_2R"
        elif current_r >= Decimal("1.5") and state.trail_phase not in ("aggressive", "trail_2", "trail_1"):
            new_phase = "trail_1"
            trail_distance = adj_atr * Decimal("1.5")
            candidate = (state.low_water_mark + trail_distance).quantize(Decimal("0.01"))
            if candidate < new_stop:
                new_stop = candidate
                reason = "trail_1_at_1_5R"
        elif current_r >= Decimal("1") and state.trail_phase == "initial":
            new_phase = "breakeven"
            candidate = state.entry_price
            if candidate < new_stop:
                new_stop = candidate
                reason = "breakeven_at_1R"

        if state.trail_phase in ("trail_1", "trail_2", "aggressive"):
            phase_atr_mult = {"trail_1": Decimal("1.5"), "trail_2": Decimal("1.0"), "aggressive": Decimal("0.75")}
            trail_dist = adj_atr * phase_atr_mult.get(state.trail_phase, Decimal("1.5"))
            candidate = (state.low_water_mark + trail_dist).quantize(Decimal("0.01"))
            if candidate < new_stop:
                new_stop = candidate
                reason = f"trail_update_{state.trail_phase}"

    # VWAP cross against
    if vwap is not None:
        if state.side == "buy" and bar_close < vwap:
            state.vwap_cross_against_count += 1
        elif state.side == "sell" and bar_close > vwap:
            state.vwap_cross_against_count += 1
        else:
            state.vwap_cross_against_count = 0

        if state.vwap_cross_against_count >= 3:
            if state.side == "buy":
                vwap_stop = (vwap - adj_atr * Decimal("0.25")).quantize(Decimal("0.01"))
                if vwap_stop > new_stop:
                    new_stop = vwap_stop
                    reason = "vwap_cross_against_tighten"
            else:
                vwap_stop = (vwap + adj_atr * Decimal("0.25")).quantize(Decimal("0.01"))
                if vwap_stop < new_stop:
                    new_stop = vwap_stop
                    reason = "vwap_cross_against_tighten"

    state.trail_phase = new_phase
    if new_stop != state.current_stop:
        state.current_stop = new_stop
        return ExitAction(
            action="update_stop", new_stop=new_stop, reason=reason,
            trail_phase=new_phase,
        )

    return ExitAction(action="hold", trail_phase=state.trail_phase)


def check_partial_exit(
    state: TrailingStopState,
    current_price: Decimal,
    partial_at_1r_pct: int = 50,
    partial_at_2r_pct: int = 25,
) -> ExitAction | None:
    """Check if a partial exit should be triggered.

    Returns ExitAction with exit_qty_pct if partial exit needed, None otherwise.
    """
    r = state.risk_per_share
    if r <= 0:
        return None
    current_r = state.current_r_multiple

    if current_r >= Decimal("1") and "1R" not in state.partial_exits_done:
        state.partial_exits_done.append("1R")
        pct = Decimal(str(partial_at_1r_pct)) / 100
        state.total_qty_exited_pct += pct
        return ExitAction(
            action="partial_exit",
            exit_qty_pct=pct,
            reason="partial_profit_1R",
            trail_phase=state.trail_phase,
        )

    if current_r >= Decimal("2") and "2R" not in state.partial_exits_done:
        state.partial_exits_done.append("2R")
        pct = Decimal(str(partial_at_2r_pct)) / 100
        state.total_qty_exited_pct += pct
        return ExitAction(
            action="partial_exit",
            exit_qty_pct=pct,
            reason="partial_profit_2R",
            trail_phase=state.trail_phase,
        )

    return None


def check_time_decay_intraday(
    state: TrailingStopState,
    current_et_time: str,
    adj_atr: Decimal,
) -> ExitAction | None:
    """Time-based stop tightening for intraday positions.

    30 bars without new high -> tighten to 0.75 ATR
    60 bars without progress + < 0.5R -> breakeven
    After 14:30 -> tighten to 0.5 ATR
    After 15:15 -> exit if < 0.5R profit
    """
    if state.bars_since_new_extreme >= 30 and state.current_r_multiple < Decimal("1"):
        if state.side == "buy":
            candidate = (state.high_water_mark - adj_atr * Decimal("0.75")).quantize(Decimal("0.01"))
            if candidate > state.current_stop:
                state.current_stop = candidate
                return ExitAction(
                    action="tighten_stop", new_stop=candidate,
                    reason="time_decay_30bars_no_new_high", trail_phase=state.trail_phase,
                )
        else:
            candidate = (state.low_water_mark + adj_atr * Decimal("0.75")).quantize(Decimal("0.01"))
            if candidate < state.current_stop:
                state.current_stop = candidate
                return ExitAction(
                    action="tighten_stop", new_stop=candidate,
                    reason="time_decay_30bars_no_new_low", trail_phase=state.trail_phase,
                )

    if state.bars_since_new_extreme >= 60 and state.current_r_multiple < Decimal("0.5"):
        if state.side == "buy" and state.entry_price > state.current_stop:
            state.current_stop = state.entry_price
            return ExitAction(
                action="tighten_stop", new_stop=state.entry_price,
                reason="time_decay_60bars_move_to_breakeven", trail_phase=state.trail_phase,
            )
        elif state.side == "sell" and state.entry_price < state.current_stop:
            state.current_stop = state.entry_price
            return ExitAction(
                action="tighten_stop", new_stop=state.entry_price,
                reason="time_decay_60bars_move_to_breakeven", trail_phase=state.trail_phase,
            )

    if current_et_time >= "14:30":
        if state.side == "buy":
            candidate = (state.high_water_mark - adj_atr * Decimal("0.5")).quantize(Decimal("0.01"))
            if candidate > state.current_stop:
                state.current_stop = candidate
                return ExitAction(
                    action="tighten_stop", new_stop=candidate,
                    reason="afternoon_tighten_after_1430", trail_phase=state.trail_phase,
                )
        else:
            candidate = (state.low_water_mark + adj_atr * Decimal("0.5")).quantize(Decimal("0.01"))
            if candidate < state.current_stop:
                state.current_stop = candidate
                return ExitAction(
                    action="tighten_stop", new_stop=candidate,
                    reason="afternoon_tighten_after_1430", trail_phase=state.trail_phase,
                )

    if current_et_time >= "15:15" and state.current_r_multiple < Decimal("0.5"):
        return ExitAction(
            action="full_exit", reason="pre_close_exit_low_profit",
            trail_phase=state.trail_phase,
        )

    return None
