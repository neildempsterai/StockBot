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
) -> SizingResult:
    """
    Compute approved share quantity for one trade.
    - risk_dollars = equity * risk_per_trade_pct_equity / 100
    - qty = floor(risk_dollars / stop_distance_per_share)
    - Cap by max_position_pct_equity, buying power, and limit checks.
    """
    equity_d = Decimal(str(equity)) if equity is not None else Decimal("0")
    buying_power_d = Decimal(str(buying_power)) if buying_power is not None else Decimal("0")
    stop_d = Decimal(str(stop_distance_per_share)) if stop_distance_per_share is not None else Decimal("0")
    entry_d = Decimal(str(intended_entry_price)) if intended_entry_price is not None else Decimal("0")

    if equity_d <= 0:
        return SizingResult(
            approved=False,
            qty=Decimal("0"),
            notional=None,
            rejection_reason="risk_insufficient_buying_power",
        )
    if stop_d <= 0:
        return SizingResult(
            approved=False,
            qty=Decimal("0"),
            notional=None,
            rejection_reason="risk_insufficient_stop_distance",
        )
    if buying_power_d <= 0 and side.lower() == "buy":
        return SizingResult(
            approved=False,
            qty=Decimal("0"),
            notional=None,
            rejection_reason="risk_insufficient_buying_power",
        )

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
    )
    if reject:
        return SizingResult(approved=False, qty=Decimal("0"), notional=None, rejection_reason=reject)

    risk_dollars = equity_d * Decimal(str(risk_per_trade_pct_equity / 100.0))
    qty_by_risk = risk_dollars / stop_d
    qty_cap_by_equity = (equity_d * Decimal(str(max_position_pct_equity / 100.0))) / entry_d if entry_d > 0 else Decimal("0")
    qty_cap_bp = buying_power_d / entry_d if entry_d > 0 and side.lower() == "buy" else qty_by_risk
    if side.lower() == "sell" and allow_shorts:
        qty_cap_bp = buying_power_d / entry_d if entry_d > 0 else qty_by_risk

    qty = min(qty_by_risk, qty_cap_by_equity, qty_cap_bp) if side.lower() == "buy" else min(qty_by_risk, qty_cap_by_equity)
    qty = qty.to_integral_value(rounding="ROUND_FLOOR")
    if qty <= 0:
        return SizingResult(
            approved=False,
            qty=Decimal("0"),
            notional=None,
            rejection_reason="risk_insufficient_stop_distance",
        )

    notional = qty * entry_d
    return SizingResult(approved=True, qty=qty, notional=notional, rejection_reason=None)
