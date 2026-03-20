"""
Portfolio-level risk manager: circuit breaker, heat tracking, combined exposure caps.
Operates across all strategies and holding types.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, UTC

logger = logging.getLogger(__name__)


@dataclass
class PortfolioRiskState:
    """Snapshot of portfolio-level risk metrics."""
    daily_realized_pnl: Decimal = Decimal("0")
    daily_unrealized_pnl: Decimal = Decimal("0")
    portfolio_heat: Decimal = Decimal("0")
    total_open_positions: int = 0
    intraday_positions: int = 0
    swing_positions: int = 0
    long_exposure: Decimal = Decimal("0")
    short_exposure: Decimal = Decimal("0")
    gross_exposure: Decimal = Decimal("0")
    net_exposure: Decimal = Decimal("0")
    trades_today: int = 0
    wins_today: int = 0
    losses_today: int = 0
    circuit_breaker_active: bool = False
    circuit_breaker_reason: str | None = None


class PortfolioRiskManager:
    """Real-time portfolio-level risk management."""

    def __init__(
        self,
        *,
        max_daily_loss_pct: float = 3.0,
        max_portfolio_heat_pct: float = 5.0,
        max_total_concurrent_positions: int = 6,
        max_daily_trades: int = 20,
        notional_equity: Decimal = Decimal("100000"),
    ) -> None:
        self._max_daily_loss_pct = Decimal(str(max_daily_loss_pct))
        self._max_portfolio_heat_pct = Decimal(str(max_portfolio_heat_pct))
        self._max_total_concurrent = max_total_concurrent_positions
        self._max_daily_trades = max_daily_trades
        self._equity = notional_equity

        self._daily_realized_pnl = Decimal("0")
        self._trades_today = 0
        self._wins_today = 0
        self._losses_today = 0
        self._circuit_breaker_active = False
        self._circuit_breaker_reason: str | None = None
        self._last_reset_date: str = ""

    def reset_daily(self) -> None:
        """Reset daily counters. Call at start of each trading day."""
        self._daily_realized_pnl = Decimal("0")
        self._trades_today = 0
        self._wins_today = 0
        self._losses_today = 0
        self._circuit_breaker_active = False
        self._circuit_breaker_reason = None

    def update_equity(self, equity: Decimal) -> None:
        self._equity = equity

    def record_trade_exit(self, pnl: Decimal) -> None:
        """Record a completed trade's P&L for circuit breaker tracking."""
        self._daily_realized_pnl += pnl
        self._trades_today += 1
        if pnl > 0:
            self._wins_today += 1
        elif pnl < 0:
            self._losses_today += 1
        self._check_circuit_breaker()

    def _check_circuit_breaker(self) -> None:
        if self._equity <= 0:
            return
        loss_pct = abs(self._daily_realized_pnl) / self._equity * 100
        if self._daily_realized_pnl < 0 and loss_pct >= self._max_daily_loss_pct:
            self._circuit_breaker_active = True
            self._circuit_breaker_reason = f"daily_loss_{loss_pct:.1f}pct_exceeds_{self._max_daily_loss_pct}pct"
            logger.warning(
                "circuit_breaker_activated reason=%s daily_pnl=%s equity=%s",
                self._circuit_breaker_reason, self._daily_realized_pnl, self._equity,
            )
        if self._trades_today >= self._max_daily_trades:
            self._circuit_breaker_active = True
            self._circuit_breaker_reason = f"max_daily_trades_{self._max_daily_trades}_reached"
            logger.warning("circuit_breaker_activated reason=%s", self._circuit_breaker_reason)

    def check_circuit_breaker(self) -> tuple[bool, str | None]:
        """Returns (blocked, reason) if circuit breaker is active."""
        if self._circuit_breaker_active:
            return (True, self._circuit_breaker_reason)
        return (False, None)

    def check_portfolio_heat(
        self,
        new_trade_risk: Decimal,
        current_positions_risk: Decimal,
    ) -> tuple[bool, str | None]:
        """Check if adding new_trade_risk would exceed portfolio heat limit.

        Heat = sum of (position_size * distance_to_stop) across all positions.
        Returns (blocked, reason).
        """
        if self._equity <= 0:
            return (True, "no_equity")
        total_heat = current_positions_risk + new_trade_risk
        heat_pct = total_heat / self._equity * 100
        if heat_pct > self._max_portfolio_heat_pct:
            return (True, f"portfolio_heat_{heat_pct:.1f}pct_exceeds_{self._max_portfolio_heat_pct}pct")
        return (False, None)

    def check_combined_positions(
        self,
        intraday_count: int,
        swing_count: int,
    ) -> tuple[bool, str | None]:
        """Check combined position count across all strategy types."""
        total = intraday_count + swing_count
        if total >= self._max_total_concurrent:
            return (True, f"total_positions_{total}_at_max_{self._max_total_concurrent}")
        return (False, None)

    def get_state(
        self,
        intraday_count: int = 0,
        swing_count: int = 0,
        portfolio_heat: Decimal = Decimal("0"),
    ) -> PortfolioRiskState:
        return PortfolioRiskState(
            daily_realized_pnl=self._daily_realized_pnl,
            portfolio_heat=portfolio_heat,
            total_open_positions=intraday_count + swing_count,
            intraday_positions=intraday_count,
            swing_positions=swing_count,
            trades_today=self._trades_today,
            wins_today=self._wins_today,
            losses_today=self._losses_today,
            circuit_breaker_active=self._circuit_breaker_active,
            circuit_breaker_reason=self._circuit_breaker_reason,
        )
