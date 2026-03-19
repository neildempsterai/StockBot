"""Universe builder: static, watchlist, liquid_us_equities, custom. Filter by price/liquidity."""
from __future__ import annotations

import logging
from typing import Callable, Awaitable

from stockbot.alpaca.client import AlpacaClient
from stockbot.config import get_settings

logger = logging.getLogger(__name__)


def _static_universe() -> list[str]:
    settings = get_settings()
    raw = settings.stockbot_universe or ""
    return [s.strip() for s in raw.split(",") if s.strip()]


async def _watchlist_universe(get_watchlist_fn: Callable[[], Awaitable[list[str]]]) -> list[str]:
    try:
        return await get_watchlist_fn()
    except Exception as e:
        logger.warning("watchlist_universe failed: %s", e)
        return []


def _custom_universe() -> list[str]:
    settings = get_settings()
    raw = getattr(settings, "scanner_custom_universe", "") or ""
    return [s.strip() for s in raw.split(",") if s.strip()]


def _liquid_us_equities() -> list[str]:
    settings = get_settings()
    include_etfs = getattr(settings, "scanner_include_etfs", True)
    max_symbols = getattr(settings, "scanner_max_symbols", 500)
    client = AlpacaClient()
    symbols = client.fetch_tradable_us_equities(include_etfs=include_etfs, tradable_only=True)
    if len(symbols) > max_symbols:
        symbols = symbols[:max_symbols]
    return symbols


async def build_universe(
    mode: str,
    universe_mode: str,
    *,
    get_watchlist_fn: Callable[[], Awaitable[list[str]]] | None = None,
) -> list[str]:
    """
    Build symbol universe for scanner.
    mode: static | dynamic | hybrid (ignored for universe selection; universe_mode drives source).
    universe_mode: watchlist | liquid_us_equities | custom
    """
    if universe_mode == "watchlist" and get_watchlist_fn:
        symbols = await _watchlist_universe(get_watchlist_fn)
    elif universe_mode == "liquid_us_equities":
        symbols = _liquid_us_equities()
    elif universe_mode == "custom":
        symbols = _custom_universe()
    else:
        symbols = _static_universe()

    if not symbols:
        return _static_universe()

    settings = get_settings()
    max_sym = getattr(settings, "scanner_max_symbols", 500)
    if len(symbols) > max_sym:
        symbols = symbols[:max_sym]
    return symbols
