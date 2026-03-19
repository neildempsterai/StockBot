# StockBot Runtime & Paper Lifecycle Validation Runbook

Repo-only source of truth. No mock UI. Paper and shadow books are strictly separate.

## Repo-grounded status after validation

- **Definitely works (from repo):** GET /health, /health/detail, /v1/config, /v1/runtime/status, /v1/system/health; POST /v1/paper/test/* routes and GET /v1/paper/test/status, /v1/paper/test/proof (when API and deps are present). Validation script runs in API-only mode when `scripts/compose.sh` is missing.
- **Partially works:** Scanner, opportunities, scrappy, account/orders/positions — depend on full stack (DB, Redis, Alpaca, services). Return real data when stack is up; 503 or honest empty when not.
- **Broken / unproven until run:** Stack startup and migrations (require infra/compose in repo or on UM790). Paper lifecycle proof (requires Alpaca paper account and trade_gateway/reconciler; evidence table must be filled by operator).
- **Exact blockers if validation fails:** (1) API not reachable at BASE_URL — start stack or set BASE_URL. (2) 503 on account/orders — Alpaca not configured or trade gateway not running. (3) Compose steps skipped — add infra/compose on UM790 or run API elsewhere.

## Scope

- **Phase 1:** Runtime validation of the actual stack (compose, migrations, API endpoints, scanner/opportunities/scrappy, dynamic universe, account/orders/positions, backtest).
- **Phase 2:** Paper execution lifecycle proof for all four flows: BUY open long, SELL close long, SELL open short, BUY cover short.

## Prerequisites

- **Full stack:** On UM790 (or wherever the full StockBot tree lives), you need: `infra/compose.yaml`, `scripts/compose.sh`, migrations (e.g. alembic), `.env` with `ALPACA_API_KEY_ID`, `ALPACA_API_SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`. If these are not in the repo, runtime validation runs in **API-only mode** (see below).
- **API-only mode:** Validation script can run against an already-running API by setting `BASE_URL` (default `http://localhost:8000`). Compose/migration steps are skipped when `./scripts/compose.sh` is not present.

---

## Phase 1 — Runtime validation (order of execution)

| Step | Check | Command / criterion |
|------|--------|----------------------|
| 1 | Compose config | `./scripts/compose.sh config --quiet` (skip if compose.sh missing) |
| 2 | Migrations | `./scripts/compose.sh run --rm api python -m alembic -c alembic.ini upgrade head` (skip if compose.sh missing) |
| 3 | Stack startup | `./scripts/compose.sh up -d postgres redis api worker scheduler alpaca_market_gateway alpaca_trade_gateway alpaca_reconciler ui` (skip if compose.sh missing) |
| 4 | GET /health | `curl -fsS "${BASE_URL:-http://localhost:8000}/health"` → `{"status":"ok"}` |
| 5 | GET /health/detail | `curl -fsS "${BASE_URL:-http://localhost:8000}/health/detail"` → api, database, redis, worker, gateway, symbol source fields; no fake success |
| 6 | GET /v1/config | `curl -fsS "${BASE_URL:-http://localhost:8000}/v1/config"` → FEED, EXTENDED_HOURS_ENABLED, PAPER_EXECUTION_E2E_SUPPORTED, etc. |
| 7 | GET /v1/runtime/status | `curl -fsS "${BASE_URL:-http://localhost:8000}/v1/runtime/status"` → strategy, market_data, symbol_source (gateway/worker), paper_execution |
| 8 | GET /v1/system/health | Same as /health/detail (alias) |
| 9 | Scanner live | GET /v1/scanner/summary and/or /v1/scanner/runs — real DB/Redis data or explicit empty/not-available |
| 10 | Opportunities | GET /v1/opportunities/summary, /v1/opportunities/now — real or honest none |
| 11 | Scrappy | GET /v1/scrappy/status, /v1/scrappy/auto-runs — real or honest none |
| 12 | Dynamic universe | From /health/detail or /v1/runtime/status: gateway_symbol_source, worker_universe_source, fallback_reason |
| 13 | Account/orders/positions | GET /v1/account, /v1/account/status, /v1/positions, /v1/orders — 200 with Alpaca data or 503 with clear detail |
| 14 | Backtest | GET /v1/backtest/status; POST /v1/backtests/run and GET /v1/backtests if implemented — honest availability |

If a route is **not in the repo** (see `src/api/main.py` and `src/stockbot/scrappy/api.py`), do not invent it; mark as "not in repo".

---

## Phase 2 — Paper execution lifecycle proof

For each flow, verify using **exact repo routes** (no assumed endpoints):

| Flow | Submit | Broker status / fills | Internal persistence | Account / positions / orders / activities | Compare-books / reconciliation | Shadow separation |
|------|--------|------------------------|----------------------|--------------------------------------------|---------------------------------|--------------------|
| **BUY open long** | POST /v1/paper/test/buy-open | Alpaca order status/fills | paper_orders + trade_updates → fills | GET /v1/account, /v1/positions, /v1/orders, /v1/account/activities | GET /v1/portfolio/compare-books; GET /v1/system/reconciliation | Shadow book unchanged |
| **SELL close long** | POST /v1/paper/test/sell-close | Alpaca order status/fills | Same | Same | Same | Shadow book unchanged |
| **SELL open short** | POST /v1/paper/test/short-open | Alpaca order status/fills | Same | Same | Same | Shadow book unchanged |
| **BUY cover short** | POST /v1/paper/test/buy-cover | Alpaca order status/fills | Same | Same | Same | Shadow book unchanged |

### Repo routes used (no invented routes)

- **Submit:** POST /v1/paper/test/buy-open, sell-close, short-open, buy-cover (Body: symbol, qty, order_type, limit_price, extended_hours, note).
- **Status/proof:** GET /v1/paper/test/status, GET /v1/paper/test/proof (last operator-test order per intent).
- **Broker truth:** GET /v1/account, /v1/account/status, /v1/positions, /v1/orders, /v1/orders/{id}, /v1/account/activities.
- **Internal ledger:** GET /v1/trades/paper (paper fills from DB), /v1/account/history (snapshots).
- **Separation:** GET /v1/shadow/trades (shadow only); GET /v1/portfolio/compare-books (paper vs shadow counts/PnL); GET /v1/system/reconciliation.

### Evidence table (fill after run)

| Flow | Submitted (200) | Order in /v1/orders | Fill in /v1/trades/paper | Account/positions updated | Proof in /v1/paper/test/proof | Notes |
|------|-----------------|---------------------|--------------------------|----------------------------|-------------------------------|-------|
| BUY open long | ☐ | ☐ | ☐ | ☐ | ☐ | |
| SELL close long | ☐ | ☐ | ☐ | ☐ | ☐ | |
| SELL open short | ☐ | ☐ | ☐ | ☐ | ☐ | |
| BUY cover short | ☐ | ☐ | ☐ | ☐ | ☐ | |

---

## Endpoint pass/fail (runtime truth only)

| Endpoint | In repo | Pass criterion | Fake/demo? |
|----------|---------|-----------------|------------|
| GET /health | Yes | status=ok | No |
| GET /health/detail | Yes | api/database/redis/symbol source truth | Must be real or error |
| GET /v1/config | Yes | FEED, PAPER_EXECUTION_E2E_SUPPORTED, etc. | No |
| GET /v1/runtime/status | Yes | strategy, symbol_source, paper_execution | No |
| GET /v1/system/health | Yes | Same as health/detail | No |
| GET /v1/scanner/summary | Yes | Real last_run or empty | Honest |
| GET /v1/opportunities/summary | Yes | Real run_id/source or none | Honest |
| GET /v1/scrappy/status | Yes | Real last_run or empty | Honest |
| GET /v1/account, /v1/positions, /v1/orders | Yes | 200 with Alpaca data or 503 | No |
| GET /v1/paper/test/status | Yes | paper_enabled, account tradable, warnings | No |
| GET /v1/paper/test/proof | Yes | Last per intent or null | No |
| POST /v1/paper/test/* | Yes | Order submission result | No |
| GET /v1/portfolio/compare-books | Yes | shadow vs paper counts | No |
| GET /v1/system/reconciliation | Yes | orders/positions matched/mismatch | No |
| GET /v1/backtest/status | Yes | Honest available/message | Honest |

---

## Commands Neil should run on UM790

1. **From repo root (full stack assumed):**
   ```bash
   cd /path/to/StockBot
   export BASE_URL=http://localhost:8000   # optional if API on same host
   make runtime-truth-validate
   ```
   Or run the script directly:
   ```bash
   ./scripts/runtime_truth_validate.sh
   ```
   If `./scripts/compose.sh` exists and infra is present:
   - Script will validate compose config, run migrations, start stack, then hit API.
   If not (API-only mode):
   - Script skips compose/migrate/up and only runs HTTP checks against `BASE_URL`.

2. **Paper lifecycle (manual proof):**
   ```bash
   # 1) Status
   curl -sS "${BASE_URL:-http://localhost:8000}/v1/paper/test/status" | jq .

   # 2) BUY open long (e.g. 1 share AAPL)
   curl -sS -X POST "${BASE_URL:-http://localhost:8000}/v1/paper/test/buy-open" \
     -H "Content-Type: application/json" -d '{"symbol":"AAPL","qty":1,"order_type":"market"}' | jq .

   # 3) Verify order and positions
   curl -sS "${BASE_URL:-http://localhost:8000}/v1/orders?status=open" | jq .
   curl -sS "${BASE_URL:-http://localhost:8000}/v1/positions" | jq .

   # 4) SELL close long
   curl -sS -X POST "${BASE_URL:-http://localhost:8000}/v1/paper/test/sell-close" \
     -H "Content-Type: application/json" -d '{"symbol":"AAPL","qty":1,"order_type":"market"}' | jq .

   # 5) SELL open short
   curl -sS -X POST "${BASE_URL:-http://localhost:8000}/v1/paper/test/short-open" \
     -H "Content-Type: application/json" -d '{"symbol":"AAPL","qty":1,"order_type":"market"}' | jq .

   # 6) BUY cover short
   curl -sS -X POST "${BASE_URL:-http://localhost:8000}/v1/paper/test/buy-cover" \
     -H "Content-Type: application/json" -d '{"symbol":"AAPL","qty":1,"order_type":"market"}' | jq .

   # 7) Proof and compare-books
   curl -sS "${BASE_URL:-http://localhost:8000}/v1/paper/test/proof" | jq .
   curl -sS "${BASE_URL:-http://localhost:8000}/v1/portfolio/compare-books" | jq .
   curl -sS "${BASE_URL:-http://localhost:8000}/v1/system/reconciliation" | jq .
   ```

3. **Log collection:**
   ```bash
   ./scripts/compose.sh logs --tail=200 api worker alpaca_trade_gateway alpaca_reconciler > runtime_truth_logs.txt
   ```

---

## Remaining gaps after this tranche

- Runtime validation depends on full stack (compose, migrations, all services). If repo does not include infra/compose, validation is API-only until the full tree is present on UM790.
- Paper lifecycle proof requires Alpaca paper account and running trade_gateway/reconciler; evidence table must be filled by operator run.
- Backtest trigger/status may remain partially implemented (replay path); document in /v1/backtest/status and do not return fake success.

---

## Exact files changed in this tranche

- `docs/VALIDATION_RUNBOOK.md` — added (runbook, endpoint table, paper lifecycle table, UM790 commands).
- `scripts/runtime_truth_validate.sh` — updated (API-only mode when compose.sh missing; BASE_URL; scanner/opportunities/scrappy/account/proof/compare-books/reconciliation checks).
- `tests/test_paper_lifecycle.py` — added (paper status/proof shapes, four-flow route acceptance, compare-books/reconciliation shape; skipped when api.main not loadable).
