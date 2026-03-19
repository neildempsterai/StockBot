"""
Limit checks for paper trading. Input: account state, positions, candidate side/symbol.
Returns rejection reason code or None if allowed.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any


def check_limits(
    *,
    equity: Decimal | float,
    buying_power: Decimal | float,
    positions: list[dict[str, Any]],
    symbol: str,
    side: str,
    allow_shorts: bool,
    max_concurrent_positions: int,
    max_gross_exposure_pct_equity: float,
    max_symbol_exposure_pct_equity: float,
) -> str | None:
    """
    Check position/exposure limits. Returns reason code if blocked, else None.
    """
    equity_d = Decimal(str(equity)) if equity is not None else Decimal("0")
    if equity_d <= 0:
        return "risk_insufficient_buying_power"
    buying_power_d = Decimal(str(buying_power)) if buying_power is not None else Decimal("0")

    side_lower = (side or "").lower()
    if side_lower == "sell" and not allow_shorts:
        return "risk_shorts_disabled"

    open_positions = [p for p in positions if p.get("symbol") and float(p.get("qty", 0) or 0) != 0]
    if len(open_positions) >= max_concurrent_positions:
        # Already at max; adding new symbol would exceed
        existing_symbols = {p.get("symbol") for p in open_positions}
        if symbol not in existing_symbols:
            return "risk_max_positions_reached"

    long_mv = Decimal("0")
    short_mv = Decimal("0")
    symbol_mv = Decimal("0")
    for p in open_positions:
        qty = Decimal(str(p.get("qty") or 0))
        mv = Decimal(str(p.get("market_value") or 0))
        if mv == 0 and "current_price" in p:
            mv = qty * Decimal(str(p["current_price"]))
        if qty > 0:
            long_mv += mv
        else:
            short_mv += abs(mv)
        if str(p.get("symbol")) == symbol:
            symbol_mv += abs(mv)

    gross_exposure = long_mv + short_mv
    max_gross = equity_d * Decimal(str(max_gross_exposure_pct_equity / 100.0))
    if gross_exposure >= max_gross and max_gross > 0:
        return "risk_gross_exposure_limit"

    max_symbol = equity_d * Decimal(str(max_symbol_exposure_pct_equity / 100.0))
    if symbol_mv >= max_symbol and max_symbol > 0:
        return "risk_symbol_exposure_limit"

    return None
