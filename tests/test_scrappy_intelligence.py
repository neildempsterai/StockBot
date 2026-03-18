"""Tests for Scrappy intelligence snapshot: build from notes, stale/conflict flags."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from stockbot.scrappy.snapshot import build_snapshot_from_notes
from stockbot.scrappy.types import (
    CATALYST_DIRECTION_CONFLICTING,
    CATALYST_DIRECTION_NEGATIVE,
    CATALYST_DIRECTION_NEUTRAL,
    CATALYST_DIRECTION_POSITIVE,
)


def _note(sentiment: str, source_name: str = "test", title: str = ""):
    n = MagicMock()
    n.sentiment_label = sentiment
    n.source_name = source_name
    n.title = title
    n.source_url = "https://example.com/1"
    n.created_at = datetime.now(UTC)
    return n


def test_build_snapshot_empty_notes():
    snap = build_snapshot_from_notes("AAPL", [])
    assert snap.symbol == "AAPL"
    assert snap.catalyst_direction == CATALYST_DIRECTION_NEUTRAL
    assert snap.catalyst_strength == 0
    assert snap.stale_flag is True
    assert snap.conflict_flag is False
    assert snap.evidence_count == 0


def test_build_snapshot_positive_notes():
    notes = [_note("positive"), _note("bullish")]
    snap = build_snapshot_from_notes("AAPL", notes)
    assert snap.catalyst_direction == CATALYST_DIRECTION_POSITIVE
    assert snap.conflict_flag is False
    assert snap.evidence_count == 2


def test_build_snapshot_negative_notes():
    notes = [_note("negative"), _note("bearish")]
    snap = build_snapshot_from_notes("MSFT", notes)
    assert snap.catalyst_direction == CATALYST_DIRECTION_NEGATIVE
    assert snap.conflict_flag is False


def test_build_snapshot_conflict_flag():
    notes = [_note("positive") for _ in range(3)] + [_note("negative") for _ in range(3)]
    snap = build_snapshot_from_notes("SPY", notes)
    assert snap.catalyst_direction == CATALYST_DIRECTION_CONFLICTING
    assert snap.conflict_flag is True


def test_build_snapshot_stale_flag():
    old = datetime.now(UTC) - timedelta(minutes=200)
    notes = [_note("neutral")]
    notes[0].created_at = old
    snap = build_snapshot_from_notes("QQQ", notes, stale_minutes=120)
    assert snap.stale_flag is True


def test_build_snapshot_fresh_not_stale():
    notes = [_note("neutral")]
    snap = build_snapshot_from_notes("AAPL", notes, stale_minutes=120)
    assert snap.stale_flag is False


def test_build_snapshot_neutral_notes():
    notes = [_note("neutral")]
    snap = build_snapshot_from_notes("AAPL", notes)
    assert snap.catalyst_direction == CATALYST_DIRECTION_NEUTRAL
    assert snap.sentiment_label == "neutral"
