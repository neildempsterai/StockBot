"""Runtime-truth endpoints: health detail, config, runtime status."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from api.main import app


def test_health_detail_shape_honest() -> None:
    """health/detail always returns runtime status fields without fake success."""
    client = TestClient(app)
    r = client.get("/health/detail")
    assert r.status_code == 200
    data = r.json()
    assert "api" in data
    assert "database" in data
    assert "redis" in data
    assert data["api"] == "ok"
    assert data["database"] in {"ok", "error"}
    assert data["redis"] in {"ok", "error"}


def test_v1_config_shape(monkeypatch) -> None:
    """v1/config exposes truthful mode and capability fields."""
    from api import main as api_main

    fake_settings = MagicMock()
    fake_settings.feed = "iex"
    fake_settings.extended_hours_enabled = False
    fake_settings.scrappy_mode = "advisory"
    fake_settings.ai_referee_mode = "off"
    fake_settings.ai_referee_enabled = False
    fake_settings.scanner_mode = "dynamic"
    fake_settings.scanner_top_stale_sec = 900
    fake_settings.stockbot_universe = "AAPL,SPY"
    fake_settings.execution_mode = "shadow"
    fake_settings.paper_execution_enabled = False
    fake_settings.alpaca_api_key_id = ""
    fake_settings.alpaca_api_secret_key = ""
    monkeypatch.setattr(api_main, "get_settings", lambda: fake_settings)

    client = TestClient(app)
    r = client.get("/v1/config")
    assert r.status_code == 200
    data = r.json()
    assert data["FEED"] == "iex"
    assert data["EXTENDED_HOURS_ENABLED"] is False
    assert data["SCANNER_MODE"] == "dynamic"
    assert data["PAPER_EXECUTION_E2E_SUPPORTED"] is False


def test_v1_runtime_status_shape(monkeypatch) -> None:
    """runtime/status reports active symbol sources and mode truth."""
    from api import main as api_main

    fake_settings = MagicMock()
    fake_settings.execution_mode = "shadow"
    fake_settings.paper_execution_enabled = False
    fake_settings.feed = "iex"
    fake_settings.extended_hours_enabled = False
    fake_settings.scanner_top_stale_sec = 900
    fake_settings.redis_url = "redis://fake/0"
    fake_settings.alpaca_api_key_id = ""
    fake_settings.alpaca_api_secret_key = ""
    monkeypatch.setattr(api_main, "get_settings", lambda: fake_settings)

    fake_redis = AsyncMock()
    fake_redis.get = AsyncMock(
        side_effect=[
            "dynamic",
            "",
            "25",
            "2026-01-01T00:00:00+00:00",
            "static",
            "no_live_top_symbols",
            "9",
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
        ]
    )
    monkeypatch.setattr(api_main.redis, "from_url", lambda *args, **kwargs: fake_redis)

    client = TestClient(app)
    r = client.get("/v1/runtime/status")
    assert r.status_code == 200
    data = r.json()
    assert data["strategy"]["execution_mode"] == "shadow"
    assert data["market_data"]["feed"] == "iex"
    assert data["symbol_source"]["gateway"]["active_source"] == "dynamic"
    assert data["symbol_source"]["gateway"]["active_source_label"] == "redis_dynamic"
    assert data["symbol_source"]["worker"]["active_source"] == "static"
    assert data["symbol_source"]["worker"]["active_source_label"] == "static_env"
