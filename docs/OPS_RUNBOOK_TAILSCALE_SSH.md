# Ops Runbook: Tailscale SSH Deploy

SSH-only deploy, Docker context setup, restart/rollback, and no-public-port policy.

## Prerequisites

- Tailscale installed on laptop and on UM790; both on same tailnet.
- SSH access to UM790 via Tailscale (e.g. `ssh user@um790` or `ssh user@<tailscale-hostname>`).
- Docker installed on UM790.

## Docker context (no public Docker port)

Create a context that uses SSH to talk to the daemon on the UM790:

```bash
docker context create um790 --docker "host=ssh://<linux-user>@<tailscale-hostname>"
docker context use um790
```

Replace `<linux-user>` and `<tailscale-hostname>` with your UM790 SSH user and Tailscale machine name (e.g. `neil@um790`).

Or use the helper script from repo root:

```bash
./scripts/docker_context_um790.sh <linux-user> <tailscale-hostname>
# Or set DOCKER_UM790_USER and DOCKER_UM790_HOST
```

## Deploy

From the repo root (on your laptop):

```bash
docker --context um790 compose -f infra/compose.yaml up -d --build
```

## Verify

```bash
docker --context um790 ps
docker --context um790 compose -f infra/compose.yaml ps
```

No Docker TCP listener should be exposed on the UM790; all control is over SSH.

## Staging smoke run

From repo root (laptop), after deploy:

```bash
export POSTGRES_PASSWORD=... ALPACA_API_KEY_ID=... ALPACA_API_SECRET_KEY=...
./scripts/smoke_um790.sh
```

The script checks that context `um790` exists, brings up the stack, waits for the API, then hits `/health`, `/v1/intelligence/summary`, and `/v1/metrics/summary`. It prints recent API and worker logs. **Pass** = exit 0; **Fail** = exit non-zero and logs are printed. Migrations must be run before first deploy (e.g. run `alembic upgrade head` from a host that can reach the deployment Postgres, or run a one-off container with the app and alembic).

## Release acceptance

Before cutting a release or merging to main, run the release gate and satisfy [RELEASE_ACCEPTANCE_CHECKLIST.md](RELEASE_ACCEPTANCE_CHECKLIST.md):

- **Docker-native (recommended)**: From repo root, run `make release-gate-docker`. No host venv; starts Postgres/Redis if needed, runs the gate in the `validate` container, writes report to `artifacts/release_gate/`.
- **On UM790**: After deploy, run smoke with `make smoke-um790` (or `./scripts/smoke_um790.sh`). To run the full gate on the UM790 and store the report there, use the same docker context: bring up postgres/redis, then run the validate container with the repo mounted (e.g. from the machine that has the repo and docker context `um790`, run `make release-gate-docker` with context set to um790 for compose — or run the gate locally and then deploy).
- **Required env**: For Docker gate: `POSTGRES_PASSWORD` (default `stockbot`). For smoke: `POSTGRES_PASSWORD`, `ALPACA_API_KEY_ID`, `ALPACA_API_SECRET_KEY`.
- **Report files**: `artifacts/release_gate/report_*.json` and `*.md`; pass = `release_gate_pass: true` and exit 0.
- **What blocks release**: Migrations fail, DB-backed tests fail, replay session_001 does not match golden outputs, or smoke fails when run.

## Restart / rollback

Restart all:

```bash
docker --context um790 compose -f infra/compose.yaml restart
```

Restart a single service:

```bash
docker --context um790 compose -f infra/compose.yaml restart alpaca_market_gateway
```

Rollback to previous image (after tagging a known-good image):

```bash
docker --context um790 compose -f infra/compose.yaml pull
# Edit compose to use previous tag if needed, then:
docker --context um790 compose -f infra/compose.yaml up -d
```

## No-public-port policy

- Do **not** bind Docker daemon to `tcp://0.0.0.0:2375` or similar. Docker warns that exposing the daemon remotely can enable unauthorized root-level access.
- Do **not** publish Postgres or Redis to the host; they are internal only.
- Admin UI: bind to localhost or access via SSH tunnel (e.g. `ssh -L 8080:localhost:8080 user@um790`).

## Access control

- Tailnet policy should allow only intended users to SSH to the UM790. Tailscale is deny-by-default and policy-driven; configure in Tailscale admin (ACLs / SSH).
