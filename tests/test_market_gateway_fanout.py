"""One-connection fan-out: only one Alpaca market-data connection; downstream receives events."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from stockbot.alpaca.stream_client import StreamClient
from stockbot.gateways.market_gateway import fan_out_handler, _serialize_payload


@pytest.mark.asyncio
async def test_fan_out_handler_pushes_to_redis_streams() -> None:
    """Fan-out handler pushes trade/quote/bar to Redis streams."""
    redis = AsyncMock()
    await fan_out_handler(redis, "trade", {"trade": None, "raw": {}})
    redis.xadd.assert_called_once()
    call = redis.xadd.call_args
    # xadd(stream_name, mapping, maxlen=...)
    mapping = call.args[1] if len(call.args) > 1 else call.kwargs
    assert "data" in mapping
    assert "trade" in mapping["data"]


@pytest.mark.asyncio
async def test_serialize_payload_handles_dataclass() -> None:
    """Payload with dataclass (e.g. Quote) is JSON-serializable."""
    from datetime import datetime, timezone
    from decimal import Decimal

    from stockbot.alpaca.types import Quote

    q = Quote(
        symbol="AAPL",
        bid_price=Decimal("150.0"),
        ask_price=Decimal("150.05"),
        bid_size=Decimal("100"),
        ask_size=Decimal("100"),
        timestamp=datetime.now(timezone.utc),
        feed="iex",
    )
    out = _serialize_payload({"quote": q})
    assert "quote" in out
    assert out["quote"]["symbol"] == "AAPL"
    assert float(out["quote"]["bid_price"]) == 150.0


def test_stream_client_single_connection() -> None:
    """StreamClient is the single connection owner; handlers are internal fan-out."""
    stream = StreamClient()
    assert stream._ws is None
    stream.add_handler(AsyncMock())
    assert len(stream._handlers) == 1
