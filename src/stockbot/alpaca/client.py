"""Alpaca REST client. Cold start, reconnect recovery, reconciliation. feed=iex."""
from __future__ import annotations

from datetime import UTC, datetime
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
        data_base_url: str | None = None,
        feed: str = "iex",
    ) -> None:
        s = get_settings()
        self._key_id = key_id or s.alpaca_api_key_id
        self._secret = secret or s.alpaca_api_secret_key
        self._base = (base_url or s.alpaca_base_url).rstrip("/")
        self._data_base = (
            (data_base_url or getattr(s, "alpaca_data_base_url", "https://data.alpaca.markets"))
            .rstrip("/")
        )
        self._feed = feed

    def _headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self._key_id,
            "APCA-API-SECRET-KEY": self._secret,
        }

    def _url(self, path: str) -> str:
        return f"{self._base}{path}"

    def _data_url(self, path: str) -> str:
        return f"{self._data_base}{path}"

    # ---------- Snapshot / latest (recovery, cold start) ----------

    def get_snapshot(self, symbol: str) -> Snapshot | None:
        """Snapshot: latest trade, quote, minute bar (data API, not trading API)."""
        with httpx.Client() as client:
            r = client.get(
                self._data_url(f"/v2/stocks/{symbol}/snapshot"),
                params={"feed": self._feed},
                headers=self._headers(),
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()
        return self._parse_snapshot(symbol, data)

    def get_snapshots(self, symbols: list[str]) -> dict[str, Snapshot | None]:
        """Snapshots for multiple symbols (data API; used for reseed)."""
        with httpx.Client() as client:
            r = client.get(
                self._data_url("/v2/stocks/snapshots"),
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
            return datetime.now(UTC)
        if isinstance(ts, str):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return datetime.now(UTC)

    # ---------- Historical bars (data API) ----------

    def get_bars(
        self,
        symbols: list[str],
        start: datetime | str,
        end: datetime | str | None = None,
        *,
        timeframe: str = "1Min",
        limit: int = 1000,
        page_token: str | None = None,
    ) -> tuple[list[Bar], str | None]:
        """Fetch minute bars from Alpaca data API. Returns (bars, next_page_token)."""
        start_str = start.isoformat() if isinstance(start, datetime) else start
        end_str = end.isoformat() if isinstance(end, datetime) else end if end else None
        params: dict[str, Any] = {
            "symbols": ",".join(symbols),
            "timeframe": timeframe,
            "limit": limit,
            "feed": self._feed,
            "start": start_str,
        }
        if end_str:
            params["end"] = end_str
        if page_token:
            params["page_token"] = page_token
        with httpx.Client() as client:
            r = client.get(
                self._data_url("/v2/stocks/bars"),
                params=params,
                headers=self._headers(),
                timeout=30.0,
            )
            r.raise_for_status()
            data = r.json()
        bars_raw = data.get("bars") or {}
        next_page_token = data.get("next_page_token")
        out: list[Bar] = []
        for sym, bar_list in bars_raw.items():
            if not isinstance(bar_list, list):
                continue
            for b in bar_list:
                out.append(
                    Bar(
                        symbol=sym,
                        open=Decimal(str(b["o"])),
                        high=Decimal(str(b["h"])),
                        low=Decimal(str(b["l"])),
                        close=Decimal(str(b["c"])),
                        volume=int(b.get("v", 0)),
                        timestamp=self._parse_ts(b.get("t")),
                        feed=self._feed,
                    )
                )
        return (out, next_page_token)

    # ---------- Latest (boot / reconnect; data API) ----------

    def get_quotes_latest(self, symbols: list[str]) -> dict[str, list[dict[str, Any]]]:
        """Latest quote per symbol. Data API."""
        with httpx.Client() as client:
            r = client.get(
                self._data_url("/v2/stocks/quotes/latest"),
                params={"symbols": ",".join(symbols), "feed": self._feed},
                headers=self._headers(),
                timeout=15.0,
            )
            r.raise_for_status()
            return r.json()

    def get_trades_latest(self, symbols: list[str]) -> dict[str, list[dict[str, Any]]]:
        """Latest trade(s) per symbol. Data API."""
        with httpx.Client() as client:
            r = client.get(
                self._data_url("/v2/stocks/trades/latest"),
                params={"symbols": ",".join(symbols), "feed": self._feed},
                headers=self._headers(),
                timeout=15.0,
            )
            r.raise_for_status()
            return r.json()

    def get_bars_latest(
        self, symbols: list[str], *, timeframe: str = "1Min"
    ) -> dict[str, list[dict[str, Any]]]:
        """Latest bar(s) per symbol. Data API."""
        with httpx.Client() as client:
            r = client.get(
                self._data_url("/v2/stocks/bars/latest"),
                params={"symbols": ",".join(symbols), "feed": self._feed, "timeframe": timeframe},
                headers=self._headers(),
                timeout=15.0,
            )
            r.raise_for_status()
            return r.json()

    # ---------- Historical quotes / news (research / replay; data API) ----------

    def get_historical_quotes(
        self,
        symbols: list[str],
        start: datetime | str,
        end: datetime | str | None = None,
        *,
        limit: int = 10000,
        page_token: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Historical quotes. Returns (list of quote objects, next_page_token)."""
        start_str = start.isoformat() if isinstance(start, datetime) else start
        end_str = end.isoformat() if isinstance(end, datetime) else end if end else None
        params: dict[str, Any] = {
            "symbols": ",".join(symbols),
            "start": start_str,
            "limit": limit,
            "feed": self._feed,
        }
        if end_str:
            params["end"] = end_str
        if page_token:
            params["page_token"] = page_token
        with httpx.Client() as client:
            r = client.get(
                self._data_url("/v2/stocks/quotes"),
                params=params,
                headers=self._headers(),
                timeout=30.0,
            )
            r.raise_for_status()
            data = r.json()
        quotes = data.get("quotes", [])
        next_token = data.get("next_page_token")
        return (quotes, next_token)

    def get_historical_news(
        self,
        symbols: list[str] | None = None,
        *,
        start: str | None = None,
        end: str | None = None,
        limit: int = 50,
        include_content: bool = True,
        sort: str = "desc",
        page_token: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Historical news. v1beta1. Returns (articles, next_page_token)."""
        params: dict[str, Any] = {
            "limit": limit,
            "include_content": str(include_content).lower(),
            "sort": sort,
        }
        if symbols:
            params["symbols"] = ",".join(symbols)
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if page_token:
            params["page_token"] = page_token
        with httpx.Client() as client:
            r = client.get(
                self._data_url("/v1beta1/news"),
                params=params,
                headers=self._headers(),
                timeout=30.0,
            )
            r.raise_for_status()
            data = r.json()
        news = data.get("news", data) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        next_token = data.get("next_page_token") if isinstance(data, dict) else None
        return (news or [], next_token)

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
        limit_price: float | None = None,
        extended_hours: bool = False,
    ) -> dict[str, Any]:
        """Submit order. client_order_id must equal signal_uuid (or paper_test_* for operator test)."""
        payload: dict[str, Any] = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
            "client_order_id": client_order_id,
        }
        if extended_hours:
            payload["extended_hours"] = True
        if limit_price is not None and order_type.lower() == "limit":
            payload["limit_price"] = str(limit_price)
        with httpx.Client() as client:
            r = client.post(
                self._url("/v2/orders"),
                json=payload,
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

    def list_orders(
        self,
        status: str | None = None,
        after: str | None = None,
        until: str | None = None,
        limit: int = 100,
        nested: bool | None = None,
    ) -> list[dict[str, Any]]:
        with httpx.Client() as client:
            params: dict[str, Any] = {"limit": limit}
            if status:
                params["status"] = status
            if after:
                params["after"] = after
            if until:
                params["until"] = until
            if nested is not None:
                params["nested"] = str(nested).lower()
            r = client.get(
                self._url("/v2/orders"),
                params=params,
                headers=self._headers(),
                timeout=30.0,  # Increased from 10.0 to handle slow responses
            )
            r.raise_for_status()
            return r.json()

    def replace_order(
        self,
        order_id: str,
        *,
        qty: int | None = None,
        limit_price: float | None = None,
        stop_price: float | None = None,
        time_in_force: str | None = None,
    ) -> dict[str, Any]:
        """Replace an open order (PATCH)."""
        body: dict[str, Any] = {}
        if qty is not None:
            body["qty"] = str(qty)
        if limit_price is not None:
            body["limit_price"] = str(limit_price)
        if stop_price is not None:
            body["stop_price"] = str(stop_price)
        if time_in_force is not None:
            body["time_in_force"] = time_in_force
        with httpx.Client() as client:
            r = client.patch(
                self._url(f"/v2/orders/{order_id}"),
                json=body,
                headers=self._headers(),
                timeout=10.0,
            )
            r.raise_for_status()
            return r.json()

    def cancel_order(self, order_id: str) -> dict[str, Any] | None:
        """Cancel one order. Returns order dict or None if 404."""
        with httpx.Client() as client:
            r = client.delete(
                self._url(f"/v2/orders/{order_id}"),
                headers=self._headers(),
                timeout=10.0,
            )
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()

    def cancel_all_orders(self) -> list[dict[str, Any]]:
        """Cancel all open orders. Returns list of cancelled order dicts."""
        with httpx.Client() as client:
            r = client.delete(
                self._url("/v2/orders"),
                headers=self._headers(),
                timeout=15.0,
            )
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else []

    def list_positions(self) -> list[dict[str, Any]]:
        with httpx.Client() as client:
            r = client.get(
                self._url("/v2/positions"),
                headers=self._headers(),
                timeout=10.0,
            )
            r.raise_for_status()
            return r.json()

    def get_position(self, symbol_or_asset_id: str) -> dict[str, Any] | None:
        """Single position by symbol or asset ID."""
        with httpx.Client() as client:
            r = client.get(
                self._url(f"/v2/positions/{symbol_or_asset_id}"),
                headers=self._headers(),
                timeout=10.0,
            )
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        """Order by ID."""
        with httpx.Client() as client:
            r = client.get(
                self._url(f"/v2/orders/{order_id}"),
                headers=self._headers(),
                timeout=10.0,
            )
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()

    # ---------- Account / paper truth (trading API) ----------

    def get_account(self) -> dict[str, Any]:
        """Account details: status, balances, buying power, tradable."""
        with httpx.Client() as client:
            r = client.get(
                self._url("/v2/account"),
                headers=self._headers(),
                timeout=10.0,
            )
            r.raise_for_status()
            return r.json()

    def get_clock(self) -> dict[str, Any]:
        """Market clock: is_open, next_open, next_close."""
        with httpx.Client() as client:
            r = client.get(
                self._url("/v2/clock"),
                headers=self._headers(),
                timeout=10.0,
            )
            r.raise_for_status()
            return r.json()

    def get_calendar(self, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
        """Trading calendar: market days, early closes. start/end in YYYY-MM-DD."""
        with httpx.Client() as client:
            params: dict[str, Any] = {}
            if start:
                params["start"] = start
            if end:
                params["end"] = end
            r = client.get(
                self._url("/v2/calendar"),
                params=params or None,
                headers=self._headers(),
                timeout=10.0,
            )
            r.raise_for_status()
            return r.json()

    def get_assets(self, status: str = "active", asset_class: str = "us_equity") -> list[dict[str, Any]]:
        """Tradable asset master. Assets may include overnight_tradable, overnight_halted (24/5)."""
        with httpx.Client() as client:
            r = client.get(
                self._url("/v2/assets"),
                params={"status": status, "asset_class": asset_class},
                headers=self._headers(),
                timeout=15.0,
            )
            r.raise_for_status()
            return r.json()

    def list_assets(
        self,
        status: str = "active",
        asset_class: str = "us_equity",
    ) -> list[dict[str, Any]]:
        """Alias for get_assets (scanner/universe)."""
        return self.get_assets(status=status, asset_class=asset_class)

    def get_stock_snapshots(self, symbols: list[str]) -> dict[str, Snapshot | None]:
        """Alias for get_snapshots; batch in chunks of 100 to respect API limits."""
        out: dict[str, Snapshot | None] = {}
        chunk = 100
        for i in range(0, len(symbols), chunk):
            part = symbols[i : i + chunk]
            out.update(self.get_snapshots(part))
        return out

    def get_stock_bars(
        self,
        symbols: list[str],
        timeframe: str,
        start: datetime | str,
        end: datetime | str | None = None,
        *,
        adjustment: str = "split",
        limit: int = 1000,
        page_token: str | None = None,
    ) -> tuple[list[Bar], str | None]:
        """Fetch bars (alias for get_bars with adjustment). Returns (bars, next_page_token)."""
        return self.get_bars(
            symbols,
            start=start,
            end=end,
            timeframe=timeframe,
            limit=limit,
            page_token=page_token,
        )

    def get_stock_quotes(
        self,
        symbol_or_symbols: str | list[str],
        start: datetime | str,
        end: datetime | str | None = None,
        *,
        limit: int = 10000,
        page_token: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Historical quotes for one or more symbols. Returns (quotes, next_page_token)."""
        sym_list = [symbol_or_symbols] if isinstance(symbol_or_symbols, str) else symbol_or_symbols
        return self.get_historical_quotes(
            symbols=sym_list,
            start=start,
            end=end,
            limit=limit,
            page_token=page_token,
        )

    def get_news(
        self,
        symbols: list[str] | None = None,
        *,
        start: str | None = None,
        end: str | None = None,
        limit: int = 50,
        page_token: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """News for symbol group. Returns (articles, next_page_token)."""
        return self.get_historical_news(
            symbols=symbols,
            start=start,
            end=end,
            limit=limit,
            page_token=page_token,
        )

    # Common ETF symbols (Alpaca asset class is us_equity for both stocks and ETFs; exclude by symbol when include_etfs=False)
    _COMMON_ETFS: frozenset[str] = frozenset(
        {"SPY", "QQQ", "IWM", "DIA", "VOO", "VTI", "VEA", "VWO", "EFA", "EEM", "GLD", "SLV", "XLF", "XLK", "XLE", "XLV", "XLI", "XLP", "XLY", "XLB", "XLU", "XLRE", "ARKK", "SOXL", "TQQQ", "SQQQ", "UPRO", "SDS", "QQQ", "IVV", "VTV", "VUG", "VXF", "VB", "VO", "VGT", "VHT", "VFH", "VNQ", "BND", "AGG", "LQD", "HYG", "JNK", "TLT", "IEF", "SHY", "MUB", "TIP"}
    )

    def fetch_tradable_us_equities(
        self,
        *,
        include_etfs: bool = True,
        tradable_only: bool = True,
    ) -> list[str]:
        """Fetch symbol list of US equities from assets API; filter tradable and optionally exclude ETFs."""
        assets = self.list_assets(status="active", asset_class="us_equity")
        symbols: list[str] = []
        for a in assets:
            if tradable_only and not a.get("tradable", True):
                continue
            sym = (a.get("symbol") or "").strip()
            if not sym or len(sym) > 10:
                continue
            if not include_etfs and sym in self._COMMON_ETFS:
                continue
            symbols.append(sym)
        return symbols

    def get_asset(self, symbol_or_asset_id: str) -> dict[str, Any] | None:
        """Single asset by symbol or asset ID. May include overnight_tradable, overnight_halted (24/5)."""
        with httpx.Client() as client:
            r = client.get(
                self._url(f"/v2/assets/{symbol_or_asset_id}"),
                headers=self._headers(),
                timeout=10.0,
            )
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()

    @staticmethod
    def is_overnight_tradable(asset: dict[str, Any]) -> bool:
        """True if asset is eligible for 24/5 overnight session (Alpaca overnight_tradable)."""
        return bool(asset.get("overnight_tradable"))

    @staticmethod
    def is_overnight_halted(asset: dict[str, Any]) -> bool:
        """True if an overnight-tradable asset is currently halted in the overnight session."""
        return bool(asset.get("overnight_halted"))

    def get_portfolio_history(
        self,
        *,
        period: str | None = None,
        timeframe: str | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
        extended_hours: bool | None = None,
    ) -> dict[str, Any]:
        """Account equity and P/L time series. period e.g. 1D, 1W, 1M, 1A; timeframe 1Min, 5Min, 15Min, 1H, 1D."""
        with httpx.Client() as client:
            params: dict[str, Any] = {}
            if period:
                params["period"] = period
            if timeframe:
                params["timeframe"] = timeframe
            if date_start:
                params["date_start"] = date_start
            if date_end:
                params["date_end"] = date_end
            if extended_hours is not None:
                params["extended_hours"] = str(extended_hours).lower()
            r = client.get(
                self._url("/v2/account/portfolio/history"),
                params=params or None,
                headers=self._headers(),
                timeout=15.0,
            )
            r.raise_for_status()
            return r.json()

    def get_movers(
        self,
        market_type: str = "stocks",
        top: int = 10,
    ) -> dict[str, Any]:
        """Top market movers (gainers/losers). Data API v1beta1. Stocks reset at market open."""
        if top < 1 or top > 50:
            top = 10
        with httpx.Client() as client:
            r = client.get(
                self._data_url(f"/v1beta1/screener/{market_type}/movers"),
                params={"top": top},
                headers=self._headers(),
                timeout=15.0,
            )
            r.raise_for_status()
            return r.json()

    def get_activities(
        self,
        *,
        activity_types: str | None = None,
        date: str | None = None,
        until: str | None = None,
        after: str | None = None,
        direction: str | None = None,
        page_size: int = 50,
        page_token: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Account activities: fills, cash, fees, dividends, etc. Returns (activities, next_page_token)."""
        with httpx.Client() as client:
            params: dict[str, Any] = {"page_size": page_size}
            if activity_types:
                params["activity_types"] = activity_types
            if date:
                params["date"] = date
            if until:
                params["until"] = until
            if after:
                params["after"] = after
            if direction:
                params["direction"] = direction
            if page_token:
                params["page_token"] = page_token
            r = client.get(
                self._url("/v2/account/activities"),
                params=params,
                headers=self._headers(),
                timeout=15.0,
            )
            r.raise_for_status()
            data = r.json()
        if isinstance(data, list):
            activities, next_token = data, None
        else:
            activities = data.get("activities", []) or []
            next_token = data.get("next_page_token")
        return (activities, next_token)
