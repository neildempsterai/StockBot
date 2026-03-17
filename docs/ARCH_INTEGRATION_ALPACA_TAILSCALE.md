# Architecture: Alpaca + Tailscale SSH Integration (v0.1)

Authoritative integration rules for Alpaca market data, Alpaca paper trading, and Tailscale SSH deployment to the UM790.

## Scope

- **Market data**: Alpaca stock data API, IEX feed only (Basic/paper). Consumed via WebSocket for timeliness; REST latest/snapshot/historical for cold start, reconnect recovery, and reconciliation.
- **Trading**: Alpaca paper trading. Orders via REST with `client_order_id = signal_uuid`. Trade lifecycle via `trade_updates` WebSocket (paper endpoint uses binary frames).
- **Deployment**: UM790 reachable only via Tailscale. Docker daemon access via SSH (`docker context`); no Docker TCP port exposed.

## Alpaca Constraints (from current docs)

- Basic/paper stock data is IEX-only.
- Stock data API is best consumed by WebSocket for timeliness.
- Paper fills are simulated from real-time quotes.
- Most subscriptions allow only one active connection per endpoint for the data stream.
- Snapshot endpoint returns: latest trade, latest quote, minute bar, daily bar, previous daily bar.
- `avg_entry_price` and `cost_basis` can change after beginning-of-day sync; do not treat as canonical across day boundaries.

## Service Topology

| Service | Responsibility |
|--------|-----------------|
| `alpaca_market_gateway` | Owns exactly one Alpaca stock-data WebSocket; subscribes to trades, quotes, minute bars (and news in semantic lane); fans out internally. |
| `alpaca_trade_gateway` | Owns Alpaca paper `trade_updates`; normalizes to internal event log. |
| `alpaca_reconciler` | Polls `/orders`, `/positions`; uses latest/snapshot for catch-up; compares to internal ledger. |

## Data Flow

- **Live data**: Alpaca WebSocket (IEX) → alpaca_market_gateway → internal fan-out (Redis stream or in-process pub/sub) → strategy/worker.
- **Orders**: API/worker → REST with `client_order_id = signal_uuid` → Alpaca paper.
- **Fills**: Alpaca `trade_updates` → alpaca_trade_gateway → immutable event log (canonical).
- **Recovery**: On reconnect or detected gap, gateways use REST snapshots/latest to reseed, then resume streaming.

## Idempotency and Ledger

- Every order: `client_order_id = signal_uuid`. Query status by client order ID.
- Internal fill/position ledger is canonical. Store Alpaca `avg_entry_price` / `cost_basis` for reference only; do not use for P&amp;L or risk across day boundaries.
- Carry `feed=iex` and feed provenance (`quote_ts`, `ingest_ts`, `bid`, `ask`, `last`, `spread_bps`, `latency_ms`, `strategy_id`, `strategy_version`) on market events, signals, and fill rows.

## Trading Hours

- v0.1: regular hours only. No extended-hours or 24/5 (separate order-type, TIF, and buying-power rules).

## Deployment

- Tailscale SSH to UM790. Docker context: `ssh://<linux-user>@<tailscale-hostname>`.
- No public Docker, Postgres, or Redis ports. Admin UI internal-only (SSH tunnel / tailnet).
