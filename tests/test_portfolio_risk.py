"""Tests for portfolio-level risk manager."""
from decimal import Decimal
from stockbot.risk.portfolio import PortfolioRiskManager


class TestCircuitBreaker:
    def test_no_trades_no_breaker(self):
        mgr = PortfolioRiskManager(max_daily_loss_pct=3.0, notional_equity=Decimal("100000"))
        blocked, reason = mgr.check_circuit_breaker()
        assert blocked is False
        assert reason is None

    def test_loss_triggers_breaker(self):
        mgr = PortfolioRiskManager(max_daily_loss_pct=3.0, notional_equity=Decimal("100000"))
        mgr.record_trade_exit(Decimal("-1500"))
        mgr.record_trade_exit(Decimal("-1600"))
        blocked, reason = mgr.check_circuit_breaker()
        assert blocked is True
        assert "daily_loss" in reason

    def test_wins_dont_trigger(self):
        mgr = PortfolioRiskManager(max_daily_loss_pct=3.0, notional_equity=Decimal("100000"))
        mgr.record_trade_exit(Decimal("5000"))
        mgr.record_trade_exit(Decimal("3000"))
        blocked, reason = mgr.check_circuit_breaker()
        assert blocked is False

    def test_max_trades_triggers_breaker(self):
        mgr = PortfolioRiskManager(max_daily_trades=5, notional_equity=Decimal("100000"))
        for _ in range(5):
            mgr.record_trade_exit(Decimal("100"))
        blocked, reason = mgr.check_circuit_breaker()
        assert blocked is True
        assert "max_daily_trades" in reason

    def test_reset_clears_breaker(self):
        mgr = PortfolioRiskManager(max_daily_loss_pct=1.0, notional_equity=Decimal("100000"))
        mgr.record_trade_exit(Decimal("-1500"))
        assert mgr.check_circuit_breaker()[0] is True
        mgr.reset_daily()
        assert mgr.check_circuit_breaker()[0] is False


class TestPortfolioHeat:
    def test_within_limits(self):
        mgr = PortfolioRiskManager(max_portfolio_heat_pct=5.0, notional_equity=Decimal("100000"))
        blocked, reason = mgr.check_portfolio_heat(Decimal("1000"), Decimal("2000"))
        assert blocked is False

    def test_exceeds_limit(self):
        mgr = PortfolioRiskManager(max_portfolio_heat_pct=5.0, notional_equity=Decimal("100000"))
        blocked, reason = mgr.check_portfolio_heat(Decimal("3000"), Decimal("3000"))
        assert blocked is True
        assert "portfolio_heat" in reason


class TestCombinedPositions:
    def test_within_max(self):
        mgr = PortfolioRiskManager(max_total_concurrent_positions=6)
        blocked, reason = mgr.check_combined_positions(2, 1)
        assert blocked is False

    def test_at_max(self):
        mgr = PortfolioRiskManager(max_total_concurrent_positions=6)
        blocked, reason = mgr.check_combined_positions(4, 2)
        assert blocked is True


class TestGetState:
    def test_state_snapshot(self):
        mgr = PortfolioRiskManager(notional_equity=Decimal("100000"))
        mgr.record_trade_exit(Decimal("500"))
        mgr.record_trade_exit(Decimal("-200"))
        state = mgr.get_state(intraday_count=2, swing_count=1)
        assert state.daily_realized_pnl == Decimal("300")
        assert state.trades_today == 2
        assert state.wins_today == 1
        assert state.losses_today == 1
        assert state.total_open_positions == 3
