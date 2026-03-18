"""API: /health, /v1/strategies, /v1/signals, /v1/shadow/trades, /v1/metrics/summary.
DB-dependent tests require async Postgres (DATABASE_URL with postgresql+asyncpg)."""
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


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_v1_strategies(client: TestClient) -> None:
    r = client.get("/v1/strategies")
    assert r.status_code == 200
    data = r.json()
    assert "strategies" in data
    assert len(data["strategies"]) >= 1
    assert data["strategies"][0]["strategy_id"] == "INTRA_EVENT_MOMO"


@pytest.mark.skipif(
    not _has_async_db(),
    reason="DATABASE_URL must be Postgres (async); endpoint uses get_session_factory",
)
def test_v1_signals_list(client: TestClient) -> None:
    r = client.get("/v1/signals?limit=5")
    assert r.status_code == 200
    data = r.json()
    assert "signals" in data
    assert "count" in data
    assert isinstance(data["signals"], list)


@pytest.mark.skipif(
    not _has_async_db(),
    reason="DATABASE_URL must be Postgres (async); endpoint uses get_session_factory",
)
def test_v1_signals_detail_not_found(client: TestClient) -> None:
    r = client.get("/v1/signals/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


@pytest.mark.skipif(
    not _has_async_db(),
    reason="DATABASE_URL must be Postgres (async); endpoint uses get_session_factory",
)
def test_v1_shadow_trades(client: TestClient) -> None:
    r = client.get("/v1/shadow/trades?limit=5")
    assert r.status_code == 200
    data = r.json()
    assert "trades" in data
    assert "count" in data


@pytest.mark.skipif(
    not _has_async_db(),
    reason="DATABASE_URL must be Postgres (async); endpoint uses get_session_factory",
)
def test_v1_metrics_summary(client: TestClient) -> None:
    r = client.get("/v1/metrics/summary")
    assert r.status_code == 200
    data = r.json()
    assert "signals_total" in data
    assert "shadow_trades_total" in data
    assert "total_net_pnl_shadow" in data
