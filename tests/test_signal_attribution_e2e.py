"""
E2E: signal -> shadow trade -> attribution persistence with real DB.
Verifies signals_with_scrappy_snapshot and linked snapshot on signal detail.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.main import app
from stockbot.db.session import get_session_factory
from stockbot.ledger.events import SignalEvent
from stockbot.ledger.store import LedgerStore
from stockbot.scrappy.store import insert_intelligence_snapshot


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
        pytest.skip("DATABASE_URL (Postgres) required")
    if not _db_reachable():
        pytest.skip("Postgres not reachable (start with compose.test.yaml)")
    return True


@pytest.fixture
def client():
    return TestClient(app)


async def test_signal_with_snapshot_shows_in_metrics(requires_db, client: TestClient) -> None:
    factory = get_session_factory()
    snap_id = None
    async with factory() as session:
        snap_id = await insert_intelligence_snapshot(
            session, "ATTRIB", datetime.now(timezone.utc), 30,
            "positive", 50, sentiment_label="positive",
            evidence_count=1, source_count=1,
        )
    sig_uuid = uuid4()
    async with factory() as session:
        store = LedgerStore(session)
        await store.insert_signal(SignalEvent(
            signal_uuid=sig_uuid,
            symbol="ATTRIB",
            side="buy",
            qty=Decimal("100"),
            strategy_id="INTRA_EVENT_MOMO",
            strategy_version="0.1.0",
            feed="iex",
            quote_ts=datetime.now(timezone.utc),
            ingest_ts=datetime.now(timezone.utc),
            bid=Decimal("200"),
            ask=Decimal("200.5"),
            last=Decimal("200"),
            spread_bps=25,
            latency_ms=None,
            reason_codes=["scrappy_positive"],
            intelligence_snapshot_id=snap_id,
        ))
    r = client.get("/v1/metrics/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["signals_with_scrappy_snapshot"] >= 1
    r2 = client.get(f"/v1/signals/{sig_uuid}")
    assert r2.status_code == 200
    assert r2.json().get("intelligence_snapshot_id") == snap_id
    assert "intelligence_snapshot" in r2.json()


async def test_shadow_trade_and_signal_list(requires_db, client: TestClient) -> None:
    r = client.get("/v1/signals?limit=10")
    assert r.status_code == 200
    assert "signals" in r.json()
    assert "count" in r.json()
    r2 = client.get("/v1/shadow/trades?limit=10")
    assert r2.status_code == 200
    assert "trades" in r2.json()
