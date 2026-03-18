"""
E2E: Scrappy gating and attribution with real DB (and optional Redis).
Tests scrappy_gate_check logic and rejection/snapshot persistence.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from worker.main import scrappy_gate_check


def _mock_snapshot(catalyst_direction: str, stale_flag: bool = False, conflict_flag: bool = False):
    m = MagicMock()
    m.catalyst_direction = catalyst_direction
    m.stale_flag = stale_flag
    m.conflict_flag = conflict_flag
    return m


# --- scrappy_gate_check (no DB/Redis) ---


def test_gate_off_allows_any():
    assert scrappy_gate_check(None, "buy", "off") is None
    assert scrappy_gate_check(_mock_snapshot("negative"), "buy", "off") is None


def test_gate_required_rejects_missing():
    assert scrappy_gate_check(None, "buy", "required") == "scrappy_missing"
    assert scrappy_gate_check(None, "sell", "required") == "scrappy_missing"


def test_gate_advisory_allows_when_no_snapshot():
    assert scrappy_gate_check(None, "buy", "advisory") is None
    assert scrappy_gate_check(None, "sell", "advisory") is None


def test_gate_rejects_long_when_negative():
    snap = _mock_snapshot("negative")
    assert scrappy_gate_check(snap, "buy", "advisory") == "scrappy_negative"
    assert scrappy_gate_check(snap, "sell", "advisory") is None


def test_gate_rejects_short_when_positive():
    snap = _mock_snapshot("positive")
    assert scrappy_gate_check(snap, "sell", "advisory") == "scrappy_positive"
    assert scrappy_gate_check(snap, "buy", "advisory") is None


def test_gate_rejects_stale():
    snap = _mock_snapshot("neutral", stale_flag=True)
    assert scrappy_gate_check(snap, "buy", "advisory") == "scrappy_stale"
    assert scrappy_gate_check(snap, "sell", "advisory") == "scrappy_stale"


def test_gate_rejects_conflict():
    snap = _mock_snapshot("conflicting", conflict_flag=True)
    assert scrappy_gate_check(snap, "buy", "advisory") == "scrappy_conflict"
    assert scrappy_gate_check(snap, "sell", "advisory") == "scrappy_conflict"


def test_gate_allows_positive_for_long():
    snap = _mock_snapshot("positive")
    assert scrappy_gate_check(snap, "buy", "advisory") is None


def test_gate_allows_negative_for_short():
    snap = _mock_snapshot("negative")
    assert scrappy_gate_check(snap, "sell", "advisory") is None


def test_gate_allows_neutral_for_both():
    snap = _mock_snapshot("neutral")
    assert scrappy_gate_check(snap, "buy", "advisory") is None
    assert scrappy_gate_check(snap, "sell", "advisory") is None


# --- DB-backed: rejection accounting (requires Postgres) ---


@pytest.fixture
def requires_db():
    url = os.environ.get("DATABASE_URL") or ""
    if not url or "sqlite" in url:
        pytest.skip("DATABASE_URL (Postgres) required")
    if not _db_reachable():
        pytest.skip("Postgres not reachable (start with compose.test.yaml)")
    return True


def _db_reachable() -> bool:
    try:
        import asyncio

        from sqlalchemy import text

        from stockbot.db.session import get_session_factory
        async def _check():
            factory = get_session_factory()
            async with factory() as session:
                await session.execute(text("SELECT 1"))
        asyncio.run(_check())
        return True
    except Exception:
        return False


@pytest.mark.asyncio
async def test_rejection_persisted_and_counted(requires_db) -> None:
    from stockbot.db.session import get_session_factory
    from stockbot.scrappy.store import get_gate_rejection_counts, insert_gate_rejection
    factory = get_session_factory()
    async with factory() as session:
        await insert_gate_rejection(session, "E2E", "scrappy_negative")
    async with factory() as session:
        counts = await get_gate_rejection_counts(session)
    assert "scrappy_negative" in counts
    assert counts["scrappy_negative"] >= 1


@pytest.mark.asyncio
async def test_snapshot_persisted_and_retrievable(requires_db) -> None:
    from tests.helpers.replay import create_snapshot_in_db

    from stockbot.db.session import get_session_factory
    from stockbot.scrappy.store import get_latest_snapshot_by_symbol

    factory = get_session_factory()
    async with factory() as session:
        sid = await create_snapshot_in_db(session, "AAPL", "positive", stale_flag=False)
    assert sid > 0
    async with factory() as session:
        row = await get_latest_snapshot_by_symbol(session, "AAPL")
    assert row is not None
    assert row.catalyst_direction == "positive"
    assert row.symbol == "AAPL"


@pytest.mark.asyncio
async def test_rejection_counts_match_db(requires_db) -> None:
    from stockbot.db.session import get_session_factory
    from stockbot.scrappy.store import get_gate_rejection_counts, insert_gate_rejection
    factory = get_session_factory()
    async with factory() as session:
        await insert_gate_rejection(session, "R1", "scrappy_conflict")
        await insert_gate_rejection(session, "R1", "scrappy_conflict")
    async with factory() as session:
        counts = await get_gate_rejection_counts(session)
    assert counts.get("scrappy_conflict", 0) >= 2
