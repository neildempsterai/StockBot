"""Single Alpaca data WebSocket connection. IEX feed; fan-out is internal (caller uses Redis or in-process)."""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import websockets
from websockets.client import WebSocketClientProtocol

from stockbot.alpaca.types import Bar, Quote, Trade
from stockbot.config import get_settings

MessageHandler = Callable[[str, dict[str, Any]], Awaitable[None]]


class StreamClient:
    """
    One connection to Alpaca data stream. Subscribe to trades, quotes, bars (and news).
    Caller is responsible for fan-out to downstream consumers.
    """

    def __init__(
        self,
        *,
        url: str | None = None,
        key_id: str | None = None,
        secret: str | None = None,
        feed: str = "iex",
    ) -> None:
        s = get_settings()
        self._url = url or s.alpaca_data_ws_url
        self._key_id = key_id or s.alpaca_api_key_id
        self._secret = secret or s.alpaca_api_secret_key
        self._feed = feed
        self._handlers: list[MessageHandler] = []
        self._ws: WebSocketClientProtocol | None = None
        self._subscribed: set[str] = set()

    def add_handler(self, handler: MessageHandler) -> None:
        self._handlers.append(handler)

    async def _dispatch(self, msg_type: str, payload: dict[str, Any]) -> None:
        for h in self._handlers:
            await h(msg_type, payload)

    @staticmethod
    def _parse_ts(ts: str | None) -> datetime:
        if not ts:
            return datetime.now(datetime.UTC)
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    def _parse_trade(self, data: dict[str, Any]) -> Trade:
        return Trade(
            symbol=data["S"],
            price=Decimal(str(data["p"])),
            size=Decimal(str(data["s"])),
            timestamp=self._parse_ts(data.get("t")),
            feed=self._feed,
        )

    def _parse_quote(self, data: dict[str, Any]) -> Quote:
        return Quote(
            symbol=data["S"],
            bid_price=Decimal(str(data["bp"])),
            ask_price=Decimal(str(data["ap"])),
            bid_size=Decimal(str(data["bs"])),
            ask_size=Decimal(str(data["as"])),
            timestamp=self._parse_ts(data.get("t")),
            feed=self._feed,
        )

    def _parse_bar(self, data: dict[str, Any]) -> Bar:
        return Bar(
            symbol=data["S"],
            open=Decimal(str(data["o"])),
            high=Decimal(str(data["h"])),
            low=Decimal(str(data["l"])),
            close=Decimal(str(data["c"])),
            volume=int(data.get("v", 0)),
            timestamp=self._parse_ts(data.get("t")),
            feed=self._feed,
        )

    async def connect(self) -> None:
        self._ws = await websockets.connect(
            self._url,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        )
        # Auth
        await self._ws.send(json.dumps({
            "action": "auth",
            "key": self._key_id,
            "secret": self._secret,
        }))
        auth_resp = await self._ws.recv()
        auth_data = json.loads(auth_resp)
        if isinstance(auth_data, list):
            for item in auth_data:
                if item.get("T") == "success" and item.get("msg") == "authenticated":
                    break
            else:
                raise RuntimeError(f"Alpaca data auth failed: {auth_data}")
        if self._subscribed:
            await self._send_subscribe()

    async def _send_subscribe(self) -> None:
        if not self._ws:
            return
        subs = list(self._subscribed)
        await self._ws.send(json.dumps({
            "action": "subscribe",
            "trades": list(subs),
            "quotes": list(subs),
            "bars": list(subs),
        }))

    def subscribe(self, symbols: list[str]) -> None:
        for s in symbols:
            self._subscribed.add(s)

    async def subscribe_news(self) -> None:
        if not self._ws:
            return
        await self._ws.send(json.dumps({"action": "subscribe", "news": ["*"]}))

    async def run(self) -> None:
        await self.connect()
        try:
            async for raw in self._ws:
                if isinstance(raw, bytes):
                    # Binary frame (some streams); try decode
                    raw = raw.decode("utf-8")
                messages = json.loads(raw) if isinstance(raw, str) else raw
                if not isinstance(messages, list):
                    messages = [messages]
                for msg in messages:
                    await self._handle_message(msg)
        finally:
            if self._ws:
                await self._ws.close()
                self._ws = None

    async def _handle_message(self, msg: dict[str, Any]) -> None:
        t = msg.get("T")
        if t == "t":
            trade = self._parse_trade(msg)
            await self._dispatch("trade", {"trade": trade, "raw": msg})
        elif t == "q":
            quote = self._parse_quote(msg)
            await self._dispatch("quote", {"quote": quote, "raw": msg})
        elif t == "b":
            bar = self._parse_bar(msg)
            await self._dispatch("bar", {"bar": bar, "raw": msg})
        elif t == "n":
            await self._dispatch("news", {"raw": msg})
        else:
            await self._dispatch("raw", msg)

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None
