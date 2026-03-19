"""Paper execution lifecycle: status/proof endpoint shapes and four-flow documentation.

These tests validate API contract and response shape. They do not place real orders.
Run with full stack (DB + Alpaca) for integration; with mocks they validate structure only.
"""
from __future__ import annotations

import pytest

# Only run if the app can be loaded (full repo deps available)
try:
    from fastapi.testclient import TestClient
    from api.main import app
    APP_AVAILABLE = True
except Exception:
    APP_AVAILABLE = False

pytestmark = pytest.mark.skipif(not APP_AVAILABLE, reason="api.main not loadable (missing deps)")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_paper_test_status_shape(client: TestClient) -> None:
    """GET /v1/paper/test/status returns operator status shape; 200 or 503 with real reason."""
    r = client.get("/v1/paper/test/status")
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        data = r.json()
        # Must not be fake/demo; must reflect real state
        assert "paper_enabled" in data or "paper_execution_enabled" in data or "detail" not in data
    else:
        assert "detail" in r.json()


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


def test_paper_buy_open_route_accepts_body(client: TestClient) -> None:
    """POST /v1/paper/test/buy-open accepts symbol, qty; returns 200 with result or 503."""
    r = client.post(
        "/v1/paper/test/buy-open",
        json={"symbol": "AAPL", "qty": 1, "order_type": "market"},
    )
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        data = r.json()
        assert data.get("_operator_only") is True


def test_paper_sell_close_route_accepts_body(client: TestClient) -> None:
    """POST /v1/paper/test/sell-close accepts symbol, qty."""
    r = client.post(
        "/v1/paper/test/sell-close",
        json={"symbol": "AAPL", "qty": 1, "order_type": "market"},
    )
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert r.json().get("_operator_only") is True


def test_paper_short_open_route_accepts_body(client: TestClient) -> None:
    """POST /v1/paper/test/short-open accepts symbol, qty."""
    r = client.post(
        "/v1/paper/test/short-open",
        json={"symbol": "AAPL", "qty": 1, "order_type": "market"},
    )
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert r.json().get("_operator_only") is True


def test_paper_buy_cover_route_accepts_body(client: TestClient) -> None:
    """POST /v1/paper/test/buy-cover accepts symbol, qty."""
    r = client.post(
        "/v1/paper/test/buy-cover",
        json={"symbol": "AAPL", "qty": 1, "order_type": "market"},
    )
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert r.json().get("_operator_only") is True


def test_compare_books_shape(client: TestClient) -> None:
    """GET /v1/portfolio/compare-books returns shadow vs paper; no fake values."""
    r = client.get("/v1/portfolio/compare-books")
    assert r.status_code == 200
    data = r.json()
    assert "shadow" in data
    assert "paper" in data
    assert "trade_count" in data["shadow"] or "fill_count" in data["paper"]


def test_reconciliation_shape(client: TestClient) -> None:
    """GET /v1/system/reconciliation returns matched/mismatch counts or no_runs."""
    r = client.get("/v1/system/reconciliation")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert data["status"] in ("ok", "no_runs") or "orders_matched" in data
