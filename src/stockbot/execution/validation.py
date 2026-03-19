"""
Execution validation for paper orders (strategy and operator test).
Checks account, asset, position, extended-hours constraints before submitting.
Returns structured reason codes; no order authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from stockbot.config import get_settings


# Reason codes for validation failures
PAPER_DISABLED = "paper_disabled"
ACCOUNT_NOT_TRADABLE = "account_not_tradable"
INSUFFICIENT_BUYING_POWER = "insufficient_buying_power"
ASSET_NOT_TRADABLE = "asset_not_tradable"
ASSET_NOT_SHORTABLE = "asset_not_shortable"
SHORTS_DISABLED = "shorts_disabled"
NO_LONG_POSITION = "no_long_position"
NO_SHORT_POSITION = "no_short_position"
INSUFFICIENT_POSITION_QTY = "insufficient_position_qty"
INVALID_EXTENDED_HOURS_ORDER = "invalid_extended_hours_order"
MARKET_CLOSED_MARKET_NOT_ALLOWED = "market_closed_market_not_allowed"
FRACTIONAL_SHORT_NOT_ALLOWED = "fractional_short_not_allowed"
PDT_RESTRICTION_POSSIBLE = "pdt_restriction_possible"
VALIDATION_ERROR = "validation_error"


@dataclass
class ValidationResult:
    allowed: bool
    reason_code: str | None
    message: str | None = None


def _decimal(v: Any, default: Decimal | None = None) -> Decimal:
    if v is None:
        return default or Decimal("0")
    try:
        return Decimal(str(v))
    except Exception:
        return default or Decimal("0")


def validate_buy_open(
    *,
    account: dict[str, Any],
    asset: dict[str, Any] | None,
    qty: Decimal | float,
    order_type: str,
    extended_hours: bool,
    limit_price: Decimal | float | None,
) -> ValidationResult:
    """Validate BUY to open long: account tradable, paper enabled, buying power, asset tradable, extended-hours rules."""
    settings = get_settings()
    if not getattr(settings, "paper_execution_enabled", False):
        return ValidationResult(False, PAPER_DISABLED, "Paper execution is disabled")
    if account.get("trading_blocked") or account.get("account_blocked"):
        return ValidationResult(False, ACCOUNT_NOT_TRADABLE, "Account is not tradable")
    buying_power = _decimal(account.get("buying_power"))
    if buying_power <= 0:
        return ValidationResult(False, INSUFFICIENT_BUYING_POWER, "No buying power")
    if asset is None:
        return ValidationResult(False, ASSET_NOT_TRADABLE, "Asset not found")
    if not asset.get("tradable", True):
        return ValidationResult(False, ASSET_NOT_TRADABLE, "Asset is not tradable")
    if extended_hours:
        if (order_type or "market").lower() != "limit":
            return ValidationResult(False, INVALID_EXTENDED_HOURS_ORDER, "Extended hours require limit order")
        if limit_price is None or _decimal(limit_price) <= 0:
            return ValidationResult(False, INVALID_EXTENDED_HOURS_ORDER, "Extended hours require limit_price")
    return ValidationResult(True, None)


def validate_sell_close(
    *,
    account: dict[str, Any],
    position: dict[str, Any] | None,
    qty: Decimal | float,
    order_type: str,
    extended_hours: bool,
    limit_price: Decimal | float | None,
) -> ValidationResult:
    """Validate SELL to close long: account tradable, paper enabled, long position exists and qty sufficient."""
    settings = get_settings()
    if not getattr(settings, "paper_execution_enabled", False):
        return ValidationResult(False, PAPER_DISABLED, "Paper execution is disabled")
    if account.get("trading_blocked") or account.get("account_blocked"):
        return ValidationResult(False, ACCOUNT_NOT_TRADABLE, "Account is not tradable")
    if position is None:
        return ValidationResult(False, NO_LONG_POSITION, "No long position for symbol")
    pos_qty = _decimal(position.get("qty"))
    if pos_qty <= 0:
        return ValidationResult(False, NO_LONG_POSITION, "Position is not long")
    qty_d = _decimal(qty)
    if qty_d <= 0 or qty_d > pos_qty:
        return ValidationResult(False, INSUFFICIENT_POSITION_QTY, "Qty exceeds long position")
    if extended_hours:
        if (order_type or "market").lower() != "limit":
            return ValidationResult(False, INVALID_EXTENDED_HOURS_ORDER, "Extended hours require limit order")
        if limit_price is None or _decimal(limit_price) <= 0:
            return ValidationResult(False, INVALID_EXTENDED_HOURS_ORDER, "Extended hours require limit_price")
    return ValidationResult(True, None)


def validate_short_open(
    *,
    account: dict[str, Any],
    asset: dict[str, Any] | None,
    qty: Decimal | float,
    order_type: str,
    extended_hours: bool,
    limit_price: Decimal | float | None,
) -> ValidationResult:
    """Validate SELL to open short: account tradable, paper enabled, shorts enabled, asset shortable, whole shares."""
    settings = get_settings()
    if not getattr(settings, "paper_execution_enabled", False):
        return ValidationResult(False, PAPER_DISABLED, "Paper execution is disabled")
    if account.get("trading_blocked") or account.get("account_blocked"):
        return ValidationResult(False, ACCOUNT_NOT_TRADABLE, "Account is not tradable")
    if not getattr(settings, "paper_allow_shorts", False):
        return ValidationResult(False, SHORTS_DISABLED, "Shorts are disabled")
    if asset is None:
        return ValidationResult(False, ASSET_NOT_TRADABLE, "Asset not found")
    if not asset.get("tradable", True):
        return ValidationResult(False, ASSET_NOT_TRADABLE, "Asset is not tradable")
    if not asset.get("shortable", True):
        return ValidationResult(False, ASSET_NOT_SHORTABLE, "Asset is not shortable")
    qty_d = _decimal(qty)
    if qty_d <= 0:
        return ValidationResult(False, VALIDATION_ERROR, "Qty must be positive")
    if qty_d != int(qty_d):
        return ValidationResult(False, FRACTIONAL_SHORT_NOT_ALLOWED, "Short orders require whole shares")
    if extended_hours:
        if (order_type or "market").lower() != "limit":
            return ValidationResult(False, INVALID_EXTENDED_HOURS_ORDER, "Extended hours require limit order")
        if limit_price is None or _decimal(limit_price) <= 0:
            return ValidationResult(False, INVALID_EXTENDED_HOURS_ORDER, "Extended hours require limit_price")
    return ValidationResult(True, None)


def validate_buy_cover(
    *,
    account: dict[str, Any],
    position: dict[str, Any] | None,
    qty: Decimal | float,
    order_type: str,
    extended_hours: bool,
    limit_price: Decimal | float | None,
) -> ValidationResult:
    """Validate BUY to cover short: account tradable, paper enabled, short position exists and qty sufficient."""
    settings = get_settings()
    if not getattr(settings, "paper_execution_enabled", False):
        return ValidationResult(False, PAPER_DISABLED, "Paper execution is disabled")
    if account.get("trading_blocked") or account.get("account_blocked"):
        return ValidationResult(False, ACCOUNT_NOT_TRADABLE, "Account is not tradable")
    if position is None:
        return ValidationResult(False, NO_SHORT_POSITION, "No short position for symbol")
    pos_qty = _decimal(position.get("qty"))
    if pos_qty >= 0:
        return ValidationResult(False, NO_SHORT_POSITION, "Position is not short")
    # qty to cover is positive; position qty is negative
    qty_d = _decimal(qty)
    if qty_d <= 0 or qty_d > abs(pos_qty):
        return ValidationResult(False, INSUFFICIENT_POSITION_QTY, "Qty exceeds short position")
    if extended_hours:
        if (order_type or "market").lower() != "limit":
            return ValidationResult(False, INVALID_EXTENDED_HOURS_ORDER, "Extended hours require limit order")
        if limit_price is None or _decimal(limit_price) <= 0:
            return ValidationResult(False, INVALID_EXTENDED_HOURS_ORDER, "Extended hours require limit_price")
    return ValidationResult(True, None)
