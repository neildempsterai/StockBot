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
- [ ] Create symbol intelligence snapshot model from Scrappy outputs
- [ ] Link strategy signals to intelligence snapshots
- [ ] Add worker-side deterministic Scrappy gating rules
- [ ] Add attribution metrics: with Scrappy gate vs without Scrappy gate
- [ ] Add stale/conflict/missing intelligence rejection counters
- [ ] Add Docker compose test profile with Postgres + Redis for Scrappy e2e tests
- [ ] Add DB/Redis-backed e2e tests for Scrappy-gated worker flow
- [ ] Add real integration test for signal -> shadow trade -> attribution persistence
- [ ] Add staging smoke script for UM790 deployment and health verification
- [ ] Add fixture-driven replay day for deterministic regression testing
- [ ] Add pass/fail validation checklist for Scrappy-gated strategy behavior
- [ ] Add fixed replay-day dataset for one market session
- [ ] Add replay runner that feeds bars, quotes, trades, news, and Scrappy snapshots deterministically
- [ ] Add golden-output assertions for signals, rejections, shadow trades, and metrics
- [ ] Add regression-diff report for replay changes between commits
- [ ] Add release acceptance checklist based on replay + smoke
- [ ] Containerize release gate so it runs without host venv/tooling
- [ ] Standardize runtime-path tests on async Postgres + Redis
- [ ] Remove SQLite fallback assumptions from API/worker validation tests
- [ ] Clean lint/type issues in release-path files
- [ ] Run first full Docker-native release gate on UM790 and store report artifact
