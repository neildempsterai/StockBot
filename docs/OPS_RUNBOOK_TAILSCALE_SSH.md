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
