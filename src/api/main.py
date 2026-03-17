"""API service: order submission with client_order_id = signal_uuid."""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI

# Placeholder: real app would wire AlpacaClient and LedgerStore

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # shutdown


app = FastAPI(title="StockBot API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/signals")
def create_signal(symbol: str, side: str, qty: float, strategy_id: str, strategy_version: str) -> dict:
    """Submit a signal. In v0.1, client_order_id = signal_uuid for idempotency."""
    signal_uuid = str(uuid.uuid4())
    # In full impl: call AlpacaClient.create_order(..., client_order_id=signal_uuid)
    return {"signal_uuid": signal_uuid, "symbol": symbol, "side": side, "qty": qty}
