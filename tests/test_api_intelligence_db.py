"""
API intelligence and metrics endpoints with real DB.
Requires DATABASE_URL (Postgres); skips when unavailable.
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.main import app
from stockbot.db.session import get_session_factory
from stockbot.ledger.events import SignalEvent
from stockbot.ledger.store import LedgerStore
from stockbot.scrappy.store import (
    get_gate_rejection_counts,
    get_latest_snapshot_by_symbol,
    get_recent_snapshots,
    insert_gate_rejection,
    insert_intelligence_snapshot,
)
from decimal import Decimal
from datetime import datetime, timezone


pytestmark = pytest.mark.asyncio


def _db_reachable() -> bool:
    try:
        import asyncio
        from stockbot.db.session import get_session_factory
        from sqlalchemy import text
        async def _check():
            factory = get_session_factory()
            async with factory() as session:
                await session.execute(text("SELECT 1"))
        asyncio.run(_check())
        return True
    except Exception:
        return False


@pytest.fixture
def requires_db():
    url = os.environ.get("DATABASE_URL") or ""
    if not url or "sqlite" in url:
        pytest.skip("DATABASE_URL (Postgres) required for API DB tests")
    if not _db_reachable():
        pytest.skip("Postgres not reachable (start with compose.test.yaml)")
    return True


@pytest.fixture
def client():
    return TestClient(app)


async def test_intelligence_latest_returns_snapshot_when_exists(requires_db, client: TestClient) -> None:
    factory = get_session_factory()
    async with factory() as session:
        await insert_intelligence_snapshot(
            session, "TEST", datetime.now(timezone.utc), 30,
            "positive", 50, sentiment_label="positive",
            evidence_count=1, source_count=1,
        )
    r = client.get("/v1/intelligence/latest?symbol=TEST")
    assert r.status_code == 200
    data = r.json()
    assert data.get("symbol") == "TEST"
    assert data.get("catalyst_direction") == "positive"


async def test_intelligence_recent_with_db(requires_db, client: TestClient) -> None:
    r = client.get("/v1/intelligence/recent?limit=5")
    assert r.status_code == 200
    data = r.json()
    assert "snapshots" in data
    assert "count" in data
    assert isinstance(data["snapshots"], list)


async def test_intelligence_summary_with_db(requires_db, client: TestClient) -> None:
    r = client.get("/v1/intelligence/summary")
    assert r.status_code == 200
    data = r.json()
    assert "snapshots_total" in data
    assert "symbols_with_snapshot" in data
    assert "by_symbol" in data


async def test_metrics_summary_attribution_keys(requires_db, client: TestClient) -> None:
    r = client.get("/v1/metrics/summary")
    assert r.status_code == 200
    data = r.json()
    assert "signals_total" in data
    assert "signals_with_scrappy_snapshot" in data
    assert "signals_without_scrappy_snapshot" in data
    assert "scrappy_gate_rejections" in data
    assert isinstance(data["scrappy_gate_rejections"], dict)


async def test_metrics_rejection_counts_match_db(requires_db, client: TestClient) -> None:
    factory = get_session_factory()
    async with factory() as session:
        await insert_gate_rejection(session, "CNT", "scrappy_stale")
    r = client.get("/v1/metrics/summary")
    assert r.status_code == 200
    counts = r.json().get("scrappy_gate_rejections") or {}
    async with factory() as session:
        db_counts = await get_gate_rejection_counts(session)
    for k, v in db_counts.items():
        assert counts.get(k) == v, f"scrappy_gate_rejections[{k}] should match DB count"


async def test_signal_detail_includes_intelligence_snapshot_when_linked(requires_db, client: TestClient) -> None:
    factory = get_session_factory()
    snap_id = None
    async with factory() as session:
        snap_id = await insert_intelligence_snapshot(
            session, "LINK", datetime.now(timezone.utc), 30,
            "neutral", 25, sentiment_label="neutral",
            evidence_count=0, source_count=0,
        )
    sig_uuid = uuid4()
    async with factory() as session:
        store = LedgerStore(session)
        await store.insert_signal(SignalEvent(
            signal_uuid=sig_uuid,
            symbol="LINK",
            side="buy",
            qty=Decimal("100"),
            strategy_id="INTRA_EVENT_MOMO",
            strategy_version="0.1.0",
            feed="iex",
            quote_ts=datetime.now(timezone.utc),
            ingest_ts=datetime.now(timezone.utc),
            bid=Decimal("100"),
            ask=Decimal("100.5"),
            last=Decimal("100"),
            spread_bps=50,
            latency_ms=None,
            reason_codes=["scrappy_neutral"],
            intelligence_snapshot_id=snap_id,
        ))
    r = client.get(f"/v1/signals/{sig_uuid}")
    assert r.status_code == 200
    data = r.json()
    assert data.get("intelligence_snapshot_id") == snap_id
    assert "intelligence_snapshot" in data
    assert data["intelligence_snapshot"].get("symbol") == "LINK"
