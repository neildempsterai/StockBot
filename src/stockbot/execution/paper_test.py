"""
Operator paper execution test: buy-open, sell-close, short-open, buy-cover, flatten-all, cancel-all.
Uses Alpaca account/position/asset truth; validates before submit; persists PaperOrder with origin=intent.
For operator validation only; not strategy authority.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import or_, select

from stockbot.alpaca.client import AlpacaClient
from stockbot.db.models import PaperOrder, PaperOrderEvent
from stockbot.db.session import get_session_factory
from stockbot.execution.validation import (
    validate_buy_cover,
    validate_buy_open,
    validate_sell_close,
    validate_short_open,
)

ORDER_ORIGIN_OPERATOR_TEST = "operator_test"
INTENT_BUY_OPEN = "buy_open"
INTENT_SELL_CLOSE = "sell_close"
INTENT_SHORT_OPEN = "short_open"
INTENT_BUY_COVER = "buy_cover"
INTENT_FLATTEN = "flatten"

CLIENT_ORDER_ID_PREFIX = "paper_test_"


def _decimal(v: float | Decimal | None) -> Decimal:
    if v is None:
        return Decimal("0")
    return Decimal(str(v))


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


async def _persist_paper_order(
    order_id: str,
    client_order_id: str,
    symbol: str,
    side: str,
    qty: Decimal,
    order_type: str,
    time_in_force: str,
    limit_price: Decimal | None,
    order_origin: str,
    order_intent: str,
    note: str | None,
    raw_order: dict,
) -> None:
    """Persist PaperOrder after Alpaca accept (so trade_updates can update it)."""
    submitted_at = _parse_ts(raw_order.get("submitted_at")) or datetime.now(UTC)
    updated_at = _parse_ts(raw_order.get("updated_at")) or datetime.now(UTC)
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(PaperOrder).where(PaperOrder.order_id == order_id).limit(1))
        if result.scalars().first():
            return
        session.add(PaperOrder(
            order_id=order_id,
            client_order_id=client_order_id,
            signal_uuid=None,
            submitted_at=submitted_at,
            updated_at=updated_at,
            symbol=symbol,
            side=side,
            qty=qty,
            notional=raw_order.get("notional") and _decimal(raw_order.get("notional")),
            order_type=order_type,
            time_in_force=time_in_force,
            limit_price=limit_price,
            stop_price=None,
            status=raw_order.get("status"),
            filled_qty=raw_order.get("filled_qty") and _decimal(raw_order.get("filled_qty")),
            filled_avg_price=raw_order.get("filled_avg_price") and _decimal(raw_order.get("filled_avg_price")),
            raw_json=raw_order,
            order_origin=order_origin,
            order_intent=order_intent,
            note=note,
        ))
        session.add(PaperOrderEvent(
            order_id=order_id,
            client_order_id=client_order_id,
            event_ts=datetime.now(UTC),
            event_type="new",
            qty=qty,
            price=limit_price,
            raw_json=raw_order,
        ))
        await session.commit()


async def run_buy_open(
    symbol: str,
    qty: float | Decimal,
    order_type: str = "market",
    limit_price: float | Decimal | None = None,
    extended_hours: bool = False,
    note: str | None = None,
) -> dict:
    """Execute buy-open (BUY to open long). Returns response shape for API."""
    import asyncio
    client = AlpacaClient()
    account = await asyncio.to_thread(client.get_account)
    asset = await asyncio.to_thread(client.get_asset, symbol)
    qty_d = _decimal(qty)
    val = validate_buy_open(
        account=account,
        asset=asset,
        qty=qty_d,
        order_type=order_type or "market",
        extended_hours=extended_hours,
        limit_price=_decimal(limit_price) if limit_price is not None else None,
    )
    if not val.allowed:
        return {
            "accepted": False,
            "reason": val.reason_code,
            "message": val.message,
            "order_id": None,
            "client_order_id": None,
            "side": "buy",
            "symbol": symbol,
            "qty": float(qty_d),
            "mode": "paper_test",
            "intent": INTENT_BUY_OPEN,
        }
    tif = "day"
    ot = (order_type or "market").lower()
    if extended_hours:
        ot = "limit"
        tif = "day"
    limit = float(limit_price) if limit_price is not None else None
    client_order_id = f"{CLIENT_ORDER_ID_PREFIX}{INTENT_BUY_OPEN}_{uuid4().hex[:12]}"
    try:
        order = await asyncio.to_thread(
            client.create_order,
            symbol, float(qty_d), "buy",
            client_order_id=client_order_id,
            time_in_force=tif,
            order_type=ot,
            limit_price=limit,
            extended_hours=extended_hours,
        )
    except Exception as e:
        return {
            "accepted": False,
            "reason": "validation_error",
            "message": str(e)[:300],
            "order_id": None,
            "client_order_id": client_order_id,
            "side": "buy",
            "symbol": symbol,
            "qty": float(qty_d),
            "mode": "paper_test",
            "intent": INTENT_BUY_OPEN,
        }
    await _persist_paper_order(
        order_id=str(order["id"]),
        client_order_id=client_order_id,
        symbol=symbol,
        side="buy",
        qty=qty_d,
        order_type=ot,
        time_in_force=tif,
        limit_price=_decimal(limit) if limit is not None else None,
        order_origin=ORDER_ORIGIN_OPERATOR_TEST,
        order_intent=INTENT_BUY_OPEN,
        note=note,
        raw_order=order,
    )
    return {
        "accepted": True,
        "reason": None,
        "order_id": str(order["id"]),
        "client_order_id": client_order_id,
        "side": "buy",
        "symbol": symbol,
        "qty": float(qty_d),
        "mode": "paper_test",
        "intent": INTENT_BUY_OPEN,
    }


async def run_sell_close(
    symbol: str,
    qty: float | Decimal,
    order_type: str = "market",
    limit_price: float | Decimal | None = None,
    extended_hours: bool = False,
    note: str | None = None,
) -> dict:
    """Execute sell-close (SELL to close long)."""
    import asyncio
    client = AlpacaClient()
    account = await asyncio.to_thread(client.get_account)
    position = await asyncio.to_thread(client.get_position, symbol)
    qty_d = _decimal(qty)
    val = validate_sell_close(
        account=account,
        position=position,
        qty=qty_d,
        order_type=order_type or "market",
        extended_hours=extended_hours,
        limit_price=_decimal(limit_price) if limit_price is not None else None,
    )
    if not val.allowed:
        return {
            "accepted": False,
            "reason": val.reason_code,
            "message": val.message,
            "order_id": None,
            "client_order_id": None,
            "side": "sell",
            "symbol": symbol,
            "qty": float(qty_d),
            "mode": "paper_test",
            "intent": INTENT_SELL_CLOSE,
        }
    tif = "day"
    ot = (order_type or "market").lower()
    if extended_hours:
        ot = "limit"
        tif = "day"
    limit = float(limit_price) if limit_price is not None else None
    client_order_id = f"{CLIENT_ORDER_ID_PREFIX}{INTENT_SELL_CLOSE}_{uuid4().hex[:12]}"
    try:
        order = await asyncio.to_thread(
            client.create_order,
            symbol, float(qty_d), "sell",
            client_order_id=client_order_id,
            time_in_force=tif,
            order_type=ot,
            limit_price=limit,
            extended_hours=extended_hours,
        )
    except Exception as e:
        return {
            "accepted": False,
            "reason": "validation_error",
            "message": str(e)[:300],
            "order_id": None,
            "client_order_id": client_order_id,
            "side": "sell",
            "symbol": symbol,
            "qty": float(qty_d),
            "mode": "paper_test",
            "intent": INTENT_SELL_CLOSE,
        }
    await _persist_paper_order(
        order_id=str(order["id"]),
        client_order_id=client_order_id,
        symbol=symbol,
        side="sell",
        qty=qty_d,
        order_type=ot,
        time_in_force=tif,
        limit_price=_decimal(limit) if limit is not None else None,
        order_origin=ORDER_ORIGIN_OPERATOR_TEST,
        order_intent=INTENT_SELL_CLOSE,
        note=note,
        raw_order=order,
    )
    return {
        "accepted": True,
        "reason": None,
        "order_id": str(order["id"]),
        "client_order_id": client_order_id,
        "side": "sell",
        "symbol": symbol,
        "qty": float(qty_d),
        "mode": "paper_test",
        "intent": INTENT_SELL_CLOSE,
    }


async def run_short_open(
    symbol: str,
    qty: float | Decimal,
    order_type: str = "market",
    limit_price: float | Decimal | None = None,
    extended_hours: bool = False,
    note: str | None = None,
) -> dict:
    """Execute short-open (SELL to open short)."""
    import asyncio
    client = AlpacaClient()
    account = await asyncio.to_thread(client.get_account)
    asset = await asyncio.to_thread(client.get_asset, symbol)
    qty_d = _decimal(qty)
    val = validate_short_open(
        account=account,
        asset=asset,
        qty=qty_d,
        order_type=order_type or "market",
        extended_hours=extended_hours,
        limit_price=_decimal(limit_price) if limit_price is not None else None,
    )
    if not val.allowed:
        return {
            "accepted": False,
            "reason": val.reason_code,
            "message": val.message,
            "order_id": None,
            "client_order_id": None,
            "side": "sell",
            "symbol": symbol,
            "qty": float(qty_d),
            "mode": "paper_test",
            "intent": INTENT_SHORT_OPEN,
        }
    tif = "day"
    ot = (order_type or "market").lower()
    if extended_hours:
        ot = "limit"
        tif = "day"
    limit = float(limit_price) if limit_price is not None else None
    client_order_id = f"{CLIENT_ORDER_ID_PREFIX}{INTENT_SHORT_OPEN}_{uuid4().hex[:12]}"
    try:
        order = await asyncio.to_thread(
            client.create_order,
            symbol, float(qty_d), "sell",
            client_order_id=client_order_id,
            time_in_force=tif,
            order_type=ot,
            limit_price=limit,
            extended_hours=extended_hours,
        )
    except Exception as e:
        return {
            "accepted": False,
            "reason": "validation_error",
            "message": str(e)[:300],
            "order_id": None,
            "client_order_id": client_order_id,
            "side": "sell",
            "symbol": symbol,
            "qty": float(qty_d),
            "mode": "paper_test",
            "intent": INTENT_SHORT_OPEN,
        }
    await _persist_paper_order(
        order_id=str(order["id"]),
        client_order_id=client_order_id,
        symbol=symbol,
        side="sell",
        qty=qty_d,
        order_type=ot,
        time_in_force=tif,
        limit_price=_decimal(limit) if limit is not None else None,
        order_origin=ORDER_ORIGIN_OPERATOR_TEST,
        order_intent=INTENT_SHORT_OPEN,
        note=note,
        raw_order=order,
    )
    return {
        "accepted": True,
        "reason": None,
        "order_id": str(order["id"]),
        "client_order_id": client_order_id,
        "side": "sell",
        "symbol": symbol,
        "qty": float(qty_d),
        "mode": "paper_test",
        "intent": INTENT_SHORT_OPEN,
    }


async def run_buy_cover(
    symbol: str,
    qty: float | Decimal,
    order_type: str = "market",
    limit_price: float | Decimal | None = None,
    extended_hours: bool = False,
    note: str | None = None,
) -> dict:
    """Execute buy-cover (BUY to cover short)."""
    import asyncio
    client = AlpacaClient()
    account = await asyncio.to_thread(client.get_account)
    position = await asyncio.to_thread(client.get_position, symbol)
    qty_d = _decimal(qty)
    val = validate_buy_cover(
        account=account,
        position=position,
        qty=qty_d,
        order_type=order_type or "market",
        extended_hours=extended_hours,
        limit_price=_decimal(limit_price) if limit_price is not None else None,
    )
    if not val.allowed:
        return {
            "accepted": False,
            "reason": val.reason_code,
            "message": val.message,
            "order_id": None,
            "client_order_id": None,
            "side": "buy",
            "symbol": symbol,
            "qty": float(qty_d),
            "mode": "paper_test",
            "intent": INTENT_BUY_COVER,
        }
    tif = "day"
    ot = (order_type or "market").lower()
    if extended_hours:
        ot = "limit"
        tif = "day"
    limit = float(limit_price) if limit_price is not None else None
    client_order_id = f"{CLIENT_ORDER_ID_PREFIX}{INTENT_BUY_COVER}_{uuid4().hex[:12]}"
    try:
        order = await asyncio.to_thread(
            client.create_order,
            symbol, float(qty_d), "buy",
            client_order_id=client_order_id,
            time_in_force=tif,
            order_type=ot,
            limit_price=limit,
            extended_hours=extended_hours,
        )
    except Exception as e:
        return {
            "accepted": False,
            "reason": "validation_error",
            "message": str(e)[:300],
            "order_id": None,
            "client_order_id": client_order_id,
            "side": "buy",
            "symbol": symbol,
            "qty": float(qty_d),
            "mode": "paper_test",
            "intent": INTENT_BUY_COVER,
        }
    await _persist_paper_order(
        order_id=str(order["id"]),
        client_order_id=client_order_id,
        symbol=symbol,
        side="buy",
        qty=qty_d,
        order_type=ot,
        time_in_force=tif,
        limit_price=_decimal(limit) if limit is not None else None,
        order_origin=ORDER_ORIGIN_OPERATOR_TEST,
        order_intent=INTENT_BUY_COVER,
        note=note,
        raw_order=order,
    )
    return {
        "accepted": True,
        "reason": None,
        "order_id": str(order["id"]),
        "client_order_id": client_order_id,
        "side": "buy",
        "symbol": symbol,
        "qty": float(qty_d),
        "mode": "paper_test",
        "intent": INTENT_BUY_COVER,
    }


async def run_flatten_all(note: str | None = None) -> dict:
    """Submit market close orders for all positions. Returns summary."""
    import asyncio
    from stockbot.config import get_settings
    settings = get_settings()
    if not getattr(settings, "paper_execution_enabled", False):
        return {
            "accepted": False,
            "reason": "paper_disabled",
            "message": "Paper execution is disabled",
            "orders_submitted": 0,
            "mode": "paper_test",
            "intent": INTENT_FLATTEN,
        }
    client = AlpacaClient()
    account = await asyncio.to_thread(client.get_account)
    if account.get("trading_blocked") or account.get("account_blocked"):
        return {
            "accepted": False,
            "reason": "account_not_tradable",
            "message": "Account is not tradable",
            "orders_submitted": 0,
            "mode": "paper_test",
            "intent": INTENT_FLATTEN,
        }
    positions = await asyncio.to_thread(client.list_positions)
    orders_submitted = 0
    for p in positions:
        qty_val = p.get("qty")
        if qty_val is None:
            continue
        try:
            qty_float = float(qty_val)
        except (TypeError, ValueError):
            continue
        if qty_float == 0:
            continue
        sym = p.get("symbol") or ""
        if not sym:
            continue
        side = "sell" if qty_float > 0 else "buy"
        close_qty = abs(qty_float)
        client_order_id = f"{CLIENT_ORDER_ID_PREFIX}{INTENT_FLATTEN}_{uuid4().hex[:12]}"
        try:
            order = await asyncio.to_thread(
                client.create_order,
                sym, close_qty, side,
                client_order_id=client_order_id,
                time_in_force="day",
                order_type="market",
            )
            orders_submitted += 1
            await _persist_paper_order(
                order_id=str(order["id"]),
                client_order_id=client_order_id,
                symbol=sym,
                side=side,
                qty=Decimal(str(close_qty)),
                order_type="market",
                time_in_force="day",
                limit_price=None,
                order_origin=ORDER_ORIGIN_OPERATOR_TEST,
                order_intent=INTENT_FLATTEN,
                note=note,
                raw_order=order,
            )
        except Exception:
            pass
    return {
        "accepted": True,
        "reason": None,
        "orders_submitted": orders_submitted,
        "mode": "paper_test",
        "intent": INTENT_FLATTEN,
    }


async def run_cancel_all() -> dict:
    """Cancel all open orders. Returns count cancelled."""
    import asyncio
    client = AlpacaClient()
    cancelled = await asyncio.to_thread(client.cancel_all_orders)
    return {
        "accepted": True,
        "cancelled_count": len(cancelled),
        "mode": "paper_test",
    }


async def get_paper_test_status() -> dict:
    """Status for operator: paper enabled, state, account tradable, buying power, positions, recent test orders, warnings.
    state: paper_disabled | credentials_missing | broker_unavailable | broker_connected_no_proof | proof_partial | proof_complete.
    No fake success."""
    import asyncio
    from datetime import timedelta
    from stockbot.config import get_settings
    from sqlalchemy import func
    settings = get_settings()
    warnings: list[str] = []
    paper_enabled = getattr(settings, "paper_execution_enabled", False)
    credentials_configured = bool(
        getattr(settings, "alpaca_api_key_id", None) and getattr(settings, "alpaca_api_secret_key", None)
    )
    account_tradable = None
    buying_power = None
    equity = None
    long_count = 0
    short_count = 0
    recent_operator_test_count = 0
    last_trade_update_ts = None
    broker_reachable = False
    intents_with_proof = 0

    if not paper_enabled:
        state = "paper_disabled"
    elif not credentials_configured:
        state = "credentials_missing"
    else:
        try:
            client = AlpacaClient()
            account = await asyncio.to_thread(client.get_account)
            broker_reachable = True
            account_tradable = not (account.get("trading_blocked") or account.get("account_blocked"))
            buying_power = float(account.get("buying_power") or 0)
            equity = float(account.get("equity") or 0)
            positions = await asyncio.to_thread(client.list_positions)
            for p in positions:
                qty = float(p.get("qty") or 0)
                if qty > 0:
                    long_count += 1
                elif qty < 0:
                    short_count += 1
            if account.get("pattern_day_trader"):
                warnings.append("Account is flagged as pattern day trader; daytrading buying power may apply.")
        except Exception as e:
            warnings.append(f"Alpaca fetch failed: {str(e)[:150]}")
            state = "broker_unavailable"

        if broker_reachable:
            try:
                factory = get_session_factory()
                async with factory() as session:
                    since = datetime.now(UTC) - timedelta(hours=24)
                    result = await session.execute(
                        select(func.count(PaperOrder.id)).where(
                            PaperOrder.order_origin == "operator_test",
                            or_(
                                PaperOrder.submitted_at >= since,
                                PaperOrder.updated_at >= since,
                            ),
                        )
                    )
                    recent_operator_test_count = result.scalar() or 0
                    result2 = await session.execute(
                        select(func.max(PaperOrderEvent.event_ts)).where(
                            PaperOrderEvent.client_order_id.like("paper_test_%")
                        )
                    )
                    ts = result2.scalar()
                    if ts:
                        last_trade_update_ts = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
                    # Count intents that have at least one operator_test order
                    result3 = await session.execute(
                        select(PaperOrder.order_intent).where(
                            PaperOrder.order_origin == "operator_test",
                            PaperOrder.order_intent.in_(
                                (INTENT_BUY_OPEN, INTENT_SELL_CLOSE, INTENT_SHORT_OPEN, INTENT_BUY_COVER)
                            ),
                        ).distinct()
                    )
                    intents_with_proof = len(result3.scalars().all())
            except Exception as e:
                warnings.append(f"DB query failed: {str(e)[:150]}")

            if state != "broker_unavailable":
                if intents_with_proof >= 4:
                    state = "proof_complete"
                elif intents_with_proof > 0:
                    state = "proof_partial"
                else:
                    state = "broker_connected_no_proof"

    return {
        "state": state,
        "paper_execution_enabled": paper_enabled,
        "credentials_configured": credentials_configured,
        "broker_reachable": broker_reachable if credentials_configured else None,
        "account_tradable": account_tradable,
        "buying_power": buying_power,
        "equity": equity,
        "current_long_positions_count": long_count,
        "current_short_positions_count": short_count,
        "recent_operator_test_orders_count": recent_operator_test_count,
        "intents_with_proof": intents_with_proof if broker_reachable else None,
        "last_trade_update_ts": last_trade_update_ts,
        "warnings": warnings,
    }
