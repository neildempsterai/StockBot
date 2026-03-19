"""Alpaca paper trade_updates WebSocket. Handles binary frames (paper endpoint)."""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Any

import websockets
from websockets.client import WebSocketClientProtocol

from stockbot.alpaca.types import TradeUpdate
from stockbot.config import get_settings

TradeUpdateHandler = Callable[[TradeUpdate], Awaitable[None]]


class TradingStreamClient:
    """
    Single connection to Alpaca paper trade_updates stream.
    Paper endpoint may send binary frames; we parse both text and binary.
    """

    def __init__(
        self,
        *,
        url: str | None = None,
        key_id: str | None = None,
        secret: str | None = None,
    ) -> None:
        s = get_settings()
        self._url = url or s.alpaca_trading_ws_url
        self._key_id = key_id or s.alpaca_api_key_id
        self._secret = secret or s.alpaca_api_secret_key
        self._handlers: list[TradeUpdateHandler] = []
        self._ws: WebSocketClientProtocol | None = None

    def add_handler(self, handler: TradeUpdateHandler) -> None:
        self._handlers.append(handler)

    async def _dispatch(self, update: TradeUpdate) -> None:
        for h in self._handlers:
            await h(update)

    @staticmethod
    def _parse_update(raw: dict[str, Any]) -> TradeUpdate:
        order = raw.get("order", raw)
        event = raw.get("event", "unknown")
        filled_qty = Decimal(str(order.get("filled_qty") or order.get("filled_qty", 0)))
        filled_avg = order.get("filled_avg_price")
        return TradeUpdate(
            event=event,
            order_id=str(order.get("id", "")),
            client_order_id=str(order.get("client_order_id", "")),
            symbol=str(order.get("symbol", "")),
            side=str(order.get("side", "")),
            qty=Decimal(str(order.get("qty", 0))),
            filled_qty=filled_qty,
            filled_avg_price=Decimal(str(filled_avg)) if filled_avg is not None else None,
            raw=raw,
        )

    async def connect(self) -> None:
        self._ws = await websockets.connect(
            self._url,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        )
        await self._ws.send(json.dumps({
            "action": "auth",
            "key": self._key_id,
            "secret": self._secret,
        }))
        auth_resp = await self._ws.recv()
        if isinstance(auth_resp, bytes):
            auth_resp = auth_resp.decode("utf-8")
        auth_data = json.loads(auth_resp)
        if isinstance(auth_data, list):
            for item in auth_data:
                if item.get("T") == "success" or item.get("msg") == "authenticated":
                    break
            else:
                raise RuntimeError(f"Alpaca trading auth failed: {auth_data}")
        await self._ws.send(json.dumps({
            "action": "listen",
            "data": {"streams": ["trade_updates"]},
        }))

    async def run(self) -> None:
        await self.connect()
        try:
            async for raw in self._ws:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                messages = json.loads(raw) if isinstance(raw, str) else raw
                if not isinstance(messages, list):
                    messages = [messages]
                for msg in messages:
                    if isinstance(msg, dict) and msg.get("stream") == "trade_updates":
                        data = msg.get("data", msg)
                        if isinstance(data, dict) and ("order" in data or "event" in data):
                            update = self._parse_update(data)
                            await self._dispatch(update)
        finally:
            if self._ws:
                await self._ws.close()
                self._ws = None

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None
