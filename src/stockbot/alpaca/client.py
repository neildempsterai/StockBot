"""Alpaca REST client. Cold start, reconnect recovery, reconciliation. feed=iex."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx

from stockbot.alpaca.types import Bar, Quote, Snapshot, Trade
from stockbot.config import get_settings


class AlpacaClient:
    """REST-only. Use for snapshots, latest, historical, orders, positions."""

    def __init__(
        self,
        *,
        key_id: str | None = None,
        secret: str | None = None,
        base_url: str | None = None,
        feed: str = "iex",
    ) -> None:
        s = get_settings()
        self._key_id = key_id or s.alpaca_api_key_id
        self._secret = secret or s.alpaca_api_secret_key
        self._base = (base_url or s.alpaca_base_url).rstrip("/")
        self._feed = feed

    def _headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self._key_id,
            "APCA-API-SECRET-KEY": self._secret,
        }

    def _url(self, path: str) -> str:
        return f"{self._base}{path}"

    # ---------- Snapshot / latest (recovery, cold start) ----------

    def get_snapshot(self, symbol: str) -> Snapshot | None:
        """Multi-symbol snapshot: latest trade, quote, minute bar, daily, prev daily."""
        with httpx.Client() as client:
            r = client.get(
                self._url(f"/v2/stocks/{symbol}/snapshot"),
                params={"feed": self._feed},
                headers=self._headers(),
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()
        return self._parse_snapshot(symbol, data)

    def get_snapshots(self, symbols: list[str]) -> dict[str, Snapshot | None]:
        """Snapshots for multiple symbols (recovery reseed)."""
        with httpx.Client() as client:
            r = client.get(
                self._url("/v2/stocks/snapshots"),
                params={"symbols": ",".join(symbols), "feed": self._feed},
                headers=self._headers(),
                timeout=15.0,
            )
            r.raise_for_status()
            raw = r.json()
        return {
            sym: self._parse_snapshot(sym, raw.get(sym, {}))
            for sym in symbols
        }

    def _parse_snapshot(self, symbol: str, data: dict[str, Any]) -> Snapshot | None:
        if not data:
            return None
        latest_trade = None
        if "latestTrade" in data and data["latestTrade"]:
            t = data["latestTrade"]
            latest_trade = Trade(
                symbol=symbol,
                price=Decimal(str(t["p"])),
                size=Decimal(str(t["s"])),
                timestamp=self._parse_ts(t.get("t")),
                feed=self._feed,
            )
        latest_quote = None
        if "latestQuote" in data and data["latestQuote"]:
            q = data["latestQuote"]
            latest_quote = Quote(
                symbol=symbol,
                bid_price=Decimal(str(q["bp"])),
                ask_price=Decimal(str(q["ap"])),
                bid_size=Decimal(str(q["bs"])),
                ask_size=Decimal(str(q["as"])),
                timestamp=self._parse_ts(q.get("t")),
                feed=self._feed,
            )
        def bar(key: str) -> Bar | None:
            b = data.get(key)
            if not b:
                return None
            return Bar(
                symbol=symbol,
                open=Decimal(str(b["o"])),
                high=Decimal(str(b["h"])),
                low=Decimal(str(b["l"])),
                close=Decimal(str(b["c"])),
                volume=int(b.get("v", 0)),
                timestamp=self._parse_ts(b.get("t")),
                feed=self._feed,
            )
        return Snapshot(
            symbol=symbol,
            latest_trade=latest_trade,
            latest_quote=latest_quote,
            minute_bar=bar("minuteBar"),
            daily_bar=bar("dailyBar"),
            prev_daily_bar=bar("prevDailyBar"),
            feed=self._feed,
        )

    @staticmethod
    def _parse_ts(ts: Any) -> datetime:
        if ts is None:
            return datetime.now(timezone.utc)
        if isinstance(ts, str):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return datetime.now(timezone.utc)

    # ---------- Orders (idempotency: client_order_id = signal_uuid) ----------

    def create_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        *,
        client_order_id: str,
        time_in_force: str = "day",
        order_type: str = "market",
    ) -> dict[str, Any]:
        """Submit order. client_order_id must equal signal_uuid."""
        with httpx.Client() as client:
            r = client.post(
                self._url("/v2/orders"),
                json={
                    "symbol": symbol,
                    "qty": str(qty),
                    "side": side,
                    "type": order_type,
                    "time_in_force": time_in_force,
                    "client_order_id": client_order_id,
                },
                headers=self._headers(),
                timeout=10.0,
            )
            r.raise_for_status()
            return r.json()

    def get_order_by_client_order_id(self, client_order_id: str) -> dict[str, Any] | None:
        """Query status by client_order_id (signal_uuid)."""
        with httpx.Client() as client:
            r = client.get(
                self._url("/v2/orders:by_client_order_id"),
                params={"client_order_id": client_order_id},
                headers=self._headers(),
                timeout=10.0,
            )
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()

    def list_orders(self, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with httpx.Client() as client:
            params: dict[str, Any] = {"limit": limit}
            if status:
                params["status"] = status
            r = client.get(
                self._url("/v2/orders"),
                params=params,
                headers=self._headers(),
                timeout=10.0,
            )
            r.raise_for_status()
            return r.json()

    def list_positions(self) -> list[dict[str, Any]]:
        with httpx.Client() as client:
            r = client.get(
                self._url("/v2/positions"),
                headers=self._headers(),
                timeout=10.0,
            )
            r.raise_for_status()
            return r.json()
