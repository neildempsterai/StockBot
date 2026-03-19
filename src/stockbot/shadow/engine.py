"""
Shadow engine: ideal and realistic fill calculators, position lifecycle, exit logic.
Conservative intrabar: for long assume stop hits before target if both touched; for short same.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

# Defaults; config overrides
DEFAULT_SLIPPAGE_BPS = 5
DEFAULT_FEE_PER_SHARE = Decimal("0")


@dataclass
class ShadowFillParams:
    execution_mode: str  # "ideal" | "realistic"
    slippage_bps: int = DEFAULT_SLIPPAGE_BPS
    fee_per_share: Decimal = DEFAULT_FEE_PER_SHARE


def ideal_entry_price(side: str, bid: Decimal, ask: Decimal) -> Decimal:
    """Buy at ask, sell at bid."""
    if side == "buy":
        return ask
    return bid


def ideal_exit_price(side: str, bid: Decimal, ask: Decimal) -> Decimal:
    """Long exit at bid, short exit at ask."""
    if side == "buy":
        return bid  # closing long
    return ask  # closing short


def realistic_entry_price(side: str, bid: Decimal, ask: Decimal, slippage_bps: int) -> Decimal:
    """Buy: ask * (1 + slippage_bps/10000); sell: bid * (1 - slippage_bps/10000)."""
    if side == "buy":
        return (ask * (1 + Decimal(slippage_bps) / 10000)).quantize(Decimal("0.0001"))
    return (bid * (1 - Decimal(slippage_bps) / 10000)).quantize(Decimal("0.0001"))


def realistic_exit_price(side: str, bid: Decimal, ask: Decimal, slippage_bps: int) -> Decimal:
    """Long exit: bid worsened by slippage; short exit: ask worsened by slippage."""
    if side == "buy":
        return (bid * (1 - Decimal(slippage_bps) / 10000)).quantize(Decimal("0.0001"))
    return (ask * (1 + Decimal(slippage_bps) / 10000)).quantize(Decimal("0.0001"))


def compute_entry_fill(
    side: str,
    bid: Decimal,
    ask: Decimal,
    params: ShadowFillParams,
) -> Decimal:
    if params.execution_mode == "ideal":
        return ideal_entry_price(side, bid, ask)
    return realistic_entry_price(side, bid, ask, params.slippage_bps)


def compute_exit_fill(
    side: str,
    bid: Decimal,
    ask: Decimal,
    params: ShadowFillParams,
) -> Decimal:
    if params.execution_mode == "ideal":
        return ideal_exit_price(side, bid, ask)
    return realistic_exit_price(side, bid, ask, params.slippage_bps)


@dataclass
class ShadowPosition:
    """One open shadow position per symbol (one signal; ideal+realistic at close)."""
    signal_uuid: UUID
    symbol: str
    side: str  # buy | sell
    qty: Decimal
    entry_ts: datetime
    ideal_entry_price: Decimal
    realistic_entry_price: Decimal
    stop_price: Decimal
    target_price: Decimal
    slippage_bps: int
    fee_per_share: Decimal


def _gross_pnl(side: str, qty: Decimal, entry: Decimal, exit_price: Decimal) -> Decimal:
    if side == "buy":
        return (exit_price - entry) * qty
    return (entry - exit_price) * qty


def _fees(qty: Decimal, fee_per_share: Decimal) -> Decimal:
    return qty * fee_per_share


def resolve_exit_conservative(
    side: str,
    bar_high: Decimal,
    bar_low: Decimal,
    stop_price: Decimal,
    target_price: Decimal,
) -> tuple[Decimal, str]:
    """
    Intrabar: assume stop hits before target if both touched.
    Returns (exit_price, exit_reason).
    """
    if side == "buy":
        stop_hit = bar_low <= stop_price
        target_hit = bar_high >= target_price
        if stop_hit and target_hit:
            return (stop_price, "stop")
        if stop_hit:
            return (stop_price, "stop")
        if target_hit:
            return (target_price, "target")
    else:
        stop_hit = bar_high >= stop_price
        target_hit = bar_low <= target_price
        if stop_hit and target_hit:
            return (stop_price, "stop")
        if stop_hit:
            return (stop_price, "stop")
        if target_hit:
            return (target_price, "target")
    return (Decimal("0"), "open")


def _close_one(
    position: ShadowPosition,
    exit_ts: datetime,
    entry_price: Decimal,
    exit_price: Decimal,
    exit_reason: str,
    execution_mode: str,
) -> dict[str, Any]:
    gross = _gross_pnl(position.side, position.qty, entry_price, exit_price)
    fees = _fees(position.qty, position.fee_per_share) * 2
    net = gross - fees
    return {
        "signal_uuid": str(position.signal_uuid),
        "execution_mode": execution_mode,
        "entry_ts": position.entry_ts,
        "exit_ts": exit_ts,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "stop_price": position.stop_price,
        "target_price": position.target_price,
        "exit_reason": exit_reason,
        "qty": position.qty,
        "gross_pnl": gross,
        "net_pnl": net,
        "slippage_bps": position.slippage_bps,
        "fee_per_share": position.fee_per_share,
    }


def close_shadow_position(
    position: ShadowPosition,
    exit_ts: datetime,
    exit_price_ideal: Decimal,
    exit_price_realistic: Decimal,
    exit_reason: str,
) -> list[dict[str, Any]]:
    """Return two records for persistence: ideal and realistic."""
    return [
        _close_one(
            position, exit_ts,
            position.ideal_entry_price, exit_price_ideal,
            exit_reason, "ideal",
        ),
        _close_one(
            position, exit_ts,
            position.realistic_entry_price, exit_price_realistic,
            exit_reason, "realistic",
        ),
    ]


class ShadowState:
    """One open shadow position per symbol; track for exit logic."""

    def __init__(self) -> None:
        self._positions: dict[str, ShadowPosition] = {}

    def open_position(self, position: ShadowPosition) -> None:
        self._positions[position.symbol] = position

    def get_position(self, symbol: str) -> ShadowPosition | None:
        return self._positions.get(symbol)

    def close_position(self, symbol: str) -> None:
        self._positions.pop(symbol, None)

    def has_position(self, symbol: str) -> bool:
        return symbol in self._positions

    def symbols_with_positions(self) -> list[str]:
        return list(self._positions.keys())

    def clear_all(self) -> None:
        self._positions.clear()
