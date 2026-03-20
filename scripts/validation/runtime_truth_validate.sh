#!/usr/bin/env bash
# Runtime truth validation: repo-native full-stack (compose + migrations + API) or API-only when API_ONLY=1.
# Primary path: docker compose -f infra/compose.yaml; migrations; stack up; then HTTP checks.
# Secondary path: API_ONLY=1 — skip compose/migrate/up; validate only HTTP endpoints against BASE_URL.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
BASE_URL="${BASE_URL:-http://localhost:8000}"
PASS=0
FAIL=0

# Load .env if present (for compose config / migrate / up)
load_env() {
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
}

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

# ---- Full-stack path (repo-native) ----
run_full_stack() {
  if [ ! -f "$ROOT/infra/compose.yaml" ]; then
    echo "[runtime_truth_validate] infra/compose.yaml not found; cannot run full-stack. Use API_ONLY=1 to validate against BASE_URL only." >&2
    exit 1
  fi
  load_env
  COMPOSE_CMD="docker compose -f $ROOT/infra/compose.yaml -p infra"

  check "Compose config validates" $COMPOSE_CMD config --quiet

  echo "==> Migrations upgrade head"
  set +e
  migrate_out=$($COMPOSE_CMD run --rm api python -m alembic -c alembic.ini upgrade head 2>&1)
  mig_ret=$?
  set -e
  if [ "$mig_ret" -eq 0 ]; then
    echo "PASS: Migrations upgrade head"
    PASS=$((PASS + 1))
  else
    echo "FAIL: Migrations upgrade head (check DATABASE_URL and postgres volume)" >&2
    echo "$migrate_out" | tail -20 >&2
    FAIL=$((FAIL + 1))
  fi
  echo

  echo "==> Stack startup"
  if $COMPOSE_CMD up -d postgres redis api worker scheduler alpaca_market_gateway alpaca_trade_gateway alpaca_reconciler scanner scrappy_auto ui 2>&1; then
    echo "PASS: Stack startup"
    PASS=$((PASS + 1))
  else
    echo "FAIL: Stack startup (check docker compose logs)" >&2
    FAIL=$((FAIL + 1))
  fi
  echo
}

# ---- API endpoint checks (same for full-stack and API-only) ----
run_http_checks() {
  check "GET /health" curl -fsS --connect-timeout 5 "${BASE_URL}/health"
  check "GET /health/detail" curl -fsS --connect-timeout 5 "${BASE_URL}/health/detail"
  check "GET /v1/config" curl -fsS --connect-timeout 5 "${BASE_URL}/v1/config"
  check "GET /v1/runtime/status" curl -fsS --connect-timeout 5 "${BASE_URL}/v1/runtime/status"
  check "GET /v1/system/health" curl -fsS --connect-timeout 5 "${BASE_URL}/v1/system/health"
  check "GET /v1/scanner/summary" curl -fsS --connect-timeout 5 "${BASE_URL}/v1/scanner/summary"
  check "GET /v1/opportunities/summary" curl -fsS --connect-timeout 5 "${BASE_URL}/v1/opportunities/summary"
  check "GET /v1/scrappy/status" curl -fsS --connect-timeout 5 "${BASE_URL}/v1/scrappy/status"
  check "GET /v1/account or 503" bash -c 'code=$(curl -fsS -o /dev/null -w "%{http_code}" --connect-timeout 5 "'"${BASE_URL}"'/v1/account"); [[ "$code" == "200" || "$code" == "503" ]]'
  check "GET /v1/paper/test/status" curl -fsS --connect-timeout 5 "${BASE_URL}/v1/paper/test/status"
  check "GET /v1/paper/test/proof" curl -fsS --connect-timeout 5 "${BASE_URL}/v1/paper/test/proof"
  check "GET /v1/portfolio/compare-books" curl -fsS --connect-timeout 5 "${BASE_URL}/v1/portfolio/compare-books"
  check "GET /v1/system/reconciliation" curl -fsS --connect-timeout 5 "${BASE_URL}/v1/system/reconciliation"
}

# ---- Main ----
if [ "${API_ONLY:-0}" = "1" ]; then
  echo "==> API-only mode (API_ONLY=1); skipping compose, migrations, and stack startup."
  echo
  run_http_checks
else
  run_full_stack
  run_http_checks
fi

echo "==> Log collection (manual)"
if [ "${API_ONLY:-0}" != "1" ] && [ -f "$ROOT/infra/compose.yaml" ]; then
  echo "  docker compose -f $ROOT/infra/compose.yaml -p infra logs --tail=200 api worker alpaca_trade_gateway alpaca_reconciler > runtime_truth_logs.txt"
else
  echo "  Capture API logs from your runtime."
fi
echo
echo "Checklist: pass=${PASS} fail=${FAIL}"
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
