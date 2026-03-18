"""Deterministic fixtures for Scrappy snapshot e2e: catalyst direction and staleness."""
from __future__ import annotations

import os
from typing import Any

import pytest


def _db_redis_required() -> bool:
    url = os.environ.get("DATABASE_URL") or ""
    redis_url = os.environ.get("REDIS_URL") or ""
    if not url or "sqlite" in url:
        return False
    if not redis_url:
        return False
    return True


@pytest.fixture
def requires_db_redis():
    """Skip test if DATABASE_URL (Postgres) or REDIS_URL not set for e2e."""
    if not _db_redis_required():
        pytest.skip("DATABASE_URL (Postgres) and REDIS_URL required for DB/Redis e2e")
    return True


# Snapshot fixture params (catalyst_direction, stale_flag, conflict_flag)
FIXTURE_POSITIVE = {"catalyst_direction": "positive", "stale_flag": False, "conflict_flag": False}
FIXTURE_NEGATIVE = {"catalyst_direction": "negative", "stale_flag": False, "conflict_flag": False}
FIXTURE_NEUTRAL = {"catalyst_direction": "neutral", "stale_flag": False, "conflict_flag": False}
FIXTURE_CONFLICTING = {"catalyst_direction": "conflicting", "stale_flag": False, "conflict_flag": True}
FIXTURE_STALE = {"catalyst_direction": "neutral", "stale_flag": True, "conflict_flag": False}


@pytest.fixture
def fixture_positive_snapshot() -> dict[str, Any]:
    return dict(FIXTURE_POSITIVE)


@pytest.fixture
def fixture_negative_snapshot() -> dict[str, Any]:
    return dict(FIXTURE_NEGATIVE)


@pytest.fixture
def fixture_neutral_snapshot() -> dict[str, Any]:
    return dict(FIXTURE_NEUTRAL)


@pytest.fixture
def fixture_conflicting_snapshot() -> dict[str, Any]:
    return dict(FIXTURE_CONFLICTING)


@pytest.fixture
def fixture_stale_snapshot() -> dict[str, Any]:
    return dict(FIXTURE_STALE)
