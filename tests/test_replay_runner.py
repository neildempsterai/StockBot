"""Replay runner integration: produces expected outputs, repeatable, diff detects changes."""
from __future__ import annotations

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
