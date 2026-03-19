#!/usr/bin/env bash
# Live paper lifecycle validation: four flows (buy-open, sell-close, short-open, buy-cover).
# Gated: runs only when ENABLE_LIVE_PAPER_VALIDATION=1 and Alpaca paper credentials are set.
# Places real paper orders. Writes JSON evidence to artifacts/paper_lifecycle_<timestamp>/.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BASE_URL="${BASE_URL:-http://localhost:8000}"

if [ "${ENABLE_LIVE_PAPER_VALIDATION:-0}" != "1" ]; then
  echo "Live paper validation is disabled. Set ENABLE_LIVE_PAPER_VALIDATION=1 to run (places real paper orders)." >&2
  exit 2
fi

# Load .env for Alpaca keys (same pattern as compose.sh)
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
if [ -z "${ALPACA_API_KEY_ID:-}" ] || [ -z "${ALPACA_API_SECRET_KEY:-}" ]; then
  echo "Alpaca paper credentials required. Set ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY (e.g. in .env)." >&2
  exit 2
fi

TS=$(date -u +%Y%m%dT%H%M%SZ)
ARTIFACT_DIR="${ROOT}/artifacts/paper_lifecycle_${TS}"
mkdir -p "$ARTIFACT_DIR"
echo "[paper_lifecycle_validate] Evidence directory: $ARTIFACT_DIR"

PASS=0
FAIL=0
SYMBOL="${PAPER_VALIDATION_SYMBOL:-AAPL}"
QTY="${PAPER_VALIDATION_QTY:-1}"

get() {
  curl -fsS --connect-timeout 10 "$BASE_URL$1"
}
post() {
  curl -fsS -X POST -H "Content-Type: application/json" -d "$2" --connect-timeout 10 "$BASE_URL$1"
}

check_step() {
  local label="$1"
  if [ "$2" = "0" ]; then
    echo "  PASS: $label"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $label"
    FAIL=$((FAIL + 1))
  fi
}

# Capture baseline for shadow comparison
get /v1/portfolio/compare-books > "$ARTIFACT_DIR/compare_books_before.json" 2>/dev/null || true
get /v1/paper/test/proof > "$ARTIFACT_DIR/proof_before.json" 2>/dev/null || true

echo "==> 1. GET /v1/paper/test/status"
STATUS=$(get /v1/paper/test/status 2>/dev/null) || { echo "[paper_lifecycle_validate] GET /v1/paper/test/status failed (broker/API down?)" >&2; exit 1; }
echo "$STATUS" > "$ARTIFACT_DIR/status.json"
if ! echo "$STATUS" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('paper_execution_enabled') or d.get('paper_enabled') else 1)" 2>/dev/null; then
  echo "  WARN: paper not enabled in status; state=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('state',''))" 2>/dev/null)" >&2
fi
echo

echo "==> 2. POST /v1/paper/test/buy-open (BUY open long)"
R=$(post /v1/paper/test/buy-open "{\"symbol\":\"$SYMBOL\",\"qty\":$QTY,\"order_type\":\"market\"}" 2>/dev/null) || R="{}"
echo "$R" > "$ARTIFACT_DIR/buy_open_response.json"
if echo "$R" | grep -q '"client_order_id"\|"order_id"\|"id"'; then
  check_step "buy-open submission" 0
else
  check_step "buy-open submission" 1
fi
sleep 3
get /v1/orders > "$ARTIFACT_DIR/orders_after_buy_open.json" 2>/dev/null || true
get /v1/trades/paper > "$ARTIFACT_DIR/trades_paper_after_buy_open.json" 2>/dev/null || true
get /v1/account > "$ARTIFACT_DIR/account_after_buy_open.json" 2>/dev/null || true
get /v1/positions > "$ARTIFACT_DIR/positions_after_buy_open.json" 2>/dev/null || true
get /v1/paper/test/proof > "$ARTIFACT_DIR/proof_after_buy_open.json" 2>/dev/null || true
get /v1/portfolio/compare-books > "$ARTIFACT_DIR/compare_books_after_buy_open.json" 2>/dev/null || true
get /v1/system/reconciliation > "$ARTIFACT_DIR/reconciliation_after_buy_open.json" 2>/dev/null || true
echo

echo "==> 3. POST /v1/paper/test/sell-close (SELL close long)"
R=$(post /v1/paper/test/sell-close "{\"symbol\":\"$SYMBOL\",\"qty\":$QTY,\"order_type\":\"market\"}" 2>/dev/null) || R="{}"
echo "$R" > "$ARTIFACT_DIR/sell_close_response.json"
if echo "$R" | grep -q '"client_order_id"\|"order_id"\|"id"'; then
  check_step "sell-close submission" 0
else
  check_step "sell-close submission" 1
fi
sleep 3
get /v1/orders > "$ARTIFACT_DIR/orders_after_sell_close.json" 2>/dev/null || true
get /v1/trades/paper > "$ARTIFACT_DIR/trades_paper_after_sell_close.json" 2>/dev/null || true
get /v1/paper/test/proof > "$ARTIFACT_DIR/proof_after_sell_close.json" 2>/dev/null || true
get /v1/portfolio/compare-books > "$ARTIFACT_DIR/compare_books_after_sell_close.json" 2>/dev/null || true
get /v1/system/reconciliation > "$ARTIFACT_DIR/reconciliation_after_sell_close.json" 2>/dev/null || true
echo

echo "==> 4. POST /v1/paper/test/short-open (SELL open short)"
R=$(post /v1/paper/test/short-open "{\"symbol\":\"$SYMBOL\",\"qty\":$QTY,\"order_type\":\"market\"}" 2>/dev/null) || R="{}"
echo "$R" > "$ARTIFACT_DIR/short_open_response.json"
if echo "$R" | grep -q '"client_order_id"\|"order_id"\|"id"'; then
  check_step "short-open submission" 0
else
  check_step "short-open submission" 1
fi
sleep 3
get /v1/orders > "$ARTIFACT_DIR/orders_after_short_open.json" 2>/dev/null || true
get /v1/trades/paper > "$ARTIFACT_DIR/trades_paper_after_short_open.json" 2>/dev/null || true
get /v1/paper/test/proof > "$ARTIFACT_DIR/proof_after_short_open.json" 2>/dev/null || true
get /v1/portfolio/compare-books > "$ARTIFACT_DIR/compare_books_after_short_open.json" 2>/dev/null || true
echo

echo "==> 5. POST /v1/paper/test/buy-cover (BUY cover short)"
R=$(post /v1/paper/test/buy-cover "{\"symbol\":\"$SYMBOL\",\"qty\":$QTY,\"order_type\":\"market\"}" 2>/dev/null) || R="{}"
echo "$R" > "$ARTIFACT_DIR/buy_cover_response.json"
if echo "$R" | grep -q '"client_order_id"\|"order_id"\|"id"'; then
  check_step "buy-cover submission" 0
else
  check_step "buy-cover submission" 1
fi
sleep 3
get /v1/paper/test/proof > "$ARTIFACT_DIR/proof_final.json" 2>/dev/null || true
get /v1/portfolio/compare-books > "$ARTIFACT_DIR/compare_books_final.json" 2>/dev/null || true
get /v1/system/reconciliation > "$ARTIFACT_DIR/reconciliation_final.json" 2>/dev/null || true
echo

echo "==> Summary"
echo "  pass=$PASS fail=$FAIL"
echo "  Evidence: $ARTIFACT_DIR"
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
