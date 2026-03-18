#!/usr/bin/env bash
# Staging smoke run for UM790: context check, compose up, health + intelligence + metrics, logs.
# Run from repo root. Requires: docker context um790, POSTGRES_PASSWORD and Alpaca keys in env.
# Exit non-zero on failure.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
COMPOSE="-f infra/compose.yaml"
CONTEXT="${DOCKER_CONTEXT:-um790}"

if ! docker context inspect "$CONTEXT" &>/dev/null; then
  echo "Docker context '$CONTEXT' not found. Create with: ./scripts/docker_context_um790.sh <user> <host>" >&2
  exit 1
fi

echo "Using context: $CONTEXT"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD}"
export ALPACA_API_KEY_ID="${ALPACA_API_KEY_ID:?Set ALPACA_API_KEY_ID}"
export ALPACA_API_SECRET_KEY="${ALPACA_API_SECRET_KEY:?Set ALPACA_API_SECRET_KEY}"

echo "Bringing up stack..."
docker --context "$CONTEXT" compose $COMPOSE up -d --build

echo "Waiting for API..."
for i in 1 2 3 4 5 6 7 8 9 10; do
  if docker --context "$CONTEXT" compose $COMPOSE exec -T api python -c "
import urllib.request
try:
    u = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5)
    assert u.getcode() == 200
except Exception as e:
    raise SystemExit(1)
" 2>/dev/null; then
    break
  fi
  if [[ $i -eq 10 ]]; then
    echo "API did not become healthy" >&2
    docker --context "$CONTEXT" compose $COMPOSE logs api --tail 30
    exit 1
  fi
  sleep 3
done

echo "GET /health..."
docker --context "$CONTEXT" compose $COMPOSE exec -T api python -c "
import urllib.request, json
u = urllib.request.urlopen('http://127.0.0.1:8000/health')
d = json.loads(u.read())
assert d.get('status') == 'ok', d
print(d)
"

echo "GET /v1/intelligence/summary..."
docker --context "$CONTEXT" compose $COMPOSE exec -T api python -c "
import urllib.request, json
u = urllib.request.urlopen('http://127.0.0.1:8000/v1/intelligence/summary')
d = json.loads(u.read())
assert 'snapshots_total' in d
print('snapshots_total:', d.get('snapshots_total'))
"

echo "GET /v1/metrics/summary..."
docker --context "$CONTEXT" compose $COMPOSE exec -T api python -c "
import urllib.request, json
u = urllib.request.urlopen('http://127.0.0.1:8000/v1/metrics/summary')
d = json.loads(u.read())
assert 'signals_total' in d and 'scrappy_gate_rejections' in d
print('signals_total:', d.get('signals_total'))
"

echo "Recent API logs..."
docker --context "$CONTEXT" compose $COMPOSE logs api --tail 15

echo "Recent Worker logs..."
docker --context "$CONTEXT" compose $COMPOSE logs worker --tail 15

echo "Smoke OK."
