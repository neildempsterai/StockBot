"""Idempotency: re-sending same signal_uuid does not create second order (client_order_id reuse)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from stockbot.alpaca.client import AlpacaClient


def test_create_order_sends_client_order_id() -> None:
    """create_order includes client_order_id in request body."""
    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.post.return_value.status_code = 200
        mock_client.post.return_value.json.return_value = {"id": "ord-1", "client_order_id": "sig-123"}
        mock_client.post.return_value.raise_for_status = MagicMock()

        client = AlpacaClient.__new__(AlpacaClient)
        client._key_id = "key"
        client._secret = "secret"
        client._base = "https://paper-api.alpaca.markets"
        client._feed = "iex"

        client.create_order("AAPL", 10.0, "buy", client_order_id="sig-123")

        call = mock_client.post.call_args
        body = call[1]["json"]
        assert body["client_order_id"] == "sig-123"
        assert body["symbol"] == "AAPL"


def test_get_order_by_client_order_id_queries_by_signal_uuid() -> None:
    """get_order_by_client_order_id uses client_order_id (signal_uuid) for lookup."""
    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.return_value.status_code = 200
        mock_client.get.return_value.json.return_value = {"id": "ord-1", "client_order_id": "sig-123"}

        client = AlpacaClient.__new__(AlpacaClient)
        client._key_id = "key"
        client._secret = "secret"
        client._base = "https://paper-api.alpaca.markets"
        client._feed = "iex"

        result = client.get_order_by_client_order_id("sig-123")
        assert result is not None
        assert result["client_order_id"] == "sig-123"
        call = mock_client.get.call_args
        assert call[1]["params"]["client_order_id"] == "sig-123"
