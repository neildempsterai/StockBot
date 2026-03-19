# Runtime Truth Audit (Repo-Only)

This document describes what is currently implemented in this repository and runtime stack. It does not describe planned behavior as if it already exists.

## 1) Compose Services (Current)

Defined in `infra/compose.yaml`:

- `postgres`: primary relational store for ledger, scanner/opportunity rows, intelligence, reconciler logs
- `redis`: stream fan-out and runtime coordination keys
- `alpaca_market_gateway`: Alpaca data websocket + snapshot/backfill fan-out into Redis streams
- `alpaca_trade_gateway`: Alpaca `trade_updates` ingestion into DB ledger
- `alpaca_reconciler`: reconciliation of broker/account/order state into DB
- `api`: FastAPI backend
- `worker`: strategy runtime (`INTRA_EVENT_MOMO` `0.1.0`) consuming Redis streams
- `scheduler`: simple daily reset loop for `traded_today` key
- `scanner`: scanner + publish top candidates
- `scrappy_auto`: autonomous Scrappy enrichment runner
- `ui`: React operator console served by nginx

## 2) Real API Routes Exposed Now

### Core API routes (`src/api/main.py`)

- `GET /health`
- `GET /health/detail`
- `GET /v1/config`
- `GET /v1/runtime/status`
- `GET /v1/backtest/status`
- `GET /v1/strategies`
- `GET /v1/signals`
- `GET /v1/signals/{signal_uuid}`
- `POST /v1/signals` (manual/test-only payload echo; does not place order)
- `GET /v1/intelligence/latest`
- `GET /v1/intelligence/recent`
- `GET /v1/intelligence/summary`
- `GET /v1/shadow/trades`
- `GET /v1/account`
- `GET /v1/account/status`
- `GET /v1/positions`
- `GET /v1/positions/{symbol_or_asset_id}`
- `GET /v1/orders`
- `GET /v1/orders/{order_id}`
- `GET /v1/clock`
- `GET /v1/calendar`
- `GET /v1/movers`
- `GET /v1/assets`
- `GET /v1/portfolio/history`
- `GET /v1/account/activities`
- `GET /v1/account/history`
- `GET /v1/trades/paper`
- `GET /v1/portfolio/compare-books`
- `GET /v1/paper/test/status`
- `GET /v1/paper/test/proof`
- `POST /v1/paper/test/buy-open`
- `POST /v1/paper/test/sell-close`
- `POST /v1/paper/test/short-open`
- `POST /v1/paper/test/buy-cover`
- `POST /v1/paper/test/flatten-all`
- `POST /v1/paper/test/cancel-all`
- `GET /v1/metrics/summary`
- `GET /v1/metrics/compare-scrappy-modes`
- `GET /v1/ai-referee/recent`
- `GET /v1/ai-referee/{assessment_id}`
- `GET /v1/metrics/compare-ai-referee`
- `GET /v1/system/health`
- `GET /v1/system/reconciliation`
- `POST /v1/system/reconcile-now`
- `POST /v1/scanner/run/now`
- `GET /v1/scanner/runs`
- `GET /v1/scanner/runs/{run_id}`
- `GET /v1/scanner/candidates`
- `GET /v1/scanner/top`
- `GET /v1/scanner/symbol/{symbol}`
- `GET /v1/scanner/summary`
- `POST /v1/scanner/run/historical`
- `POST /v1/opportunities/run/now`
- `GET /v1/opportunities/now`
- `GET /v1/opportunities/summary`
- `GET /v1/opportunities/session`
- `GET /v1/opportunities/symbol/{symbol}`
- `GET /v1/opportunities/history`
- `POST /v1/scrappy/auto-run/now`
- `GET /v1/scrappy/status`
- `GET /v1/scrappy/auto-runs`
- `POST /v1/backtests/run`
- `GET /v1/backtests`
- `GET /v1/backtests/{run_id}`
- `GET /v1/backtests/{run_id}/trades`
- `GET /v1/backtests/{run_id}/summary`

### Scrappy router routes (`src/stockbot/scrappy/api.py`, mounted on `/scrappy`)

- `GET /scrappy/health`
- `GET /scrappy/telemetry`
- `GET /scrappy/sources/health`
- `GET /scrappy/audit`
- `GET /scrappy/notes/recent`
- `POST /scrappy/run`
- `GET /scrappy/watchlist`
- `POST /scrappy/watchlist`
- `POST /scrappy/run/watchlist`
- `POST /scrappy/run/symbol/{symbol}`

## 3) Placeholder / Scaffold Components (Current)

- `src/scheduler/main.py`: minimal scheduler; only clears `stockbot:strategies:intra_event_momo:traded_today` at 04:00 ET
- `src/ui/main.py`: minimal Starlette admin proxy (text/json endpoints), separate from React UI
- `GET /v1/backtest/status`: explicitly reports REST trigger for replay is planned (not implemented)
- `POST /v1/signals`: manual/test-only response, no order placement

## 4) Runtime Dependencies (Current)

- Docker + Docker Compose
- Postgres 16 (`postgres`)
- Redis 7 (`redis`)
- Alpaca paper trading/data credentials (`ALPACA_API_KEY_ID`, `ALPACA_API_SECRET_KEY`)
- Alpaca data websocket + trading websocket
- Python services under `src/`
- Frontend build/runtime (`frontend/Dockerfile` + nginx)

## 5) Mode Limitations (Current)

- Strategy authority is only `INTRA_EVENT_MOMO` `0.1.0` in worker
- Feed is constrained to `iex` by config typing (`feed: Literal["iex"]`)
- Extended-hours global mode defaults disabled and remains limited by current strategy/session logic
- Scheduler is not a full orchestrator (daily reset loop only)
- Dynamic symbol universe now depends on Redis top symbols freshness; stale or missing dynamic list falls back to static env symbols
- Paper execution is conditional on credentials + runtime services, and remains separated from shadow trade ledger concepts
- UI is operator-facing and reads backend state; no separate mock-mode truth endpoint exists

## 6) Runtime Validation Path (Repo-Owned)

Use `make runtime-truth-validate` (or `bash scripts/runtime_truth_validate.sh`) to run:

1. compose config validation
2. migration upgrade command
3. stack startup
4. smoke checks for key API truth endpoints
5. pass/fail checklist summary

Log collection command is printed by the script for manual capture.
