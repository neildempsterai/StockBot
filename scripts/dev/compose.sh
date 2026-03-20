#!/usr/bin/env bash
# Run Docker Compose from repo root with .env loaded. Use: ./scripts/dev/compose.sh up -d
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
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
exec docker compose -f "$ROOT/infra/compose.yaml" -p infra "$@"
