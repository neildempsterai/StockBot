"""Tests for daily context: ATR, EMA, volume computations."""
from decimal import Decimal
from stockbot.strategies.daily_context import DailyBar, DailyContext, _compute_atr, _compute_ema


def _make_bars(data: list[tuple]) -> list[DailyBar]:
    return [DailyBar(open=Decimal(str(o)), high=Decimal(str(h)), low=Decimal(str(l)), close=Decimal(str(c)), volume=v) for o, h, l, c, v in data]


class TestATR:
    def test_basic_atr(self):
        bars = _make_bars([
            (100, 105, 95, 102, 1000),
            (102, 108, 98, 105, 1200),
            (105, 110, 100, 107, 1100),
        ])
        atr = _compute_atr(bars, period=2)
        assert atr is not None
        assert atr > 0

    def test_insufficient_bars(self):
        bars = _make_bars([(100, 105, 95, 102, 1000)])
        assert _compute_atr(bars) is None

    def test_atr_uses_true_range(self):
        bars = _make_bars([
            (100, 105, 95, 102, 1000),
            (102, 103, 101, 102, 1000),  # narrow bar but gap from prev close
        ])
        atr = _compute_atr(bars, period=1)
        assert atr is not None
        assert atr >= Decimal("1")  # true range includes gap


class TestEMA:
    def test_basic_ema(self):
        values = [Decimal(str(x)) for x in [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]]
        ema = _compute_ema(values, 5)
        assert ema is not None
        assert ema > Decimal("14")  # EMA of rising sequence biased to recent

    def test_insufficient_period(self):
        values = [Decimal("10"), Decimal("11")]
        assert _compute_ema(values, 5) is None

    def test_constant_series(self):
        values = [Decimal("50")] * 20
        ema = _compute_ema(values, 9)
        assert ema == Decimal("50.00")


class TestDailyContext:
    def test_compute(self):
        ctx = DailyContext(symbol="TEST")
        ctx.daily_bars = _make_bars([
            (100, 105, 95, 102, 10000),
            (102, 108, 98, 105, 12000),
            (105, 110, 100, 107, 11000),
            (107, 112, 103, 110, 13000),
            (110, 115, 105, 112, 14000),
            (112, 118, 108, 115, 15000),
            (115, 120, 110, 118, 16000),
            (118, 122, 113, 120, 17000),
            (120, 125, 115, 122, 18000),
            (122, 128, 118, 125, 19000),
            (125, 130, 120, 128, 20000),
            (128, 132, 123, 130, 21000),
            (130, 135, 125, 132, 22000),
            (132, 138, 128, 135, 23000),
            (135, 140, 130, 137, 24000),
        ])
        ctx.compute()
        assert ctx.atr_14 is not None
        assert ctx.atr_14 > 0
        assert ctx.ema_9 is not None
        assert ctx.ema_9 > 0
        assert ctx.avg_daily_volume > 0
        assert ctx.avg_daily_dollar_volume > 0

    def test_empty_bars(self):
        ctx = DailyContext(symbol="EMPTY")
        ctx.compute()
        assert ctx.atr_14 is None
        assert ctx.ema_9 is None
        assert ctx.avg_daily_volume == 0
