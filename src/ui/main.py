"""Internal admin UI. Access via SSH tunnel only (e.g. ssh -L 8080:localhost:8080 user@um790)."""
import os

import httpx
from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route

API_BASE = os.environ.get("STOCKBOT_API_BASE", "http://localhost:8000")


async def homepage(request):
    return PlainTextResponse(
        "StockBot Admin (internal only)\n"
        "Endpoints: /health, /signals, /shadow-trades, /metrics, /metrics/compare, /metrics/compare-ai-referee, "
        "/config, /intelligence, /intelligence/summary, /ai-referee/recent\n"
    )


async def _get(path: str) -> dict | list:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{API_BASE}{path}", timeout=5.0)
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass
    return {}


async def health_page(request):
    data = await _get("/health")
    return JSONResponse(data if data else {"status": "error", "message": "API unreachable"})


async def signals_page(request):
    data = await _get("/v1/signals?limit=20")
    return JSONResponse(data if data else {"signals": [], "count": 0})


async def shadow_trades_page(request):
    data = await _get("/v1/shadow/trades?limit=20")
    return JSONResponse(data if data else {"trades": [], "count": 0})


async def metrics_page(request):
    data = await _get("/v1/metrics/summary")
    return JSONResponse(data if data else {"signals_total": 0, "shadow_trades_total": 0, "total_net_pnl_shadow": 0})


async def metrics_compare_page(request):
    """Advisory vs required scrappy_mode comparison for staging experiment."""
    data = await _get("/v1/metrics/compare-scrappy-modes")
    if not data:
        data = {"by_scrappy_mode": {}, "note": "API unreachable"}
    return JSONResponse(data)


async def config_page(request):
    data = await _get("/v1/strategies")
    return JSONResponse(data if data else {"strategies": []})


async def intelligence_page(request):
    data = await _get("/v1/intelligence/recent?limit=20")
    return JSONResponse(data if data else {"snapshots": [], "count": 0})


async def intelligence_summary_page(request):
    data = await _get("/v1/intelligence/summary")
    return JSONResponse(data if data else {"snapshots_total": 0, "symbols_with_snapshot": 0, "by_symbol": {}})


async def ai_referee_recent_page(request):
    data = await _get("/v1/ai-referee/recent?limit=20")
    return JSONResponse(data if data else {"assessments": [], "count": 0})


async def metrics_compare_ai_referee_page(request):
    data = await _get("/v1/metrics/compare-ai-referee")
    return JSONResponse(data if data else {"by_decision_class": {}, "signals_with_referee": 0, "signals_without_referee": 0, "note": "API unreachable"})


app = Starlette(
    debug=False,
    routes=[
        Route("/", homepage),
        Route("/health", health_page),
        Route("/signals", signals_page),
        Route("/shadow-trades", shadow_trades_page),
        Route("/metrics", metrics_page),
        Route("/metrics/compare", metrics_compare_page),
        Route("/config", config_page),
        Route("/intelligence", intelligence_page),
        Route("/intelligence/summary", intelligence_summary_page),
        Route("/ai-referee/recent", ai_referee_recent_page),
        Route("/metrics/compare-ai-referee", metrics_compare_ai_referee_page),
    ],
)
