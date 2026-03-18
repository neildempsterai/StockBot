# StockBot v0.1

Alpaca market data + paper trading, deployed to a MINISFORUM UM790 via Tailscale SSH. No public Docker/Postgres/Redis ports.

## Decisions (v0.1)

- **Alpaca** only: market data (IEX) and paper trading. Direct REST + WebSocket APIs; no Alpaca MCP.
- **One market-data connection** in `alpaca_market_gateway`; fan-out via Redis streams.
- **Separate trade gateway** for paper `trade_updates` (binary frames).
- **REST** used for cold start, reconnect recovery, and reconciliation only.
- **client_order_id = signal_uuid** on every order (idempotency).
- **Internal fill ledger** is canonical; Alpaca `avg_entry_price` is informational (BOD sync can change it).
- **Regular hours only**; no extended/overnight in v0.1.
- **Deploy**: Docker context over SSH to UM790; no Docker TCP port.

See [docs/ARCH_INTEGRATION_ALPACA_TAILSCALE.md](docs/ARCH_INTEGRATION_ALPACA_TAILSCALE.md) and [docs/OPS_RUNBOOK_TAILSCALE_SSH.md](docs/OPS_RUNBOOK_TAILSCALE_SSH.md).

## Strategy (v0.1)

- **INTRA_EVENT_MOMO / 0.1.0**: shadow-only; entry 09:35–11:30 ET, force flat 15:45 ET; one trade max per symbol per day. Optional Scrappy intelligence gating: `SCRAPPY_MODE=off | advisory | required` (default advisory). See `docs/STRATEGY_CATALOG.md` and `docs/SCRAPPY_INTEGRATION.md`.

## Run locally

```bash
# Optional: create venv and install
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

# Lint and type-check
.venv/bin/ruff check src tests
.venv/bin/mypy src

# Tests (set env for any test that loads config)
export ALPACA_API_KEY_ID=dummy ALPACA_API_SECRET_KEY=dummy
export DATABASE_URL=postgresql+asyncpg://u:p@localhost/db
export REDIS_URL=redis://localhost:6379/0
.venv/bin/pytest tests -v

# Strategy env (optional): STOCKBOT_UNIVERSE, SHADOW_SLIPPAGE_BPS, SHADOW_FEE_PER_SHARE, ENTRY_START_ET, ENTRY_END_ET, FORCE_FLAT_ET

# Compose config (requires POSTGRES_PASSWORD and Alpaca keys in env or .env)
POSTGRES_PASSWORD=secret ALPACA_API_KEY_ID=key ALPACA_API_SECRET_KEY=secret \
  docker compose -f infra/compose.yaml config

# DB-backed tests (Postgres + Redis; expose ports first)
docker compose -f infra/compose.yaml -f infra/compose.test.yaml up -d postgres redis
export DATABASE_URL=postgresql+asyncpg://stockbot:PASSWORD@localhost:5432/stockbot REDIS_URL=redis://localhost:6379/0
pytest tests/test_scrappy_*.py tests/test_worker_scrappy_e2e.py tests/test_api_intelligence_db.py tests/test_signal_attribution_e2e.py -v

# Deterministic replay (same env; release gate)
make replay
# Or: PYTHONPATH=.:src python scripts/run_replay.py --session replay/session_001
# Replay requires clean validation DB (signals, shadow_trades, scrappy_gate_rejections, symbol_intelligence_snapshots empty).
# Release gate runs scripts/reset_validation_state.py before DB tests and before replay. For ad-hoc replay after other tests:
#   python scripts/run_replay.py --reset-state --session replay/session_001
# Or override: --allow-dirty (not deterministic). To refresh golden: --output actual.json, review diff, copy to expected_outputs.json, document in DECISION_LOG.md.
# Compare two outputs: python scripts/replay_diff.py actual.json expected_outputs.json

# Release gate — Docker-native (preferred; no host venv)
make release-gate-docker
# Starts postgres + redis if needed, runs migrations, resets validation state (signals/shadow_trades/scrappy_gate_rejections/symbol_intelligence_snapshots), DB tests, reset again, replay inside validate container, writes report to artifacts/release_gate/. Requires: Docker, POSTGRES_PASSWORD (default stockbot), optional ALPACA keys (dummy OK). Isolated state per run so replay is deterministic.

# If buildx has permission issues: use classic docker build (no buildx)
make release-gate-docker-classic
# Builds validate image with `docker build`, then runs the gate in that container on the same network as postgres/redis.

# Release gate — local (requires venv + Postgres + Redis)
docker compose -f infra/compose.yaml -f infra/compose.test.yaml up -d postgres redis
export DATABASE_URL=postgresql+asyncpg://stockbot:${POSTGRES_PASSWORD:-stockbot}@localhost:5432/stockbot REDIS_URL=redis://localhost:6379/0
make release-gate
# Reports: artifacts/release_gate/report_YYYYMMDD_HHMMSS.json and .md. Pass = exit 0; fail = first failing step.

# UM790: run gate then smoke (after deploy)
make release-gate-um790   # local gate + smoke_um790
# Or on UM790 host: use docker context um790 and run smoke_um790 after deploy.

make smoke-um790
# Or: ./scripts/smoke_um790.sh
```

## Deploy to UM790 (Tailscale SSH)

```bash
./scripts/docker_context_um790.sh <linux-user> <tailscale-hostname>
# Then from repo root:
docker --context um790 compose -f infra/compose.yaml up -d --build
```

**Staging smoke run:** After deploy, run `./scripts/smoke_um790.sh` (requires `POSTGRES_PASSWORD`, `ALPACA_API_KEY_ID`, `ALPACA_API_SECRET_KEY`). Pass = /health, /v1/intelligence/summary, /v1/metrics/summary return 200; fail = non-zero exit and recent logs printed.

See [docs/OPS_RUNBOOK_TAILSCALE_SSH.md](docs/OPS_RUNBOOK_TAILSCALE_SSH.md) for restart/rollback and no-public-port policy.
