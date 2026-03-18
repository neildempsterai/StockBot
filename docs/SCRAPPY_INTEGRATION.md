# Scrappy Integration

Scrappy role in StockBot:
- gather external market intelligence
- normalize it into symbol-scoped intelligence snapshots
- preserve evidence references and freshness metadata
- support deterministic strategy filtering and attribution

Scrappy must not:
- emit BUY/SELL/SHORT/COVER instructions
- set entry, exit, stop, or target
- set position size
- place or simulate orders
- override deterministic strategy rules

Strategy consumption rule:
A strategy may consume Scrappy outputs only as:
- gate
- filter
- ranking input
- tag
- attribution dimension

Audit rule:
If a signal uses Scrappy data, the signal must persist:
- scrappy_snapshot_id (intelligence_snapshot_id on signals table)
- scrappy_run_id (on snapshot row)
- freshness_minutes
- catalyst_direction
- catalyst_strength
- evidence refs used

Implementation (strategy bridge):
- **Symbol intelligence snapshots**: `symbol_intelligence_snapshots` table; built from Scrappy notes per symbol after each run. Fields: symbol, snapshot_ts, freshness_minutes, catalyst_direction, catalyst_strength, sentiment_label, evidence_count, source_count, stale_flag, conflict_flag, raw_evidence_refs_json, scrappy_run_id, scrappy_version.
- **Worker gating**: `SCRAPPY_MODE=off | advisory | required` (default advisory). INTRA_EVENT_MOMO fetches latest non-stale snapshot per symbol; long entries allowed only when catalyst_direction is positive or neutral; short only when negative or neutral; reject if conflict_flag or stale_flag; if required and no snapshot, reject (scrappy_missing). Reason codes: scrappy_positive, scrappy_negative, scrappy_neutral, scrappy_conflict, scrappy_stale, scrappy_missing.
- **API**: GET /v1/intelligence/latest?symbol=, GET /v1/intelligence/recent?symbol=&limit=, GET /v1/intelligence/summary. Signal detail includes intelligence_snapshot when present. Metrics summary includes signals_with_scrappy_snapshot, signals_without_scrappy_snapshot, scrappy_gate_rejections.
- **Attribution**: scrappy_gate_rejections table stores rejections for attribution metrics.

## End-to-end validation

- **DB-backed tests**: Run with Postgres + Redis (e.g. `docker compose -f infra/compose.yaml -f infra/compose.test.yaml up -d postgres redis` then set `DATABASE_URL` and `REDIS_URL`). Tests: `test_scrappy_*.py`, `test_worker_scrappy_e2e.py`, `test_api_intelligence_db.py`, `test_signal_attribution_e2e.py`.
- **Replay helper**: `tests/helpers/replay.py` — `push_bar`, `push_quote`, `push_news`, `create_snapshot_in_db` for deterministic event sequences.
- **Replay runner**: `scripts/run_replay.py` — loads `replay/session_001` (bars, quotes, trades, news, scrappy_snapshots), runs worker, compares outputs to `expected_outputs.json`. Used as the main regression gate; see [TEST_PLAN_V01.md](TEST_PLAN_V01.md) and [RELEASE_ACCEPTANCE_CHECKLIST.md](RELEASE_ACCEPTANCE_CHECKLIST.md). Run: `make replay` or `PYTHONPATH=.:src python scripts/run_replay.py --session replay/session_001`.
- **Golden outputs**: `replay/session_001/expected_outputs.json` — contract for signal_count, signal_symbols, signal_sides, rejection_counts_by_reason, shadow_trade_count, attribution_summary, etc. Any change must be documented in DECISION_LOG.md.
- **Replay diff**: `scripts/replay_diff.py <a.json> <b.json>` — human-readable diff of two replay output JSONs; use to review intentional strategy changes before accepting new golden outputs.
- **Gate logic**: `worker.main.scrappy_gate_check(snapshot_row, side, scrappy_mode)` — returns rejection reason or None; unit-tested without DB.
- **Staging smoke**: `./scripts/smoke_um790.sh` — context check, compose up, GET /health, /v1/intelligence/summary, /v1/metrics/summary, logs. Pass = all return 200; fail = exit non-zero.
