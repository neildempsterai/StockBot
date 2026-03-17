# Backlog

- [ ] Create `alpaca_market_gateway` service with single-stream internal fan-out.
- [ ] Create `alpaca_trade_gateway` service for paper `trade_updates`.
- [ ] Create `alpaca_reconciler` polling `/orders`, `/positions`, and latest/snapshot endpoints.
- [ ] Add Tailscale SSH deploy docs and Docker context commands.
- [ ] Add feed provenance columns (`feed`, `quote_ts`, `ingest_ts`, `bid`, `ask`, `last`, `spread_bps`, `latency_ms`).
- [ ] Disable extended-hours logic in strategy configs for v0.1.
