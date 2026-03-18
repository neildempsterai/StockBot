"""
E2E: run -> notes -> repeat run -> no duplicate notes.
Uses real Postgres when DATABASE_URL is set; skips otherwise.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import func, select

from stockbot.db.models import MarketIntelNote
from stockbot.db.session import get_session_factory
from stockbot.scrappy.run_service import run_scrappy
from stockbot.scrappy.store import count_notes

pytestmark = pytest.mark.asyncio


@pytest.fixture
def db_available():
    """Skip if DATABASE_URL not set or sqlite (async Postgres required)."""
    url = os.environ.get("DATABASE_URL") or ""
    if not url or "sqlite" in url:
        pytest.skip("DATABASE_URL (Postgres async) required for e2e")
    return True


async def test_run_then_repeat_run_no_duplicate_notes(db_available) -> None:
    """Run Scrappy twice with same scope; second run must not create duplicate notes."""
    factory = get_session_factory()
    _ = db_available
    async with factory() as session:
        count_before = await count_notes(session)

    result1 = await run_scrappy(run_type="symbol", symbols=["AAPL"], themes=[])
    count_after_first = count_before + result1.get("notes_created", 0)

    result2 = await run_scrappy(run_type="symbol", symbols=["AAPL"], themes=[])
    notes_created_second = result2.get("notes_created", 0)

    assert notes_created_second == 0, "Second run must create 0 new notes (all deduped)"

    async with factory() as session:
        count_after_both = await count_notes(session)
    assert count_after_both == count_after_first, "Total note count must not increase on repeat run"

    async with factory() as session:
        r = await session.execute(
            select(MarketIntelNote.dedup_hash).where(MarketIntelNote.dedup_hash.isnot(None))
        )
        hashes = [row for row in r.scalars().all()]
    assert len(hashes) == len(set(hashes)), "All dedup_hash values must be unique"


async def test_idempotent_note_insert_by_dedup_hash(db_available) -> None:
    """Inserting a note with same dedup_hash twice returns same note_id and does not create duplicate row."""
    from stockbot.scrappy.notes import build_note_from_candidate, validate_note_payload
    from stockbot.scrappy.store import insert_market_intel_note

    candidate = {
        "url": "https://example.com/e2e-test-article",
        "source_name": "e2e_test",
        "source_url": "https://example.com/feed",
        "published_at": "2026-03-17T12:00:00Z",
        "title": "E2E test article",
        "summary": "Summary for idempotency test",
        "raw_metadata": {},
    }
    payload = build_note_from_candidate(candidate, "run-e2e-test")
    validate_note_payload(payload)
    dedup_hash = payload["dedup_hash"]

    factory = get_session_factory()
    async with factory() as session:
        nid1 = await insert_market_intel_note(
            session,
            source_name=payload["source_name"],
            source_url=payload["source_url"],
            published_at=payload.get("published_at"),
            title=payload.get("title"),
            summary=payload.get("summary"),
            dedup_hash=dedup_hash,
            content_mode=payload.get("content_mode"),
            scrappy_run_id="run-e2e-test",
        )
        nid2 = await insert_market_intel_note(
            session,
            source_name=payload["source_name"],
            source_url=payload["source_url"],
            published_at=payload.get("published_at"),
            title=payload.get("title"),
            summary=payload.get("summary"),
            dedup_hash=dedup_hash,
            content_mode=payload.get("content_mode"),
            scrappy_run_id="run-e2e-test",
        )
    assert nid1 == nid2, "Same dedup_hash must return same note_id (idempotent insert)"

    async with factory() as session:
        r = await session.execute(
            select(func.count(MarketIntelNote.id)).where(MarketIntelNote.dedup_hash == dedup_hash)
        )
        cnt = r.scalar() or 0
    assert cnt == 1, "Exactly one row per dedup_hash"
