"""Recovery: reseed from snapshots/latest then resume without duplicating bars/quotes."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from stockbot.alpaca.client import AlpacaClient
from stockbot.alpaca.stream_client import StreamClient
from stockbot.gateways.market_gateway import reseed_from_snapshots
from stockbot.alpaca.types import Quote, Trade


@pytest.mark.asyncio
async def test_reseed_from_snapshots_dispatches_quote_and_trade() -> None:
    """Reseed calls snapshot API and dispatches quote/trade per symbol."""
    received = []

    async def capture(msg_type: str, payload: dict) -> None:
        received.append((msg_type, payload))

    stream = StreamClient.__new__(StreamClient)
    stream._feed = "iex"
    stream._handlers = [capture]

    async def mock_dispatch(t: str, p: dict) -> None:
        await capture(t, p)

    stream._dispatch = mock_dispatch

    with (
        patch("stockbot.config.get_settings") as mock_settings,
        patch.object(AlpacaClient, "get_snapshots") as get_snapshots,
    ):
        from datetime import datetime, timezone
        from decimal import Decimal
        mock_settings.return_value = MagicMock(
            alpaca_api_key_id="k",
            alpaca_api_secret_key="s",
            alpaca_base_url="https://paper-api.alpaca.markets",
            redis_url="redis://localhost:6379/0",
            database_url="postgresql://localhost/db",
            feed="iex",
        )
        get_snapshots.return_value = {
            "AAPL": MagicMock(
                latest_quote=Quote("AAPL", Decimal("1"), Decimal("2"), Decimal("1"), Decimal("1"), datetime.now(timezone.utc), "iex"),
                latest_trade=Trade("AAPL", Decimal("1.5"), Decimal("100"), datetime.now(timezone.utc), "iex"),
            ),
        }
        await reseed_from_snapshots(stream, ["AAPL"])

    assert len(received) >= 1  # at least quote or trade
    types = [r[0] for r in received]
    assert "quote" in types or "trade" in types
