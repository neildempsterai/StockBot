# Release Acceptance Checklist

A release candidate must satisfy all items below before merge/release. No exceptions without a Decision Log entry.

## Single release gate command

From repo root, with Postgres and Redis running (e.g. `docker compose -f infra/compose.yaml -f infra/compose.test.yaml up -d postgres redis`):

```bash
export DATABASE_URL=postgresql+asyncpg://stockbot:${POSTGRES_PASSWORD:-stockbot}@localhost:5432/stockbot
export REDIS_URL=redis://localhost:6379/0
# Optional: POSTGRES_PASSWORD if not using default
make release-gate
```

This runs, in order: migrations, DB-backed tests, replay session_001 vs golden, and writes a report to `artifacts/release_gate/`. Exit 0 = pass; exit 1 = first failure. To include UM790 smoke: `make release-gate-um790` (requires docker context `um790` and Alpaca keys).

**Required env**: `DATABASE_URL` (Postgres, async), `REDIS_URL`. Alpaca keys can be dummy for replay.

## Minimum pass criteria

- [ ] **Migrations apply cleanly**  
  `alembic upgrade head` succeeds against the target Postgres (local or deployment). No unapplied migrations.

- [ ] **DB-backed tests pass**  
  With `DATABASE_URL` (Postgres) and `REDIS_URL` set:  
  `make test-db` or `make test-scrappy-db` and `make test-replay` (or full `make release-gate`).

- [ ] **Replay session_001 matches golden outputs**  
  `make replay` exits 0.  
  Outputs compared: signal_count, signal_symbols, signal_sides, rejection_counts_by_reason, shadow_trade_count, shadow_trade_symbols, accepted_with_snapshot_count, accepted_without_snapshot_count, attribution_summary, metrics_summary_subset, replay_version.

- [ ] **Smoke (UM790) passes**  
  After deploy: `make smoke-um790` exits 0.  
  /health, /v1/intelligence/summary, /v1/metrics/summary return 200.

- [ ] **Attribution summary shape is stable**  
  Replay and API metrics/summary expose the same attribution keys (signals_with_scrappy_snapshot, signals_without_scrappy_snapshot, scrappy_gate_rejections). No unexpected new keys that would break consumers.

- [ ] **No duplicate signals or trades on replay restart**  
  Running replay twice (or restarting worker from same stream IDs) does not produce duplicate signals or shadow trades for the same event sequence. Validated by replay repeat-run test and idempotent stream consumption.

## Optional pre-release

- Run `make lint` (ruff + mypy).
- Run full `pytest tests -v`.
- Run `scripts/replay_diff.py expected_outputs.json actual.json` after any intentional strategy change to review diff before accepting new golden outputs.

## Report artifacts

- **Path**: `artifacts/release_gate/` (gitignored).
- **Contents**: `report_YYYYMMDD_HHMMSS.json` and `report_YYYYMMDD_HHMMSS.md` with git commit, migration status, DB test result, replay result, smoke status, timestamp, and overall pass/fail.
- **What blocks release**: Any step failing (migrations, DB tests, replay, or smoke when run) or `release_gate_pass: false` in the JSON report.

## Changing golden outputs

Any change to `replay/session_001/expected_outputs.json` must be:
- Reviewed and explicitly accepted in [DECISION_LOG.md](../DECISION_LOG.md).
- Reflected in this checklist if new assertions are added.
