# Test Plan Additions (v0.1)

## One-connection fan-out test

Only one Alpaca market-data connection is active; downstream consumers still receive all events.

- **Location**: `tests/test_market_gateway_fanout.py`
- **Assertion**: `StreamClient` owns a single WebSocket; handlers are registered for internal fan-out. Fan-out handler pushes to Redis streams.

## Binary-frame trade-update test

Paper `trade_updates` parser handles the paper stream correctly (including binary frames).

- **Location**: `tests/test_trade_gateway_binary_frames.py`
- **Assertion**: `TradingStreamClient._parse_update` parses both text JSON and decoded binary payloads.

## Recovery test

Kill the market stream, reseed from snapshots/latest, then resume without duplicating bars or quote state.

- **Location**: `tests/test_recovery_reseed.py`
- **Assertion**: `reseed_from_snapshots` calls REST snapshots and dispatches quote/trade to the same handlers used by the stream.

## Idempotency test

Re-sending the same signal UUID does not create a second paper order because `client_order_id` is reused.

- **Location**: `tests/test_idempotency_client_order_id.py`
- **Assertion**: `create_order` sends `client_order_id` in the request; `get_order_by_client_order_id` queries by it.

## BOD reconciliation test

Internal ledger stays stable even when Alpaca's position average fields change after BOD sync.

- **Location**: `tests/test_bod_reconciliation.py`
- **Assertion**: `FillEvent` carries `avg_fill_price` as canonical; `alpaca_avg_entry_price` is informational only.

## SSH deploy smoke test

`docker --context um790 ps` and `docker --context um790 compose ps` work over the tailnet; no Docker TCP listener is exposed.

- **Manual**: After creating the context, run from laptop and confirm containers list. Do not open Docker on a TCP port on the UM790.

## Access-control test

Tailnet policy only allows your user to SSH to the UM790. Tailscale's access-control model is deny-by-default and policy-driven.

- **Manual**: Configure in Tailscale admin (ACLs / SSH). Document in OPS_RUNBOOK_TAILSCALE_SSH.md.

## INTRA_EVENT_MOMO strategy tests

- **News classification**: `tests/test_intra_event_momo_news.py` — positive/negative/neutral keyword tagging.
- **Signal generation**: `tests/test_intra_event_momo_signals.py` — long/short signal, reject spread/news/gap.
- **Shadow engine**: `tests/test_shadow_engine.py` — ideal/realistic fill math, conservative intrabar stop-vs-target.
- **API**: `tests/test_api_strategies.py` — GET /health, /v1/strategies, /v1/signals, /v1/signals/{uuid}, /v1/shadow/trades, /v1/metrics/summary.
- **Scheduler day reset**: Manual or integration — TRADED_TODAY_KEY cleared at session boundary (04:00 ET).
- **One trade per symbol per day**: Worker uses Redis set `stockbot:strategies:intra_event_momo:traded_today`; scheduler clears daily.

## Scrappy-gated strategy and e2e validation

- **Gate logic (unit)**: `tests/test_worker_scrappy_e2e.py` — `scrappy_gate_check`: reject long when negative, short when positive; reject stale/conflict/missing when required.
- **DB-backed e2e**: Same file + `tests/test_api_intelligence_db.py`, `tests/test_signal_attribution_e2e.py` — require `DATABASE_URL` (Postgres) and optionally `REDIS_URL`. Cover: snapshot persist/read, rejection counts, signal with `intelligence_snapshot_id`, metrics attribution keys.
- **Replay helper**: `tests/helpers/replay.py` — push_bar, push_quote, push_news, create_snapshot_in_db for deterministic replay.
- **Run DB-backed tests locally**: `docker compose -f infra/compose.yaml -f infra/compose.test.yaml up -d postgres redis` then `DATABASE_URL=postgresql+asyncpg://stockbot:PASSWORD@localhost:5432/stockbot REDIS_URL=redis://localhost:6379/0 pytest tests/test_scrappy_*.py tests/test_worker_scrappy_e2e.py tests/test_api_intelligence_db.py tests/test_signal_attribution_e2e.py -v`.
- **Staging smoke**: `./scripts/smoke_um790.sh` — run after UM790 deploy; checks context, compose up, GET /health, /v1/intelligence/summary, /v1/metrics/summary, prints logs. **Pass** = script exits 0 and all endpoints 200; **Fail** = non-zero exit, logs printed.

## Deterministic Replay Gate

A release candidate must pass one fixed replay-day test pack.

The replay gate must prove:
- exact signal count
- exact rejection count by reason_code
- exact shadow trade count
- exact accepted vs rejected Scrappy-gated candidates
- exact attribution summary shape
- no duplicate processing on replay restart
- stable outputs across repeated runs with the same inputs

Any change in golden outputs must be reviewed and explicitly accepted in the Decision Log before release.

### How to run replay locally

- Start Postgres + Redis (e.g. `docker compose -f infra/compose.yaml -f infra/compose.test.yaml up -d postgres redis`).
- Set `DATABASE_URL`, `REDIS_URL`, and Alpaca keys (dummy OK for replay).
- From repo root: `make replay` or `PYTHONPATH=.:src python scripts/run_replay.py --session replay/session_001`.
- Exit 0 = outputs match `replay/session_001/expected_outputs.json`; exit 1 = mismatch and diff printed to stderr.

### How to refresh golden outputs

- After an intentional strategy or gate change, run:  
  `PYTHONPATH=.:src python scripts/run_replay.py --session replay/session_001 --output replay/session_001/actual.json`.
- Compare: `python scripts/replay_diff.py replay/session_001/expected_outputs.json replay/session_001/actual.json`.
- If the diff is accepted, copy `actual.json` to `expected_outputs.json` and add a Decision Log entry for the change.

### What counts as release-pass

See [RELEASE_ACCEPTANCE_CHECKLIST.md](RELEASE_ACCEPTANCE_CHECKLIST.md): migrations apply, DB-backed tests pass, replay session_001 matches golden, smoke_um790 passes, attribution shape stable, no duplicate signals/trades on restart.
