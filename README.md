# StockBot

Multi-strategy equity trading platform with deterministic strategy authority, paper/shadow execution, and full operator visibility.

## What this repo contains

A complete trading automation stack: market data ingestion, multi-strategy evaluation, paper order execution via Alpaca, lifecycle tracking, and an operator console for monitoring everything.

**Strategies are the sole trade authority.** Scrappy (research/intelligence) and AI Referee (assessment) are advisory only — they inform but never generate orders.

## Service map

| Service | Description |
|---------|-------------|
| **API** (`src/api/`) | FastAPI backend — signals, exposure, lifecycle, metrics, system health |
| **Worker** (`src/worker/`) | Strategy runtime — evaluates symbols, generates signals, manages positions |
| **Market Gateway** (`src/stockbot/gateways/market_gateway.py`) | Alpaca WebSocket — real-time quotes, trades, bars into Redis Streams |
| **Trade Gateway** (`src/stockbot/gateways/trade_gateway.py`) | Alpaca trade updates — fills, cancels, rejections into canonical ledger |
| **Reconciler** (`src/stockbot/gateways/reconciler.py`) | Periodic position/order reconciliation against broker |
| **Scanner** (`src/stockbot/scanner/`) | Universe scanning — scores candidates on liquidity, gap, spread, volume |
| **Scrappy** (`src/stockbot/scrappy/`) | AI research agent — catalyst/sentiment analysis (advisory only) |
| **AI Referee** (`src/stockbot/ai_referee/`) | Setup quality assessment (advisory only) |
| **Scheduler** (`src/scheduler/`) | Cron-like scheduler for scanner, scrappy auto-runs |
| **Frontend** (`frontend/`) | React operator console — Command Center, Portfolio, Premarket Prep, etc. |

## Strategies

| Strategy | Type | Description |
|----------|------|-------------|
| `INTRA_EVENT_MOMO / 0.1.0` | Intraday | Frozen baseline — event-driven momentum |
| `OPEN_DRIVE_MOMO / 0.1.0` | Intraday | Morning drive momentum |
| `INTRADAY_CONTINUATION / 0.1.0` | Intraday | Later-session continuation |
| `SWING_EVENT_CONTINUATION / 0.1.0` | Swing (1-5d) | Multi-day event follow-through (shadow only) |

## Repo layout

```
src/
  api/              FastAPI application
  worker/           Strategy runtime
  scheduler/        Cron scheduler
  stockbot/         Core library
    strategies/     Strategy definitions + router
    gateways/       Market/trade/reconciliation gateways
    scanner/        Universe scanner
    opportunities/  Opportunity engine
    scrappy/        AI research (Scrappy)
    ai_referee/     AI setup assessor
    risk/           Sizing and risk checks
    db/             SQLAlchemy models + engine
    ledger/         Signal/fill/lifecycle persistence
    shadow/         Shadow position engine
    alpaca/         Alpaca API client
    config.py       All configuration (env-driven)

frontend/           React + Vite operator console
  src/pages/        Page components
  src/components/   Shared UI components
  src/api/          API client + endpoints
  src/types/        TypeScript interfaces

infra/              Docker Compose + Dockerfiles + nginx config
tests/              Pytest suite
scripts/
  validation/       Runtime/lifecycle/premarket validation scripts
  dev/              Infrastructure setup (compose, ensure_infra)
  ops/              Deployment (entrypoint, sync)
docs/
  architecture/     System design docs
  runbooks/         Operator procedures
  status/           Current implementation status
  archive/          Historical tranches and audits
```

## Quick start

```bash
# 1. Copy and configure environment
cp .env.example .env   # fill in ALPACA_API_KEY_ID, ALPACA_API_SECRET_KEY, POSTGRES_PASSWORD, OPENAI_API_KEY

# 2. Start infrastructure + all services
cd infra && docker compose --env-file ../.env up -d --build

# 3. Verify
curl http://localhost:8000/health          # API
open http://localhost:8080                  # UI
```

## Common commands

```bash
make up-infra                # Start postgres + redis, run migrations
make test                    # Run tests in Docker (no local venv needed)
make test-full               # Start infra, then run full test suite
make lint                    # Lint + format + type-check
make runtime-truth-validate  # Full-stack runtime validation
make premarket-validate      # Premarket activation validation
```

## Key docs

- [Multi-Strategy Architecture](docs/architecture/MULTI_STRATEGY_IMPLEMENTATION.md)
- [Intelligence & AI Referee](docs/architecture/INTELLIGENCE_AND_AI_REFEREE.md)
- [Paper Trading Runbook](docs/runbooks/PAPER_OPERATOR_RUNBOOK.md)
- [Premarket Runbook](docs/runbooks/PREMARKET_OPERATOR_RUNBOOK.md)
- [Validation Runbook](docs/runbooks/VALIDATION_RUNBOOK.md)
- [Implementation Status](docs/status/IMPLEMENTATION_STATUS.md)

## Safety defaults

- All strategies default to **shadow-only** (no real orders)
- Paper trading requires explicit arming via `/v1/paper/arm`
- Swing strategies require separate `STRATEGY_SWING_EVENT_CONTINUATION_PAPER_ENABLED=true`
- Static fallback symbols block paper trading
- Arming prerequisites enforce broker connectivity, account state, and dynamic universe freshness
