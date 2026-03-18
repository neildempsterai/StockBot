"""Tests for Scrappy API response shapes."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from api.main import app

# Skip notes/run tests when no Postgres (async); sqlite URL would use sync driver
REQUIRES_DB = not os.environ.get("DATABASE_URL") or "sqlite" in (os.environ.get("DATABASE_URL") or "")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_scrappy_health(client: TestClient) -> None:
    r = client.get("/scrappy/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    assert data.get("service") == "scrappy"


def test_scrappy_telemetry(client: TestClient) -> None:
    r = client.get("/scrappy/telemetry?limit=10&hours=24")
    assert r.status_code == 200
    data = r.json()
    assert "sources_count" in data
    assert "runs" in data


def test_scrappy_sources_health(client: TestClient) -> None:
    r = client.get("/scrappy/sources/health")
    assert r.status_code == 200
    data = r.json()
    assert "total_configured" in data
    assert "enabled" in data
    assert "sources" in data


def test_scrappy_audit(client: TestClient) -> None:
    r = client.get("/scrappy/audit?limit=5")
    assert r.status_code == 200
    data = r.json()
    assert "limit" in data
    assert "runs" in data


@pytest.mark.skipif(REQUIRES_DB, reason="DATABASE_URL not set")
def test_scrappy_notes_recent(client: TestClient) -> None:
    r = client.get("/scrappy/notes/recent?limit=10")
    assert r.status_code == 200
    data = r.json()
    assert "notes" in data
    assert "count" in data
    assert isinstance(data["notes"], list)


@pytest.mark.skipif(REQUIRES_DB, reason="DATABASE_URL not set")
def test_scrappy_run_post(client: TestClient) -> None:
    r = client.post("/scrappy/run?run_type=sweep")
    assert r.status_code == 200
    data = r.json()
    assert "run_id" in data
    assert data.get("run_type") == "sweep"
    assert "outcome_code" in data
