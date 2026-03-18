"""Replay dataset schema and expected_outputs contract validation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION_001 = REPO_ROOT / "replay" / "session_001"


def test_session_001_dir_exists():
    assert SESSION_001.is_dir(), "replay/session_001 must exist"


def test_metadata_schema():
    path = SESSION_001 / "metadata.json"
    assert path.exists()
    with path.open() as f:
        meta = json.load(f)
    assert "session_id" in meta
    assert "replay_version" in meta
    assert meta.get("session_id") == "session_001"


def test_expected_outputs_schema():
    path = SESSION_001 / "expected_outputs.json"
    assert path.exists()
    with path.open() as f:
        out = json.load(f)
    assert "replay_version" in out
    assert "signal_count" in out
    assert "signal_symbols" in out
    assert "signal_sides" in out
    assert "rejection_counts_by_reason" in out
    assert "shadow_trade_count" in out
    assert "shadow_trade_symbols" in out
    assert "accepted_with_snapshot_count" in out
    assert "accepted_without_snapshot_count" in out
    assert "attribution_summary" in out
    assert "metrics_summary_subset" in out
    assert isinstance(out["rejection_counts_by_reason"], dict)
    assert isinstance(out["signal_symbols"], list)
    assert isinstance(out["signal_sides"], list)


def test_bars_jsonl_format():
    path = SESSION_001 / "bars.jsonl"
    assert path.exists()
    with path.open() as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            assert "symbol" in row and "o" in row and "h" in row and "l" in row and "c" in row and "v" in row and "timestamp" in row


def test_scrappy_snapshots_jsonl_format():
    path = SESSION_001 / "scrappy_snapshots.jsonl"
    assert path.exists()
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            assert "symbol" in row and "catalyst_direction" in row
            assert row["catalyst_direction"] in ("positive", "negative", "neutral", "conflicting")
