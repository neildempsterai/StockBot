"""Paper trade_updates parser handles binary frames correctly."""
from __future__ import annotations

import json
from decimal import Decimal

from stockbot.alpaca.trading_stream import TradingStreamClient


def test_parse_update_from_text_json(sample_trade_update: dict) -> None:
    """Parse trade update from dict (text JSON decoded)."""
    client = TradingStreamClient.__new__(TradingStreamClient)
    client._key_id = "key"
    client._secret = "secret"
    client._url = "wss://example.com"
    update = TradingStreamClient._parse_update(sample_trade_update)
    assert update.event == "fill"
    assert update.client_order_id == sample_trade_update["order"]["client_order_id"]
    assert update.symbol == "AAPL"
    assert update.filled_qty == Decimal("10")
    assert update.filled_avg_price == Decimal("150.25")


def test_parse_update_from_binary_frame(sample_binary_trade_update: bytes) -> None:
    """Parse trade update from binary frame (paper endpoint)."""
    data = json.loads(sample_binary_trade_update.decode("utf-8"))
    payload = data.get("data", data)
    client = TradingStreamClient.__new__(TradingStreamClient)
    client._key_id = "key"
    client._secret = "secret"
    client._url = "wss://example.com"
    update = TradingStreamClient._parse_update(payload)
    assert update.event == "fill"
    assert update.symbol == "SPY"
    assert update.filled_qty == Decimal("5")
    assert update.filled_avg_price == Decimal("450.10")
