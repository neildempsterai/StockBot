"""Tests for validation script behavior: gating and API_ONLY mode.

Contract tests only. No live orders. No fake integration success.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

SCRIPT_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))


def test_paper_lifecycle_validate_exits_2_without_gate() -> None:
    """Without ENABLE_LIVE_PAPER_VALIDATION=1, paper_lifecycle_validate.sh must exit 2 (gated)."""
    script = os.path.join(SCRIPT_DIR, "paper_lifecycle_validate.sh")
    if not os.path.isfile(script):
        pytest.skip("paper_lifecycle_validate.sh not found")
    env = os.environ.copy()
    env.pop("ENABLE_LIVE_PAPER_VALIDATION", None)
    result = subprocess.run(
        ["bash", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert b"ENABLE_LIVE_PAPER_VALIDATION" in result.stderr or b"disabled" in result.stderr.lower()


def test_paper_lifecycle_validate_requires_credentials_or_fails_on_api() -> None:
    """With gate set, script must exit 2 if credentials missing, or exit 1 if API/status unreachable.
    (If .env supplies credentials, script may reach API check and exit 1 instead of 2.)"""
    script = os.path.join(SCRIPT_DIR, "paper_lifecycle_validate.sh")
    if not os.path.isfile(script):
        pytest.skip("paper_lifecycle_validate.sh not found")
    env = os.environ.copy()
    env["ENABLE_LIVE_PAPER_VALIDATION"] = "1"
    env.pop("ALPACA_API_KEY_ID", None)
    env.pop("ALPACA_API_SECRET_KEY", None)
    result = subprocess.run(
        ["bash", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode != 0
    stderr = result.stderr.lower()
    assert (
        b"credential" in stderr
        or b"alpaca" in stderr
        or b"status failed" in stderr
        or b"broker" in stderr
        or b"api" in stderr
    )


def test_runtime_truth_validate_api_only_skips_compose() -> None:
    """With API_ONLY=1, runtime_truth_validate.sh should not run docker compose (runs HTTP only).
    We only check that the script runs and eventually fails on unreachable BASE_URL (no server)."""
    script = os.path.join(SCRIPT_DIR, "runtime_truth_validate.sh")
    if not os.path.isfile(script):
        pytest.skip("runtime_truth_validate.sh not found")
    env = os.environ.copy()
    env["API_ONLY"] = "1"
    env["BASE_URL"] = "http://127.0.0.1:19999"
    result = subprocess.run(
        ["bash", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        timeout=30,
    )
    # Should fail (connection refused) and exit 1, not fail on missing compose
    assert result.returncode == 1
    # Should not say "compose.yaml not found" (that would be full-stack path)
    assert b"compose.yaml not found" not in result.stderr or b"API-only" in result.stdout
