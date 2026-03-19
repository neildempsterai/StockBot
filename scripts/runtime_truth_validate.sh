#!/usr/bin/env bash
# Runtime truth smoke validation for current repo behavior.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PASS=0
FAIL=0

check() {
  local label="$1"
  shift
  echo "==> ${label}"
  if "$@"; then
    echo "PASS: ${label}"
    PASS=$((PASS + 1))
  else
    echo "FAIL: ${label}"
    FAIL=$((FAIL + 1))
  fi
  echo
}

check "Compose config validates" ./scripts/compose.sh config --quiet
check "Migrations upgrade head" ./scripts/compose.sh run --rm api python -m alembic -c alembic.ini upgrade head
check "Stack startup" ./scripts/compose.sh up -d postgres redis api worker scheduler alpaca_market_gateway alpaca_trade_gateway alpaca_reconciler ui

check "GET /health" curl -fsS http://localhost:8000/health
check "GET /health/detail" curl -fsS http://localhost:8000/health/detail
check "GET /v1/config" curl -fsS http://localhost:8000/v1/config
check "GET /v1/runtime/status" curl -fsS http://localhost:8000/v1/runtime/status
check "GET /v1/system/health" curl -fsS http://localhost:8000/v1/system/health

echo "==> Log collection (manual)"
echo "./scripts/compose.sh logs --tail=200 api worker scanner alpaca_market_gateway alpaca_trade_gateway alpaca_reconciler scheduler ui > runtime_truth_logs.txt"
echo

echo "Checklist: pass=${PASS} fail=${FAIL}"
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
