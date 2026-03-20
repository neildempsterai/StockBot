"""Paper execution lifecycle: status/proof endpoint shapes and four-flow documentation.

These tests validate API contract and response shape. They do not place real orders.
Run with full stack (DB + Alpaca) for integration; with mocks they validate structure only.

When running outside Docker (host machine), DB and Redis use Docker-internal hostnames
(postgres, redis) that won't resolve. Tests that hit these services will be skipped
with a clear message. Run inside the Docker network for full integration testing.
"""
from __future__ import annotations

import socket
import pytest

# Only run if the app can be loaded (full repo deps available)
try:
    from fastapi.testclient import TestClient
    from api.main import app
    APP_AVAILABLE = True
except Exception:
    APP_AVAILABLE = False

# Check if DB/Redis are reachable (Docker hostnames resolve)
def _can_resolve(host: str) -> bool:
    try:
        socket.getaddrinfo(host, None)
        return True
    except socket.gaierror:
        return False

DB_REACHABLE = _can_resolve("postgres")
REDIS_REACHABLE = _can_resolve("redis")

pytestmark = pytest.mark.skipif(not APP_AVAILABLE, reason="api.main not loadable (missing deps)")

requires_db = pytest.mark.skipif(
    not DB_REACHABLE,
    reason="DB hostname 'postgres' not resolvable — run inside Docker network"
)
requires_infra = pytest.mark.skipif(
    not (DB_REACHABLE and REDIS_REACHABLE),
    reason="DB/Redis hostnames not resolvable — run inside Docker network"
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_paper_test_status_shape(client: TestClient) -> None:
    """GET /v1/paper/test/status returns operator status shape; 200 or 503 with real reason."""
    r = client.get("/v1/paper/test/status")
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        data = r.json()
        # Must distinguish state: paper_disabled | credentials_missing | broker_unavailable | broker_connected_no_proof | proof_partial | proof_complete
        assert "state" in data
        assert data["state"] in (
            "paper_disabled",
            "credentials_missing",
            "broker_unavailable",
            "broker_connected_no_proof",
            "proof_partial",
            "proof_complete",
        )
        assert "paper_enabled" in data or "paper_execution_enabled" in data
    else:
        assert "detail" in r.json()


@requires_db
def test_paper_test_proof_shape(client: TestClient) -> None:
    """GET /v1/paper/test/proof returns proof per intent; intents are the four flows."""
    r = client.get("/v1/paper/test/proof")
    assert r.status_code == 200
    data = r.json()
    assert "proof" in data
    assert "intents" in data
    assert set(data["intents"]) == {"buy_open", "sell_close", "short_open", "buy_cover"}
    for intent in data["intents"]:
        assert intent in data["proof"]
        if data["proof"][intent] is not None:
            p = data["proof"][intent]
            assert "order_id" in p or "client_order_id" in p
            assert "order_intent" in p


@requires_infra
def test_paper_buy_open_route_accepts_body(client: TestClient) -> None:
    """POST /v1/paper/test/buy-open accepts symbol, qty; returns 200, 403 (not armed), or 503."""
    r = client.post(
        "/v1/paper/test/buy-open",
        json={"symbol": "AAPL", "qty": 1, "order_type": "market"},
    )
    assert r.status_code in (200, 403, 503)
    if r.status_code == 200:
        data = r.json()
        assert data.get("_operator_only") is True
    elif r.status_code == 403:
        data = r.json()
        assert "detail" in data


@requires_infra
def test_paper_sell_close_route_accepts_body(client: TestClient) -> None:
    """POST /v1/paper/test/sell-close accepts symbol, qty."""
    r = client.post(
        "/v1/paper/test/sell-close",
        json={"symbol": "AAPL", "qty": 1, "order_type": "market"},
    )
    assert r.status_code in (200, 403, 503)
    if r.status_code == 200:
        assert r.json().get("_operator_only") is True


@requires_infra
def test_paper_short_open_route_accepts_body(client: TestClient) -> None:
    """POST /v1/paper/test/short-open accepts symbol, qty."""
    r = client.post(
        "/v1/paper/test/short-open",
        json={"symbol": "AAPL", "qty": 1, "order_type": "market"},
    )
    assert r.status_code in (200, 403, 503)
    if r.status_code == 200:
        assert r.json().get("_operator_only") is True


@requires_infra
def test_paper_buy_cover_route_accepts_body(client: TestClient) -> None:
    """POST /v1/paper/test/buy-cover accepts symbol, qty."""
    r = client.post(
        "/v1/paper/test/buy-cover",
        json={"symbol": "AAPL", "qty": 1, "order_type": "market"},
    )
    assert r.status_code in (200, 403, 503)
    if r.status_code == 200:
        assert r.json().get("_operator_only") is True


@requires_infra
def test_compare_books_shape(client: TestClient) -> None:
    """GET /v1/portfolio/compare-books returns shadow vs paper; no fake values."""
    r = client.get("/v1/portfolio/compare-books")
    assert r.status_code == 200
    data = r.json()
    assert "shadow" in data
    assert "paper" in data
    assert "trade_count" in data["shadow"] or "fill_count" in data["paper"]


@requires_infra
def test_reconciliation_shape(client: TestClient) -> None:
    """GET /v1/system/reconciliation returns matched/mismatch counts or no_runs."""
    r = client.get("/v1/system/reconciliation")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert data["status"] in ("ok", "no_runs") or "orders_matched" in data


@requires_infra
def test_paper_exposure_lifecycle_fields(client: TestClient) -> None:
    """GET /v1/paper/exposure returns lifecycle fields when lifecycle exists."""
    r = client.get("/v1/paper/exposure")
    assert r.status_code in (200, 503)
    data = r.json()
    assert "positions" in data
    if r.status_code == 503:
        return
    assert "count" in data
    # If positions exist, check for lifecycle fields
    if data["positions"]:
        pos = data["positions"][0]
        # Lifecycle fields should be present (may be None if no lifecycle)
        assert "entry_order_id" in pos
        assert "exit_order_id" in pos
        assert "stop_price" in pos
        assert "target_price" in pos
        assert "force_flat_time" in pos
        assert "protection_mode" in pos
        assert "protection_active" in pos
        assert "managed_status" in pos
        assert "orphaned" in pos
        assert "universe_source" in pos
        assert "static_fallback_at_entry" in pos
        assert "lifecycle_status" in pos
        assert "exit_reason" in pos
        assert "exit_ts" in pos
        assert "last_error" in pos
        # Sizing fields should be present
        assert "sizing_at_entry" in pos
        if pos["sizing_at_entry"]:
            sizing = pos["sizing_at_entry"]
            assert "equity" in sizing
            assert "buying_power" in sizing
            assert "stop_distance" in sizing
            assert "qty_approved" in sizing


@requires_infra
def test_paper_exposure_managed_status_values(client: TestClient) -> None:
    """GET /v1/paper/exposure managed_status has valid values."""
    r = client.get("/v1/paper/exposure")
    assert r.status_code in (200, 503)
    if r.status_code != 200:
        return
    data = r.json()
    valid_statuses = {"managed", "unmanaged", "orphaned", "exited", "pending", "blocked"}
    for pos in data.get("positions", []):
        if "managed_status" in pos and pos["managed_status"]:
            assert pos["managed_status"] in valid_statuses


@requires_infra
def test_paper_exposure_lifecycle_status_values(client: TestClient) -> None:
    """GET /v1/paper/exposure lifecycle_status has valid values when present."""
    r = client.get("/v1/paper/exposure")
    assert r.status_code in (200, 503)
    if r.status_code != 200:
        return
    data = r.json()
    valid_statuses = {
        "planned",
        "entry_submitted",
        "entry_filled",
        "exit_pending",
        "exit_submitted",
        "exited",
        "orphaned",
        "blocked",
        "not_persisted",
    }
    for pos in data.get("positions", []):
        if "lifecycle_status" in pos and pos["lifecycle_status"]:
            assert pos["lifecycle_status"] in valid_statuses


@requires_infra
def test_paper_exposure_protection_mode_values(client: TestClient) -> None:
    """GET /v1/paper/exposure protection_mode has valid values when present."""
    r = client.get("/v1/paper/exposure")
    assert r.status_code in (200, 503)
    if r.status_code != 200:
        return
    data = r.json()
    valid_modes = {"broker_native", "worker_mirrored", "unprotected", "unknown"}
    for pos in data.get("positions", []):
        if "protection_mode" in pos and pos["protection_mode"]:
            assert pos["protection_mode"] in valid_modes
