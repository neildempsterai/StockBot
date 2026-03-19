# StockBot Runtime & Paper Lifecycle Validation Runbook

Repo-only source of truth. No mock UI. Paper and shadow books are strictly separate.

## Repo-grounded status

- **Primary path:** Full-stack validation is repo-native. The repo contains `infra/compose.yaml` and `alembic.ini`. The validation script uses `docker compose -f infra/compose.yaml -p infra` for config, migrations, and stack startup — no optional wrappers required.
- **Secondary path:** External API-only validation: set `API_ONLY=1` and `BASE_URL` to validate only HTTP endpoints against an already-running API (e.g. on another host).
- **Live paper proof:** Separate executable, gated path; see "Live paper lifecycle validation" below. Requires Alpaca paper credentials and explicit opt-in.

## What works / what does not (brutally honest)

| Area | Status | Notes |
|------|--------|-------|
| GET /health, /health/detail, /v1/config, /v1/runtime/status, /v1/system/health | Real | In repo; return real state or error. No fake success. |
| GET /v1/scanner/summary, /v1/opportunities/summary, /v1/scrappy/status | Real or honest empty | Depend on full stack (DB, Redis, services). When stack down or no data: empty or 503. |
| GET /v1/account, /v1/positions, /v1/orders | 200 with Alpaca data or 503 | Route exists. 503 when Alpaca not configured or trade gateway not running. |
| GET /v1/paper/test/status, /v1/paper/test/proof | Real | Distinguish: paper disabled, credentials missing, broker unavailable, broker connected no proof yet, proof partial/complete. No fake success. |
| POST /v1/paper/test/* | Real | Operator-only; submits to Alpaca paper. 503 if broker/gateway unavailable. |
| GET /v1/portfolio/compare-books, /v1/system/reconciliation | Real | Shadow vs paper; reconciliation result. Depend on DB and trade/reconciler services. |
| Stack startup / migrations | Repo-native | Require `infra/compose.yaml`, `alembic.ini`, `.env` (DATABASE_URL, etc.). If missing, use API_ONLY=1. |

**Blockers if validation fails:** (1) API not reachable — start stack or set BASE_URL. (2) 503 on account/orders — Alpaca credentials or trade gateway. (3) Full-stack path fails — ensure infra/compose.yaml and .env exist; run from repo root.

---

## Phase 1 — Runtime validation (order of execution)

**Primary: repo-native full-stack**

From repo root, with `infra/compose.yaml` and `.env` present:

| Step | Check | Command / criterion |
|------|--------|----------------------|
| 1 | Compose config | `docker compose -f infra/compose.yaml -p infra config --quiet` |
| 2 | Migrations | `docker compose -f infra/compose.yaml -p infra run --rm api python -m alembic -c alembic.ini upgrade head` |
| 3 | Stack startup | `docker compose -f infra/compose.yaml -p infra up -d postgres redis api worker scheduler alpaca_market_gateway alpaca_trade_gateway alpaca_reconciler scanner scrappy_auto ui` |
| 4 | GET /health | `curl -fsS "${BASE_URL:-http://localhost:8000}/health"` → `{"status":"ok"}` |
| 5 | GET /health/detail | api, database, redis, worker, gateway, symbol source; no fake success |
| 6 | GET /v1/config | FEED, PAPER_EXECUTION_E2E_SUPPORTED, etc. |
| 7 | GET /v1/runtime/status | strategy, market_data, symbol_source, paper_execution |
| 8 | GET /v1/system/health | Same as /health/detail |
| 9 | GET /v1/scanner/summary | Real last_run or honest empty |
| 10 | GET /v1/opportunities/summary | Real or honest none |
| 11 | GET /v1/scrappy/status | Real or honest none |
| 12 | GET /v1/account | 200 with Alpaca data or 503 with clear detail |
| 13 | GET /v1/paper/test/status | paper_enabled, state, account tradable, warnings |
| 14 | GET /v1/paper/test/proof | Last per intent or null |
| 15 | GET /v1/portfolio/compare-books | shadow vs paper |
| 16 | GET /v1/system/reconciliation | matched/mismatch or no_runs |

**Secondary: external API-only**

When you have an API already running elsewhere (or want to skip compose/migrate/up):

```bash
export API_ONLY=1
export BASE_URL=http://localhost:8000   # or https://your-api-host
./scripts/runtime_truth_validate.sh
```

Only HTTP checks run; compose and migrations are skipped.

---

## Phase 2 — Live paper lifecycle validation (gated, executable)

This is a **separate** path. It places real paper orders and must never run accidentally.

- **Gate:** Set `ENABLE_LIVE_PAPER_VALIDATION=1` and provide Alpaca paper credentials (e.g. in .env or ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY).
- **Script:** `scripts/paper_lifecycle_validate.sh` (see below). Contract tests remain in `tests/test_paper_lifecycle.py` (shape only; no live orders).

**Four flows verified:** BUY open long → SELL close long → SELL open short → BUY cover short.

After each flow the script checks: submission response; order in GET /v1/orders; fill in GET /v1/trades/paper; account/positions update; proof in GET /v1/paper/test/proof; compare-books truthful; shadow book unchanged; reconciliation visible.

**Evidence:** JSON artifacts written to `artifacts/paper_lifecycle_<timestamp>/`.

---

## Commands to run locally

**Full-stack runtime validation (repo-native):**

```bash
cd /path/to/StockBot
# Ensure .env has POSTGRES_PASSWORD, ALPACA_*, DATABASE_URL, REDIS_URL
make runtime-truth-validate
```

Or:

```bash
./scripts/runtime_truth_validate.sh
```

**API-only (no compose):**

```bash
export API_ONLY=1
export BASE_URL=http://localhost:8000
./scripts/runtime_truth_validate.sh
```

**Compose config only:**

```bash
make compose-config
# Or: docker compose -f infra/compose.yaml -p infra config --quiet
```

**Up infra (postgres, redis, migrations) then tests:**

```bash
make up-infra
# then
PYTHONPATH=.:src pytest tests -v --tb=short
```

**Live paper lifecycle (gated):**

```bash
export ENABLE_LIVE_PAPER_VALIDATION=1
export BASE_URL=http://localhost:8000
# Alpaca paper credentials in .env or ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY
./scripts/paper_lifecycle_validate.sh
```

---

## Commands to run on UM790

Same as local, from repo root:

1. **Full-stack validation:** `make runtime-truth-validate` or `./scripts/runtime_truth_validate.sh`
2. **API-only:** `API_ONLY=1 BASE_URL=http://localhost:8000 ./scripts/runtime_truth_validate.sh`
3. **Live paper (gated):** `ENABLE_LIVE_PAPER_VALIDATION=1 ./scripts/paper_lifecycle_validate.sh` (with Alpaca paper in .env)
4. **Log collection:** `docker compose -f infra/compose.yaml -p infra logs --tail=200 api worker alpaca_trade_gateway alpaca_reconciler > runtime_truth_logs.txt`

---

## Endpoint pass/fail (runtime truth)

| Endpoint | In repo | Pass criterion | Fake/demo? |
|----------|---------|----------------|------------|
| GET /health | Yes | status=ok | No |
| GET /health/detail | Yes | api/database/redis/symbol source truth | No |
| GET /v1/config | Yes | FEED, PAPER_EXECUTION_E2E_SUPPORTED, etc. | No |
| GET /v1/runtime/status | Yes | strategy, symbol_source, paper_execution | No |
| GET /v1/system/health | Yes | Same as health/detail | No |
| GET /v1/scanner/summary | Yes | Real last_run or empty | Honest |
| GET /v1/opportunities/summary | Yes | Real or none | Honest |
| GET /v1/scrappy/status | Yes | Real or empty | Honest |
| GET /v1/account, /v1/positions, /v1/orders | Yes | 200 or 503 | No |
| GET /v1/paper/test/status | Yes | state + paper_enabled, account tradable, warnings | No |
| GET /v1/paper/test/proof | Yes | Last per intent or null | No |
| POST /v1/paper/test/* | Yes | Submission result | No |
| GET /v1/portfolio/compare-books | Yes | shadow vs paper | No |
| GET /v1/system/reconciliation | Yes | matched/mismatch | No |

---

## Remaining gaps

- Full-stack validation requires Docker, `infra/compose.yaml`, and built images (or build step). If compose or images are missing, use API_ONLY=1.
- Live paper proof requires Alpaca paper account and running trade_gateway/reconciler; operator must run the gated script and review artifacts.
- Backtest: if implemented, /v1/backtest/status must be honest (no fake success).

---

## Files changed in this tranche

| File | Change |
|------|--------|
| `scripts/ensure_infra.sh` | **New.** Minimal wrapper: postgres + redis up, migrations via `docker compose -f infra/compose.yaml -p infra`. |
| `scripts/runtime_truth_validate.sh` | **Updated.** Primary path: repo-native full-stack (compose config, migrate, up, then HTTP). Secondary: `API_ONLY=1` for API-only. Migration failure logs last 20 lines. |
| `scripts/paper_lifecycle_validate.sh` | **New.** Gated live paper validation; requires `ENABLE_LIVE_PAPER_VALIDATION=1` and Alpaca credentials; four flows; writes JSON to `artifacts/paper_lifecycle_<timestamp>/`. |
| `docs/VALIDATION_RUNBOOK.md` | **Updated.** Primary/secondary/paper sections; repo-native commands; no “compose may not be in repo” framing. |
| `Makefile` | **Updated.** test-full runs `./scripts/ensure_infra.sh` (no source); compose-config checks infra/compose.yaml exists and uses `-p infra`; runtime-truth-validate comment. |
| `tests/test_paper_lifecycle.py` | **Updated.** Status shape test asserts `state` in allowed set. |
| `tests/test_validation_scripts.py` | **New.** Gating: paper script exit 2 without gate; credential/API failure; API_ONLY=1 skips compose. |
| `src/stockbot/execution/paper_test.py` | **Updated.** `get_paper_test_status()` returns `state`, `credentials_configured`, `broker_reachable`, `intents_with_proof`; state one of paper_disabled, credentials_missing, broker_unavailable, broker_connected_no_proof, proof_partial, proof_complete. |

---

## Repo-grounded summary

- **Entrypoints:** `scripts/compose.sh` remains the thin wrapper (load .env, `docker compose -f infra/compose.yaml -p infra`). `scripts/ensure_infra.sh` was added and uses the same repo-native compose/migration commands; Makefile `up-infra` and `test-full` use it.
- **Validation:** Primary path is repo-native: `docker compose -f infra/compose.yaml -p infra` for config, migrate, and up; then HTTP checks in fixed order. External API-only is explicit: `API_ONLY=1`; no implicit fallback from “compose.sh missing”.
- **Runbook:** Structured as primary (full-stack), secondary (API-only), and separate live paper lifecycle section. Honest about what depends on Alpaca/DB/services.
- **Live paper:** Executable gated path in `scripts/paper_lifecycle_validate.sh`; requires `ENABLE_LIVE_PAPER_VALIDATION=1` and Alpaca paper credentials; four flows; evidence to `artifacts/`. Contract tests stay in `tests/test_paper_lifecycle.py`; no fake integration success.
- **Paper status/proof:** `/v1/paper/test/status` now returns `state` and clearly distinguishes paper_disabled, credentials_missing, broker_unavailable, broker_connected_no_proof, proof_partial, proof_complete. No fake success.

---

## Commands to run locally

```bash
# Full-stack runtime validation (compose + migrate + up + HTTP)
make runtime-truth-validate
# or
./scripts/runtime_truth_validate.sh

# API-only (no compose)
API_ONLY=1 BASE_URL=http://localhost:8000 ./scripts/runtime_truth_validate.sh

# Compose config only
make compose-config

# Up infra (postgres, redis, migrations)
make up-infra

# Full test suite after up-infra
make test-full

# Live paper lifecycle (gated; real paper orders)
ENABLE_LIVE_PAPER_VALIDATION=1 ./scripts/paper_lifecycle_validate.sh
```

---

## Commands to run on UM790

Same as local, from repo root:

```bash
make runtime-truth-validate
# or API-only against existing API
API_ONLY=1 BASE_URL=http://localhost:8000 ./scripts/runtime_truth_validate.sh

ENABLE_LIVE_PAPER_VALIDATION=1 ./scripts/paper_lifecycle_validate.sh

docker compose -f infra/compose.yaml -p infra logs --tail=200 api worker alpaca_trade_gateway alpaca_reconciler > runtime_truth_logs.txt
```

---

## What definitely works now

- Full-stack validation runs from repo’s real compose/migration path (`docker compose -f infra/compose.yaml -p infra`); no phantom helpers.
- Makefile targets `runtime-truth-validate`, `compose-config`, `up-infra`, `test-full` point to existing scripts or direct commands.
- Runbook matches repo: primary = repo-native full-stack, secondary = API_ONLY=1.
- Paper lifecycle proof is executable and gated; contract tests and live validation are separate.
- `/v1/paper/test/status` returns truthful `state`; no fake operator success in validated surfaces.

---

## What is still unproven

- Full-stack validation end-to-end on a clean machine (Docker, images, .env) until run once.
- Live paper lifecycle script end-to-end with real Alpaca paper account and running trade_gateway/reconciler until operator runs it and reviews artifacts.
- Backtest routes if present; documented as honest in runbook.

---

## Remaining blockers

- None for repo-native validation path. For full-stack: need Docker, `infra/compose.yaml`, `.env`, and built images (or build step). For live paper: need Alpaca paper credentials and running stack.

---

## Example validation output

**Full-stack runtime validation (excerpt):**

```
==> Compose config validates
PASS: Compose config validates

==> Migrations upgrade head
PASS: Migrations upgrade head

==> Stack startup
PASS: Stack startup

==> GET /health
PASS: GET /health
...
Checklist: pass=16 fail=0
```

**API-only (excerpt):**

```
==> API-only mode (API_ONLY=1); skipping compose, migrations, and stack startup.

==> GET /health
PASS: GET /health
...
```

**Live paper lifecycle (gated; excerpt):**

```
[paper_lifecycle_validate] Evidence directory: /path/to/artifacts/paper_lifecycle_20260319T120000Z
==> 1. GET /v1/paper/test/status
==> 2. POST /v1/paper/test/buy-open (BUY open long)
  PASS: buy-open submission
...
==> Summary
  pass=4 fail=0
  Evidence: /path/to/artifacts/paper_lifecycle_20260319T120000Z
```

**Without gate:**

```
Live paper validation is disabled. Set ENABLE_LIVE_PAPER_VALIDATION=1 to run (places real paper orders).
# exit 2
```
