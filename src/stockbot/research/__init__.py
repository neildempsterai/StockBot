"""Research and backtest: historical bars, regimes, run deterministic strategy over time."""
from stockbot.research.backtest import run_backtest
from stockbot.research.datasets import fetch_bars_range
from stockbot.research.regimes import classify_regime_spy

__all__ = ["run_backtest", "fetch_bars_range", "classify_regime_spy"]
