#!/usr/bin/env bash
# Runtime truth validation: stack (if present) + API endpoints.
# On UM790 with full stack: set BASE_URL or leave default; compose steps run if ./scripts/compose.sh exists.
# API-only mode: when compose.sh is missing, only HTTP checks run against BASE_URL (default http://localhost:8000).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BASE_URL="${BASE_URL:-http://localhost:8000}"
COMPOSE_SH="${ROOT}/scripts/compose.sh"
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

# Optional: compose config
if [ -x "$COMPOSE_SH" ]; then
  check "Compose config validates" "$COMPOSE_SH" config --quiet
  check "Migrations upgrade head" "$COMPOSE_SH" run --rm api python -m alembic -c alembic.ini upgrade head
  check "Stack startup" "$COMPOSE_SH" up -d postgres redis api worker scheduler alpaca_market_gateway alpaca_trade_gateway alpaca_reconciler ui
else
  echo "==> Skipping compose/migrate/up (compose.sh not found); API-only mode."
  echo
fi

# Required: API endpoints (real truth, no fake values)
check "GET /health" curl -fsS --connect-timeout 5 "${BASE_URL}/health"
check "GET /health/detail" curl -fsS --connect-timeout 5 "${BASE_URL}/health/detail"
check "GET /v1/config" curl -fsS --connect-timeout 5 "${BASE_URL}/v1/config"
check "GET /v1/runtime/status" curl -fsS --connect-timeout 5 "${BASE_URL}/v1/runtime/status"
check "GET /v1/system/health" curl -fsS --connect-timeout 5 "${BASE_URL}/v1/system/health"

# Scanner / opportunities / scrappy (honest empty or data)
check "GET /v1/scanner/summary" curl -fsS --connect-timeout 5 "${BASE_URL}/v1/scanner/summary"
check "GET /v1/opportunities/summary" curl -fsS --connect-timeout 5 "${BASE_URL}/v1/opportunities/summary"
check "GET /v1/scrappy/status" curl -fsS --connect-timeout 5 "${BASE_URL}/v1/scrappy/status"

# Account/orders/positions (200 or 503 with clear detail)
check "GET /v1/account or 503" curl -fsS --connect-timeout 5 -o /dev/null -w "%{http_code}" "${BASE_URL}/v1/account" | grep -qE '^(200|503)$'
check "GET /v1/paper/test/status" curl -fsS --connect-timeout 5 "${BASE_URL}/v1/paper/test/status"
check "GET /v1/paper/test/proof" curl -fsS --connect-timeout 5 "${BASE_URL}/v1/paper/test/proof"
check "GET /v1/portfolio/compare-books" curl -fsS --connect-timeout 5 "${BASE_URL}/v1/portfolio/compare-books"
check "GET /v1/system/reconciliation" curl -fsS --connect-timeout 5 "${BASE_URL}/v1/system/reconciliation"

echo "==> Log collection (manual)"
if [ -x "$COMPOSE_SH" ]; then
  echo "$COMPOSE_SH logs --tail=200 api worker scanner alpaca_market_gateway alpaca_trade_gateway alpaca_reconciler scheduler ui > runtime_truth_logs.txt"
else
  echo "No compose.sh; capture API logs from your runtime."
fi
echo
echo "Checklist: pass=${PASS} fail=${FAIL}"
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
