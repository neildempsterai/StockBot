"""Fetch historical bars from Alpaca for backtest."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from stockbot.alpaca.client import AlpacaClient
from stockbot.alpaca.types import Bar
from stockbot.strategies.state import BarLike


def fetch_bars_range(
    symbols: list[str],
    start: datetime | str,
    end: datetime | str | None = None,
    *,
    timeframe: str = "1Min",
    feed: str = "iex",
    limit_per_request: int = 1000,
) -> list[BarLike]:
    """Fetch all bars for symbols in [start, end]; returns list of BarLike sorted by timestamp."""
    client = AlpacaClient()
    start_str = start.isoformat() if isinstance(start, datetime) else start
    end_str = end.isoformat() if isinstance(end, datetime) else end if end else None
    out: list[BarLike] = []
    page_token: str | None = None
    while True:
        bars, next_token = client.get_bars(
            symbols=symbols,
            start=start_str,
            end=end_str,
            timeframe=timeframe,
            limit=limit_per_request,
            page_token=page_token,
        )
        for b in bars:
            out.append(
                BarLike(
                    symbol=b.symbol,
                    open=b.open,
                    high=b.high,
                    low=b.low,
                    close=b.close,
                    volume=b.volume,
                    timestamp=b.timestamp,
                )
            )
        if not next_token:
            break
        page_token = next_token
    out.sort(key=lambda x: x.timestamp)
    return out
