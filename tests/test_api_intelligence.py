"""Tests for intelligence API endpoints."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from api.main import app


def _has_async_db() -> bool:
    url = os.environ.get("DATABASE_URL", "")
    return "postgresql+asyncpg" in url or (
        url.startswith("postgresql://") and "asyncpg" not in url
    )


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_intelligence_latest_requires_symbol(client: TestClient) -> None:
    """Does not hit DB; 422 when symbol missing."""
    r = client.get("/v1/intelligence/latest")
    assert r.status_code == 422


@pytest.mark.skipif(
    not _has_async_db(),
    reason="DATABASE_URL must be Postgres (async); these endpoints use get_session_factory",
)
def test_intelligence_recent_shape(client: TestClient) -> None:
    r = client.get("/v1/intelligence/recent?limit=5")
    assert r.status_code == 200
    data = r.json()
    assert "snapshots" in data
    assert "count" in data
    assert isinstance(data["snapshots"], list)


@pytest.mark.skipif(
    not _has_async_db(),
    reason="DATABASE_URL must be Postgres (async); these endpoints use get_session_factory",
)
def test_intelligence_summary_shape(client: TestClient) -> None:
    r = client.get("/v1/intelligence/summary")
    assert r.status_code == 200
    data = r.json()
    assert "snapshots_total" in data
    assert "symbols_with_snapshot" in data
    assert "by_symbol" in data


@pytest.mark.skipif(
    not _has_async_db(),
    reason="DATABASE_URL must be Postgres (async); these endpoints use get_session_factory",
)
def test_metrics_summary_includes_attribution(client: TestClient) -> None:
    r = client.get("/v1/metrics/summary")
    assert r.status_code == 200
    data = r.json()
    assert "signals_total" in data
    assert "signals_with_scrappy_snapshot" in data
    assert "signals_without_scrappy_snapshot" in data
    assert "scrappy_gate_rejections" in data
    assert isinstance(data["scrappy_gate_rejections"], dict)
