#!/usr/bin/env bash
# Bring up Postgres + Redis and run migrations. Repo-native: uses infra/compose.yaml and alembic.ini.
# Run from repo root: ./scripts/dev/ensure_infra.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
if [ ! -f "$ROOT/infra/compose.yaml" ]; then
  echo "[ensure_infra] infra/compose.yaml not found; cannot start infra." >&2
  exit 1
fi
# Load .env if present (same as compose.sh)
if [ -f "$ROOT/.env" ]; then
  _envsh=$(mktemp)
  python3 - "$ROOT" "$_envsh" << 'PY' || true
import sys
root = sys.argv[1]
out = open(sys.argv[2], 'w')
with open(root + '/.env') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            v = v.replace("'", "'\\''")
            out.write("export " + k.strip() + "='" + v + "'\n")
out.close()
PY
  [ -s "$_envsh" ] && . "$_envsh"
  rm -f "$_envsh"
fi
COMPOSE_CMD="docker compose -f $ROOT/infra/compose.yaml -p infra"
echo "[ensure_infra] Starting postgres and redis..."
$COMPOSE_CMD up -d postgres redis
echo "[ensure_infra] Waiting for postgres..."
until $COMPOSE_CMD exec -T postgres pg_isready -U "${POSTGRES_USER:-stockbot}" 2>/dev/null; do sleep 2; done
echo "[ensure_infra] Running migrations..."
$COMPOSE_CMD run --rm api python -m alembic -c alembic.ini upgrade head
echo "[ensure_infra] Done."
