"""Shadow engine: ideal/realistic fill math, exit precedence."""
from __future__ import annotations

from datetime import UTC
from decimal import Decimal
from uuid import uuid4

from stockbot.shadow.engine import (
    ShadowPosition,
    close_shadow_position,
    ideal_entry_price,
    ideal_exit_price,
    realistic_entry_price,
    resolve_exit_conservative,
)


def test_ideal_fill_math() -> None:
    bid = Decimal("100")
    ask = Decimal("100.05")
    assert ideal_entry_price("buy", bid, ask) == ask
    assert ideal_entry_price("sell", bid, ask) == bid
    assert ideal_exit_price("buy", bid, ask) == bid
    assert ideal_exit_price("sell", bid, ask) == ask


def test_realistic_fill_math() -> None:
    bid = Decimal("100")
    ask = Decimal("100.05")
    slip = 5
    # buy: ask * (1 + 5/10000) = ask * 1.0005
    r_buy = realistic_entry_price("buy", bid, ask, slip)
    assert r_buy > ask
    # sell: bid * (1 - 5/10000)
    r_sell = realistic_entry_price("sell", bid, ask, slip)
    assert r_sell < bid


def test_conservative_intrabar_stop_before_target_long() -> None:
    # Long: stop = or_low, target above. Bar touches both -> assume stop hits first
    exit_price, reason = resolve_exit_conservative(
        "buy",
        bar_high=Decimal("110"),
        bar_low=Decimal("95"),
        stop_price=Decimal("98"),
        target_price=Decimal("108"),
    )
    assert reason == "stop"
    assert exit_price == Decimal("98")


def test_conservative_intrabar_stop_before_target_short() -> None:
    exit_price, reason = resolve_exit_conservative(
        "sell",
        bar_high=Decimal("102"),
        bar_low=Decimal("90"),
        stop_price=Decimal("100"),
        target_price=Decimal("92"),
    )
    assert reason == "stop"
    assert exit_price == Decimal("100")


def test_close_shadow_position_returns_two_records() -> None:
    from datetime import datetime
    pos = ShadowPosition(
        signal_uuid=uuid4(),
        symbol="AAPL",
        side="buy",
        qty=Decimal("100"),
        entry_ts=datetime.now(UTC),
        ideal_entry_price=Decimal("100"),
        realistic_entry_price=Decimal("100.05"),
        stop_price=Decimal("98"),
        target_price=Decimal("104"),
        slippage_bps=5,
        fee_per_share=Decimal("0"),
    )
    exit_ts = datetime.now(UTC)
    records = close_shadow_position(pos, exit_ts, Decimal("104"), Decimal("103.95"), "target")
    assert len(records) == 2
    modes = {r["execution_mode"] for r in records}
    assert modes == {"ideal", "realistic"}
    ideal_rec = next(r for r in records if r["execution_mode"] == "ideal")
    assert ideal_rec["entry_price"] == Decimal("100")
    assert ideal_rec["exit_price"] == Decimal("104")
