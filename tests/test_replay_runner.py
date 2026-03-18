"""Replay runner integration: produces expected outputs, repeatable, diff detects changes."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RUN_REPLAY = REPO_ROOT / "scripts" / "run_replay.py"
REPLAY_DIFF = REPO_ROOT / "scripts" / "replay_diff.py"
RESET_STATE = REPO_ROOT / "scripts" / "reset_validation_state.py"
SESSION_001 = REPO_ROOT / "replay" / "session_001"
EXPECTED = SESSION_001 / "expected_outputs.json"


def _load_run_replay_module():
    spec = importlib.util.spec_from_file_location("run_replay", RUN_REPLAY)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_replay"] = mod
    spec.loader.exec_module(mod)
    return mod


def _db_redis_available() -> bool:
    url = os.environ.get("DATABASE_URL") or ""
    redis_url = os.environ.get("REDIS_URL") or ""
    if not url or "sqlite" in url or not redis_url:
        return False
    try:
        import asyncio
        sys.path.insert(0, str(REPO_ROOT / "src"))
        from sqlalchemy import text

        from stockbot.db.session import get_session_factory
        async def check():
            factory = get_session_factory()
            async with factory() as session:
                await session.execute(text("SELECT 1"))
        asyncio.run(check())
        return True
    except Exception:
        return False


@pytest.fixture
def requires_db_redis():
    if not _db_redis_available():
        pytest.skip("DATABASE_URL and REDIS_URL (Postgres + Redis) required for replay runner tests")
    return True


def test_replay_diff_detects_difference(tmp_path):
    """replay_diff.py exits 1 and prints diff when files differ."""
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text('{"signal_count": 1}')
    b.write_text('{"signal_count": 2}')
    r = subprocess.run(
        [sys.executable, str(REPLAY_DIFF), str(a), str(b)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1
    assert "signal_count" in r.stdout or "signal_count" in r.stderr


def test_replay_diff_no_diff(tmp_path):
    """replay_diff.py exits 0 when files match."""
    a = tmp_path / "a.json"
    a.write_text('{"signal_count": 2}')
    r = subprocess.run(
        [sys.executable, str(REPLAY_DIFF), str(a), str(a)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0


def _run_reset_state():
    subprocess.run(
        [sys.executable, str(RESET_STATE)],
        cwd=str(REPO_ROOT),
        env=os.environ,
        capture_output=True,
        check=True,
        timeout=30,
    )


def test_replay_runner_skip_worker_produces_zero_signals(requires_db_redis, tmp_path):
    """With --skip-worker, replay loads data but no signals (runner still collects). Uses clean DB state."""
    _run_reset_state()
    out_json = tmp_path / "actual.json"
    r = subprocess.run(
        [
            sys.executable, str(RUN_REPLAY),
            "--session", str(SESSION_001),
            "--skip-worker",
            "--output", str(out_json),
        ],
        cwd=str(REPO_ROOT),
        env={**os.environ, "PYTHONPATH": f"{REPO_ROOT}:{REPO_ROOT / 'src'}"},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert out_json.exists()
    data = json.loads(out_json.read_text())
    assert data.get("signal_count") == 0


def test_replay_fails_on_dirty_db_without_allow_dirty(requires_db_redis, tmp_path):
    """Replay exits non-zero with clear message when validation tables have rows and --allow-dirty is not set."""
    _run_reset_state()
    # Create dirty state: run replay with --allow-dirty so snapshots (and no signals) remain
    subprocess.run(
        [
            sys.executable, str(RUN_REPLAY),
            "--session", str(SESSION_001),
            "--skip-worker",
            "--allow-dirty",
            "--output", str(tmp_path / "dummy.json"),
        ],
        cwd=str(REPO_ROOT),
        env={**os.environ, "PYTHONPATH": f"{REPO_ROOT}:{REPO_ROOT / 'src'}"},
        capture_output=True,
        text=True,
        timeout=60,
    )
    # Second run without --allow-dirty should fail (DB has symbol_intelligence_snapshots from first run)
    r = subprocess.run(
        [
            sys.executable, str(RUN_REPLAY),
            "--session", str(SESSION_001),
            "--skip-worker",
        ],
        cwd=str(REPO_ROOT),
        env={**os.environ, "PYTHONPATH": f"{REPO_ROOT}:{REPO_ROOT / 'src'}"},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode != 0
    assert "clean validation state" in r.stderr or "allow-dirty" in r.stderr
    _run_reset_state()


def test_merged_timeline_deterministic():
    """Merged timeline is sorted by (ts, type_priority); same input yields same order."""
    mod = _load_run_replay_module()
    timeline = mod.build_merged_timeline(SESSION_001)
    # Check sorted by (ts, priority)
    for i in range(1, len(timeline)):
        prev_ts, prev_pri = timeline[i - 1][0], timeline[i - 1][1]
        curr_ts, curr_pri = timeline[i][0], timeline[i][1]
        assert (prev_ts, prev_pri) <= (curr_ts, curr_pri)
    # Deterministic: run again and get same order
    timeline2 = mod.build_merged_timeline(SESSION_001)
    assert len(timeline) == len(timeline2)
    for a, b in zip(timeline, timeline2):
        assert a[0] == b[0] and a[1] == b[1] and a[2] == b[2]


def test_quote_news_before_decision_bar():
    """Quote and news events precede bars at the same or earlier timestamp."""
    mod = _load_run_replay_module()
    timeline = mod.build_merged_timeline(SESSION_001)
    # session_001: news at 13:30, bars at 13:35..13:40, quotes at 13:35 and 13:40
    # So any bar at 13:40 must come after news (13:30) and after quotes at 13:35/13:40
    bar_indices = [i for i, e in enumerate(timeline) if e[2] == "bar"]
    quote_indices = [i for i, e in enumerate(timeline) if e[2] == "quote"]
    news_indices = [i for i, e in enumerate(timeline) if e[2] == "news"]
    assert news_indices, "session_001 has news"
    assert quote_indices, "session_001 has quotes"
    # Every bar must appear after all news (news has earliest ts)
    if news_indices and bar_indices:
        assert max(news_indices) < min(bar_indices) or timeline[news_indices[0]][0] <= timeline[bar_indices[0]][0]
    # Bars at 13:40: at least one quote at 13:35 or 13:40 must appear before the first 13:40 bar
    from datetime import datetime, timezone
    bar_1340 = [i for i in bar_indices if timeline[i][0].hour == 13 and timeline[i][0].minute == 40]
    if bar_1340:
        first_1340_bar_idx = min(bar_1340)
        # There must be some quote or news before this bar in the timeline
        assert any(i < first_1340_bar_idx for i in quote_indices + news_indices)


def test_full_replay_matches_expected(requires_db_redis, tmp_path):
    """Full replay (worker running) produces output that matches expected_outputs.json."""
    _run_reset_state()
    out_json = tmp_path / "full_actual.json"
    r = subprocess.run(
        [
            sys.executable, str(RUN_REPLAY),
            "--session", str(SESSION_001),
            "--output", str(out_json),
        ],
        cwd=str(REPO_ROOT),
        env={**os.environ, "PYTHONPATH": f"{REPO_ROOT}:{REPO_ROOT / 'src'}"},
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert out_json.exists()
    actual = json.loads(out_json.read_text())
    expected = json.loads(EXPECTED.read_text())
    assert actual.get("signal_count") == expected.get("signal_count")
    assert sorted(actual.get("signal_symbols", [])) == sorted(expected.get("signal_symbols", []))
    assert actual.get("shadow_trade_count") == expected.get("shadow_trade_count")


def test_repeated_replay_identical(requires_db_redis, tmp_path):
    """Two consecutive full replays (with reset between) produce identical outputs."""
    out1 = tmp_path / "out1.json"
    out2 = tmp_path / "out2.json"
    _run_reset_state()
    r1 = subprocess.run(
        [sys.executable, str(RUN_REPLAY), "--session", str(SESSION_001), "--output", str(out1)],
        cwd=str(REPO_ROOT),
        env={**os.environ, "PYTHONPATH": f"{REPO_ROOT}:{REPO_ROOT / 'src'}"},
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert r1.returncode == 0, (r1.stdout, r1.stderr)
    _run_reset_state()
    r2 = subprocess.run(
        [sys.executable, str(RUN_REPLAY), "--session", str(SESSION_001), "--output", str(out2)],
        cwd=str(REPO_ROOT),
        env={**os.environ, "PYTHONPATH": f"{REPO_ROOT}:{REPO_ROOT / 'src'}"},
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert r2.returncode == 0, (r2.stdout, r2.stderr)
    data1 = json.loads(out1.read_text())
    data2 = json.loads(out2.read_text())
    assert data1.get("signal_count") == data2.get("signal_count")
    assert data1.get("signal_symbols") == data2.get("signal_symbols")
    assert data1.get("shadow_trade_count") == data2.get("shadow_trade_count")
