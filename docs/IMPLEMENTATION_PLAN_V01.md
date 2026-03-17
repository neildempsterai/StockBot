# Implementation Plan: v0.1 Alpaca + Tailscale SSH

## 1) File paths

```
StockBot/
├── KB_INDEX.md
├── DECISION_LOG.md
├── BACKLOG.md
├── docs/
│   ├── ARCH_INTEGRATION_ALPACA_TAILSCALE.md
│   ├── OPS_RUNBOOK_TAILSCALE_SSH.md
│   └── IMPLEMENTATION_PLAN_V01.md
├── infra/
│   ├── compose.yaml
│   └── .env.example
├── pyproject.toml
├── ruff.toml
├── src/
│   ├── stockbot/
│   │   __init__.py
│   │   ├── config.py
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── session.py
│   │   │   └── models.py
│   │   ├── alpaca/
│   │   │   ├── __init__.py
│   │   │   ├── client.py          # REST client (shared)
│   │   │   ├── stream_client.py   # Data WebSocket (single connection)
│   │   │   ├── trading_stream.py  # Paper trade_updates
│   │   │   └── types.py
│   │   ├── gateways/
│   │   │   ├── __init__.py
│   │   │   ├── market_gateway.py  # alpaca_market_gateway entry
│   │   │   ├── trade_gateway.py   # alpaca_trade_gateway entry
│   │   │   └── reconciler.py      # alpaca_reconciler entry
│   │   └── ledger/
│   │       ├── __init__.py
│   │       ├── events.py          # Immutable event log types
│   │       └── store.py           # Persist fills/signals with feed provenance
│   ├── alpaca_market_gateway/
│   │   └── main.py
│   ├── alpaca_trade_gateway/
│   │   └── main.py
│   ├── alpaca_reconciler/
│   │   └── main.py
│   ├── api/
│   │   └── main.py
│   ├── worker/
│   │   └── main.py
│   ├── scheduler/
│   │   └── main.py
│   └── ui/
│       └── (static or minimal server)
├── migrations/
│   └── versions/
│       └── 001_feed_provenance_and_ledger.py
├── tests/
│   ├── conftest.py
│   ├── test_market_gateway_fanout.py
│   ├── test_trade_gateway_binary_frames.py
│   ├── test_recovery_reseed.py
│   ├── test_idempotency_client_order_id.py
│   ├── test_bod_reconciliation.py
│   └── test_alpaca_client.py
└── scripts/
    └── docker_context_um790.sh
```

## 2) Compose topology

- **Services**: api, worker, scheduler, postgres, redis, alpaca_market_gateway, alpaca_trade_gateway, alpaca_reconciler, ui.
- **No published ports** for postgres, redis.
- **UI**: bind to localhost or omit ports (SSH tunnel only).
- **Docker**: no host binding for daemon; deploy via `docker context` over SSH.

## 3) Service interfaces and adapters

| Component | Interface | Adapter |
|-----------|-----------|---------|
| Market data ingest | Single Alpaca data WebSocket | `alpaca.stream_client.StreamClient` (one connection) |
| Market fan-out | Internal pub/sub | Redis Streams or asyncio broadcast to in-process subscribers |
| Trade updates ingest | Alpaca paper trade_updates | `alpaca.trading_stream.TradingStream` (binary-frame capable) |
| Orders out | REST | `alpaca.client.AlpacaClient` with `client_order_id=signal_uuid` |
| Recovery | REST snapshots/latest | Same `AlpacaClient`; gateways call on reconnect |
| Ledger | Canonical fills/signals | `ledger.store.LedgerStore` with feed, quote_ts, ingest_ts, etc. |

## 4) Migrations

- Add tables/columns: `feed`, `quote_ts`, `ingest_ts`, `bid`, `ask`, `last`, `spread_bps`, `latency_ms`, `strategy_id`, `strategy_version` on signals and fill rows.
- Internal fill ledger table keyed by `signal_uuid` / `client_order_id`; Alpaca `avg_entry_price` stored as non-canonical reference.

## 5) Tests

- One-connection fan-out: only one Alpaca data connection; downstream still receives events.
- Binary-frame trade_updates: paper stream parser handles binary frames.
- Recovery: kill stream, reseed from snapshots/latest, resume without duplicating bars/quotes.
- Idempotency: same signal_uuid does not create second order (client_order_id reuse).
- BOD reconciliation: internal ledger stable when Alpaca position averages change.
- SSH deploy smoke: `docker --context um790 ps` / compose ps over tailnet; no Docker TCP.
- Access-control: documented tailnet policy (deny-by-default).

## 6) Deploy docs

- OPS_RUNBOOK_TAILSCALE_SSH.md: Docker context create/use, compose up, restart/rollback, no-public-port policy.
- scripts/docker_context_um790.sh: Example script for context creation and deploy.
