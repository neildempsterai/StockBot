"""
Session classification and clock helpers for US equities (NYSE/NASDAQ).
Aligns with Alpaca 24/5 trading sessions. Used by scanner, opportunity engine, and execution.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

SessionLabel = Literal["overnight", "premarket", "regular", "afterhours", "closed"]

# Alpaca 24/5 session boundaries (ET): overnight 8PM–4AM, premarket 4AM–9:30AM, regular 9:30AM–4PM, afterhours 4PM–8PM.
# Overnight is a tradable session when 24/5 (BOATS) is enabled; only limit orders, day TIF.
# Weekend: closed. Overnight follows NYSE holiday calendar.


def _et_now() -> datetime:
    try:
        import zoneinfo
        return datetime.now(UTC).astimezone(zoneinfo.ZoneInfo("America/New_York"))
    except Exception:
        return datetime.now(UTC)


def current_session() -> SessionLabel:
    """
    Classify current time into session for US equities (Alpaca 24/5).
    - overnight: 20:00–04:00 ET (tradable when 24/5 enabled; limit orders only)
    - premarket: 04:00–09:30 ET
    - regular: 09:30–16:00 ET
    - afterhours: 16:00–20:00 ET
    - closed: weekend (no overnight session)
    """
    et = _et_now()
    h, m = et.hour, et.minute
    # Weekend: closed
    if et.weekday() >= 5:
        return "closed"
    # 04:00–09:30 premarket
    if h < 9 or (h == 9 and m < 30):
        if h >= 4:
            return "premarket"
        return "overnight"
    # 09:30–16:00 regular
    if h < 16:
        return "regular"
    # 16:00–20:00 afterhours
    if h < 20:
        return "afterhours"
    # 20:00–04:00 overnight (24/5 tradable session)
    return "overnight"


def is_premarket() -> bool:
    et = _et_now()
    if et.weekday() >= 5:
        return False
    return et.hour < 9 or (et.hour == 9 and et.minute < 30)


def is_regular_hours() -> bool:
    et = _et_now()
    if et.weekday() >= 5:
        return False
    return (9, 30) <= (et.hour, et.minute) < (16, 0)


def is_after_hours() -> bool:
    et = _et_now()
    if et.weekday() >= 5:
        return False
    return (16, 0) <= (et.hour, et.minute) < (20, 0)


def is_overnight_or_closed() -> bool:
    s = current_session()
    return s in ("overnight", "closed")


def is_overnight_session() -> bool:
    """True during 20:00–04:00 ET (24/5 overnight / BOATS). When True, only limit orders are supported."""
    return current_session() == "overnight"


def session_allows_scanner(session: SessionLabel, premarket_ok: bool, regular_ok: bool, afterhours_ok: bool, overnight_ok: bool) -> bool:
    if session == "premarket":
        return premarket_ok
    if session == "regular":
        return regular_ok
    if session == "afterhours":
        return afterhours_ok
    if session in ("overnight", "closed"):
        return overnight_ok
    return False
