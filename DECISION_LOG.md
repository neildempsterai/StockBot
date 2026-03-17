# Decision Log

## 2026-03-17 — Freeze v0.1 integrations to Alpaca + Tailscale SSH
Status: Accepted

Decision:
- Alpaca is the sole v0.1 provider for US equities market data and paper trading.
- Runtime uses Alpaca direct APIs only; no Alpaca MCP runtime integration.
- One internal market-data gateway owns the Alpaca stock stream and fans out internally.
- One separate trade gateway owns Alpaca paper `trade_updates`.
- REST latest/snapshot/historical endpoints are recovery/reconciliation tools, not the primary live data path.
- `client_order_id` must equal the bot signal UUID for idempotency and auditability.
- Internal fills/positions ledger is canonical; Alpaca-reported average entry price is informational only.
- Deployment to the UM790 is SSH-only over Tailscale using Docker contexts; no public Docker daemon exposure.
- v0.1 trading scope is regular-hours only; extended-hours and 24/5 are disabled.
