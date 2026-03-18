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

- **INTRA_EVENT_MOMO / 0.1.0**: shadow-only; entry 09:35–11:30 ET, force flat 15:45 ET; one trade max per symbol per day. See `docs/STRATEGY_CATALOG.md`.

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
```

## Deploy to UM790 (Tailscale SSH)

```bash
./scripts/docker_context_um790.sh <linux-user> <tailscale-hostname>
# Then from repo root:
docker --context um790 compose -f infra/compose.yaml up -d --build
```

See [docs/OPS_RUNBOOK_TAILSCALE_SSH.md](docs/OPS_RUNBOOK_TAILSCALE_SSH.md) for restart/rollback and no-public-port policy.
