# Release Acceptance Checklist

A release candidate must satisfy all items below before merge/release. No exceptions without a Decision Log entry.

## Minimum pass criteria

- [ ] **Migrations apply cleanly**  
  `alembic upgrade head` succeeds against the target Postgres (local or deployment). No unapplied migrations.

- [ ] **DB-backed tests pass**  
  With `DATABASE_URL` (Postgres) and `REDIS_URL` set:  
  `pytest tests -v -k "e2e or replay or worker_scrappy or signal_attribution"` (or `make test-db`) passes.

- [ ] **Replay session_001 matches golden outputs**  
  `python scripts/run_replay.py --session replay/session_001` (or `make replay`) exits 0.  
  Outputs compared: signal_count, signal_symbols, signal_sides, rejection_counts_by_reason, shadow_trade_count, shadow_trade_symbols, accepted_with_snapshot_count, accepted_without_snapshot_count, attribution_summary, metrics_summary_subset, replay_version.

- [ ] **Smoke (UM790) passes**  
  After deploy: `./scripts/smoke_um790.sh` (or `make smoke-um790`) exits 0.  
  /health, /v1/intelligence/summary, /v1/metrics/summary return 200.

- [ ] **Attribution summary shape is stable**  
  Replay and API metrics/summary expose the same attribution keys (signals_with_scrappy_snapshot, signals_without_scrappy_snapshot, scrappy_gate_rejections). No unexpected new keys that would break consumers.

- [ ] **No duplicate signals or trades on replay restart**  
  Running replay twice (or restarting worker from same stream IDs) does not produce duplicate signals or shadow trades for the same event sequence. Validated by replay repeat-run test and idempotent stream consumption.

## Optional pre-release

- Run `ruff check src tests scripts && mypy src`.
- Run full `pytest tests -v`.
- Run `scripts/replay_diff.py expected_outputs.json actual.json` after any intentional strategy change to review diff before accepting new golden outputs.

## Changing golden outputs

Any change to `replay/session_001/expected_outputs.json` must be:
- Reviewed and explicitly accepted in [DECISION_LOG.md](../DECISION_LOG.md).
- Reflected in this checklist if new assertions are added.
