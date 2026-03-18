"""Alpaca REST client: snapshot, orders, feed=iex."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from stockbot.alpaca.client import AlpacaClient


def test_get_snapshot_uses_feed_param() -> None:
    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.return_value.status_code = 200
        mock_client.get.return_value.json.return_value = {}
        mock_client.get.return_value.raise_for_status = MagicMock()

        client = AlpacaClient.__new__(AlpacaClient)
        client._key_id = "key"
        client._secret = "secret"
        client._base = "https://paper-api.alpaca.markets"
        client._feed = "iex"

        client.get_snapshot("AAPL")
        call = mock_client.get.call_args
        assert call[1]["params"]["feed"] == "iex"


def test_parse_snapshot_returns_none_for_empty() -> None:
    client = AlpacaClient.__new__(AlpacaClient)
    client._feed = "iex"
    assert client._parse_snapshot("AAPL", {}) is None
