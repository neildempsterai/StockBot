"""Pytest fixtures. Use env or overrides for Alpaca/Redis/DB in tests."""
from __future__ import annotations

import os
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic_settings import BaseSettings


@pytest.fixture
def signal_uuid() -> str:
    return str(uuid4())


@pytest.fixture
def client_order_id(signal_uuid: str) -> str:
    return signal_uuid


@pytest.fixture
def sample_trade_update(client_order_id: str) -> dict:
    return {
        "event": "fill",
        "order": {
            "id": "alpaca-order-123",
            "client_order_id": client_order_id,
            "symbol": "AAPL",
            "side": "buy",
            "qty": "10",
            "filled_qty": "10",
            "filled_avg_price": "150.25",
        },
    }


@pytest.fixture
def sample_binary_trade_update(client_order_id: str) -> bytes:
    import json
    return json.dumps({
        "stream": "trade_updates",
        "data": {
            "event": "fill",
            "order": {
                "id": "alpaca-order-456",
                "client_order_id": client_order_id,
                "symbol": "SPY",
                "side": "sell",
                "qty": "5",
                "filled_qty": "5",
                "filled_avg_price": "450.10",
            },
        },
    }).encode("utf-8")
