"""
Deterministic position sizing for paper mode.
Inputs: account equity, buying power, stop distance, risk params.
Output: approved qty, notional, or rejection reason.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from stockbot.risk.limits import check_limits


@dataclass
class SizingResult:
    approved: bool
    qty: Decimal
    notional: Decimal | None
    rejection_reason: str | None


def compute_sizing(
    *,
    equity: Decimal | float,
    buying_power: Decimal | float,
    positions: list[dict[str, Any]],
    symbol: str,
    side: str,
    stop_distance_per_share: Decimal | float,
    intended_entry_price: Decimal | float,
    allow_shorts: bool,
    risk_per_trade_pct_equity: float,
    max_position_pct_equity: float,
    max_concurrent_positions: int,
    max_gross_exposure_pct_equity: float,
    max_symbol_exposure_pct_equity: float,
    atr: Decimal | float | None = None,
    avg_daily_volume: int | None = None,
    max_pct_of_adv: float = 1.0,
    quality_score_multiplier: Decimal | None = None,
    short_risk_multiplier: float = 1.0,
    max_short_gross_exposure_pct_equity: float = 15.0,
    short_max_concurrent: int = 2,
    max_overnight_exposure_pct_equity: float = 0.0,
    is_swing: bool = False,
) -> SizingResult:
    """
    Compute approved share quantity for one trade.
    - risk_dollars = equity * risk_per_trade_pct_equity / 100
    - effective_stop = max(stop_distance, 1.5 * ATR) for volatility-adjusted sizing
    - qty = floor(risk_dollars / effective_stop)
    - Cap by max_position_pct_equity, buying power, ADV, and limit checks.
    - quality_score_multiplier modulates final qty (0.5x for marginal, 1.0x for strong).
    """
    equity_d = Decimal(str(equity)) if equity is not None else Decimal("0")
    buying_power_d = Decimal(str(buying_power)) if buying_power is not None else Decimal("0")
    stop_d = Decimal(str(stop_distance_per_share)) if stop_distance_per_share is not None else Decimal("0")
    entry_d = Decimal(str(intended_entry_price)) if intended_entry_price is not None else Decimal("0")

    if equity_d <= 0:
        return SizingResult(approved=False, qty=Decimal("0"), notional=None, rejection_reason="risk_insufficient_buying_power")
    if stop_d <= 0:
        return SizingResult(approved=False, qty=Decimal("0"), notional=None, rejection_reason="risk_insufficient_stop_distance")
    if buying_power_d <= 0 and side.lower() == "buy":
        return SizingResult(approved=False, qty=Decimal("0"), notional=None, rejection_reason="risk_insufficient_buying_power")

    reject = check_limits(
        equity=equity_d,
        buying_power=buying_power_d,
        positions=positions,
        symbol=symbol,
        side=side,
        allow_shorts=allow_shorts,
        max_concurrent_positions=max_concurrent_positions,
        max_gross_exposure_pct_equity=max_gross_exposure_pct_equity,
        max_symbol_exposure_pct_equity=max_symbol_exposure_pct_equity,
        max_short_gross_exposure_pct_equity=max_short_gross_exposure_pct_equity,
        short_max_concurrent=short_max_concurrent,
        max_overnight_exposure_pct_equity=max_overnight_exposure_pct_equity,
        is_swing=is_swing,
    )
    if reject:
        return SizingResult(approved=False, qty=Decimal("0"), notional=None, rejection_reason=reject)

    # Volatility-adjusted sizing: use max(stop, 1.5*ATR) as effective risk
    effective_stop = stop_d
    if atr is not None:
        atr_d = Decimal(str(atr))
        if atr_d > 0:
            atr_floor = atr_d * Decimal("1.5")
            effective_stop = max(stop_d, atr_floor)

    risk_pct = Decimal(str(risk_per_trade_pct_equity / 100.0))
    if side.lower() == "sell":
        risk_pct = risk_pct * Decimal(str(short_risk_multiplier))
    risk_dollars = equity_d * risk_pct

    qty_by_risk = risk_dollars / effective_stop
    qty_cap_by_equity = (equity_d * Decimal(str(max_position_pct_equity / 100.0))) / entry_d if entry_d > 0 else Decimal("0")
    qty_cap_bp = buying_power_d / entry_d if entry_d > 0 and side.lower() == "buy" else qty_by_risk
    if side.lower() == "sell" and allow_shorts:
        qty_cap_bp = buying_power_d / entry_d if entry_d > 0 else qty_by_risk

    caps = [qty_by_risk, qty_cap_by_equity]
    if side.lower() == "buy" or (side.lower() == "sell" and allow_shorts):
        caps.append(qty_cap_bp)

    # Liquidity cap: max % of average daily volume
    if avg_daily_volume and avg_daily_volume > 0 and max_pct_of_adv > 0:
        qty_cap_adv = Decimal(str(int(avg_daily_volume * max_pct_of_adv / 100.0)))
        if qty_cap_adv > 0:
            caps.append(qty_cap_adv)

    qty = min(caps)

    # Quality score modulation
    if quality_score_multiplier is not None and quality_score_multiplier > 0:
        qty = qty * quality_score_multiplier

    qty = qty.to_integral_value(rounding="ROUND_FLOOR")
    if qty <= 0:
        return SizingResult(approved=False, qty=Decimal("0"), notional=None, rejection_reason="risk_insufficient_stop_distance")

    notional = qty * entry_d
    return SizingResult(approved=True, qty=qty, notional=notional, rejection_reason=None)
