# Backlog

- [ ] Create `alpaca_market_gateway` service with single-stream internal fan-out.
- [ ] Create `alpaca_trade_gateway` service for paper `trade_updates`.
- [ ] Create `alpaca_reconciler` polling `/orders`, `/positions`, and latest/snapshot endpoints.
- [ ] Add Tailscale SSH deploy docs and Docker context commands.
- [ ] Add feed provenance columns (`feed`, `quote_ts`, `ingest_ts`, `bid`, `ask`, `last`, `spread_bps`, `latency_ms`).
- [ ] Disable extended-hours logic in strategy configs for v0.1.

### INTRA_EVENT_MOMO (v0.1 shadow slice)

- [x] Strategy module, news classifier, feature set, entry/exit rules.
- [x] Shadow engine (ideal + realistic fills), position lifecycle, conservative exit.
- [x] Worker: consume Redis bars/quotes/news, persist signals and shadow trades (no Alpaca orders).
- [x] Scheduler: daily reset of traded_today at 04:00 ET.
- [x] API: /v1/strategies, /v1/signals, /v1/shadow/trades, /v1/metrics/summary.
- [ ] E2E test with real Redis + Postgres: bar -> signal -> shadow trade persistence.

### Scrappy follow-ups (post v1)

- [x] Wire watchlist table: watchlist_symbols table, GET/POST /scrappy/watchlist, POST /scrappy/run/watchlist uses real symbols.
- [x] Optional open_text fetch: SCRAPPY_OPEN_TEXT_FETCH_ENABLED; fetch_content.fetch_full_text() for open_text domains.
- [x] LLM note drafting: SCRAPPY_LLM_NOTE_DRAFT_ENABLED; router structured_note_draft for summary/why_this_matters.
- [x] Per-source health: scrappy_source_health table, last_attempt_at/success_at, attempt/success/failure counts; GET /scrappy/sources/health.
- [x] E2E test: test_scrappy_e2e.py — run → notes → repeat run → no duplicate notes; idempotent insert by dedup_hash.
- [x] Hardening: source policy with reason codes; policy-driven acquisition; strict JSON LLM draft; source health fetch vs note yield; run counters and outcome from actuals; migration 006; tests (registry, notes, run_outcome).
