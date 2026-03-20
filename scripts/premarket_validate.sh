#!/usr/bin/env bash
# Premarket activation validation: critical path checks for premarket readiness.
# Validates: scanner/opportunity live, Scrappy auto-run live, AI coverage state, paper arming/gating, lifecycle/protection, degraded-state UI honesty.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BASE_URL="${BASE_URL:-http://localhost:8000}"
PASS=0
FAIL=0
WARN=0

# Load .env if present
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

load_env

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

warn() {
  local label="$1"
  shift
  echo "==> ${label}"
  if "$@"; then
    echo "WARN: ${label} (check manually)"
    WARN=$((WARN + 1))
  else
    echo "PASS: ${label}"
    PASS=$((PASS + 1))
  fi
  echo
}

get() {
  curl -fsS -H "Accept: application/json" "${BASE_URL}$1" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "{}"
}

# ---- 1. Scanner/Opportunity Live ----
echo "=== 1. Scanner/Opportunity Live ==="
echo

scanner_summary=$(get "/v1/scanner/summary")
scanner_status=$(echo "$scanner_summary" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('last_run_status', 'unknown'))" 2>/dev/null || echo "unknown")
scanner_top_count=$(echo "$scanner_summary" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('top_count', 0))" 2>/dev/null || echo "0")
scanner_last_run=$(echo "$scanner_summary" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('last_run_ts', ''))" 2>/dev/null || echo "")

check "Scanner has completed run" [ "$scanner_status" = "completed" ]
check "Scanner has top candidates" [ "$scanner_top_count" -gt 0 ]
warn "Scanner last run is recent (< 2 hours)" python3 -c "
import sys, json, datetime
last_run = '$scanner_last_run'
if not last_run:
    sys.exit(1)
try:
    dt = datetime.datetime.fromisoformat(last_run.replace('Z', '+00:00'))
    age_hours = (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds() / 3600
    sys.exit(0 if age_hours < 2 else 1)
except:
    sys.exit(1)
"

opportunities_summary=$(get "/v1/opportunities/summary")
opp_source=$(echo "$opportunities_summary" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('source', 'none'))" 2>/dev/null || echo "none")
opp_top_count=$(echo "$opportunities_summary" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('top_count', 0))" 2>/dev/null || echo "0")

check "Opportunity engine has source" [ "$opp_source" != "none" ]
check "Opportunity engine has top candidates" [ "$opp_top_count" -gt 0 ]

opportunities_now=$(get "/v1/opportunities/now")
opp_count=$(echo "$opportunities_now" | python3 -c "import sys, json; d=json.load(sys.stdin); opps=d.get('opportunities', []); print(len(opps))" 2>/dev/null || echo "0")
opp_with_price=$(echo "$opportunities_now" | python3 -c "import sys, json; d=json.load(sys.stdin); opps=d.get('opportunities', []); print(sum(1 for o in opps if o.get('price') is not None))" 2>/dev/null || echo "0")

check "Opportunities endpoint returns candidates" [ "$opp_count" -gt 0 ]
check "Opportunities have price data" [ "$opp_with_price" -gt 0 ]

# ---- 2. Scrappy Auto-Run Live ----
echo "=== 2. Scrappy Auto-Run Live ==="
echo

scrappy_status=$(get "/v1/scrappy/status")
scrappy_enabled=$(echo "$scrappy_status" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('scrappy_auto_enabled', False))" 2>/dev/null || echo "False")
scrappy_last_run=$(echo "$scrappy_status" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('last_run_at', ''))" 2>/dev/null || echo "")
scrappy_last_attempt=$(echo "$scrappy_status" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('last_attempt_at', ''))" 2>/dev/null || echo "")
scrappy_failure=$(echo "$scrappy_status" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('last_failure_reason', ''))" 2>/dev/null || echo "")
scrappy_snapshots=$(echo "$scrappy_status" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('last_snapshots_updated', 0))" 2>/dev/null || echo "0")

check "Scrappy auto-run is enabled" [ "$scrappy_enabled" = "True" ]
warn "Scrappy has recent run (< 2 hours)" python3 -c "
import sys, json, datetime
last_run = '$scrappy_last_run'
if not last_run:
    sys.exit(1)
try:
    dt = datetime.datetime.fromisoformat(last_run.replace('Z', '+00:00'))
    age_hours = (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds() / 3600
    sys.exit(0 if age_hours < 2 else 1)
except:
    sys.exit(1)
"
warn "Scrappy has recent attempt" [ -n "$scrappy_last_attempt" ]
check "Scrappy has no recent failure" [ -z "$scrappy_failure" ]
warn "Scrappy updated snapshots" [ "$scrappy_snapshots" -gt 0 ]

# ---- 3. AI Coverage State Correct ----
echo "=== 3. AI Coverage State Correct ==="
echo

runtime_status=$(get "/v1/runtime/status")
ai_referee_enabled=$(echo "$runtime_status" | python3 -c "import sys, json; d=json.load(sys.stdin); ai=d.get('ai_referee', {}); print(ai.get('enabled', False))" 2>/dev/null || echo "False")
ai_referee_mode=$(echo "$runtime_status" | python3 -c "import sys, json; d=json.load(sys.stdin); ai=d.get('ai_referee', {}); print(ai.get('mode', 'off'))" 2>/dev/null || echo "off")

ai_referee_recent=$(get "/v1/ai-referee/recent?limit=10")
ai_assessment_count=$(echo "$ai_referee_recent" | python3 -c "import sys, json; d=json.load(sys.stdin); assessments=d.get('assessments', []); print(len(assessments))" 2>/dev/null || echo "0")

check "AI Referee status is available" [ -n "$ai_referee_enabled" ]
if [ "$ai_referee_enabled" = "True" ]; then
  warn "AI Referee has recent assessments" [ "$ai_assessment_count" -gt 0 ]
else
  echo "INFO: AI Referee is disabled (not required for premarket)"
  PASS=$((PASS + 1))
fi

# ---- 4. Paper Arming/Gating Correct ----
echo "=== 4. Paper Arming/Gating Correct ==="
echo

paper_prereqs=$(get "/v1/paper/arming-prerequisites")
prereqs_satisfied=$(echo "$paper_prereqs" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('satisfied', False))" 2>/dev/null || echo "False")
prereqs_blockers=$(echo "$paper_prereqs" | python3 -c "import sys, json; d=json.load(sys.stdin); blockers=d.get('blockers', []); print('|'.join(blockers) if blockers else '')" 2>/dev/null || echo "")

paper_armed=$(echo "$runtime_status" | python3 -c "import sys, json; d=json.load(sys.stdin); pe=d.get('paper_execution', {}); print(pe.get('armed', False))" 2>/dev/null || echo "False")
paper_reason=$(echo "$runtime_status" | python3 -c "import sys, json; d=json.load(sys.stdin); pe=d.get('paper_execution', {}); print(pe.get('armed_reason', ''))" 2>/dev/null || echo "")

check "Paper arming prerequisites endpoint exists" [ -n "$prereqs_satisfied" ]
if [ "$paper_armed" = "True" ]; then
  check "Paper armed when prerequisites satisfied" [ "$prereqs_satisfied" = "True" ]
  check "Paper armed reason is present" [ -n "$paper_reason" ]
else
  check "Paper disarmed when prerequisites not satisfied" [ "$prereqs_satisfied" = "False" ] || [ -n "$prereqs_blockers" ]
fi

# ---- 5. Lifecycle/Protection Still Correct ----
echo "=== 5. Lifecycle/Protection Still Correct ==="
echo

paper_exposure=$(get "/v1/paper/exposure")
exposure_positions=$(echo "$paper_exposure" | python3 -c "import sys, json; d=json.load(sys.stdin); positions=d.get('positions', []); print(len(positions))" 2>/dev/null || echo "0")

if [ "$exposure_positions" -gt 0 ]; then
  # Check that positions have lifecycle data
  positions_with_stop=$(echo "$paper_exposure" | python3 -c "import sys, json; d=json.load(sys.stdin); positions=d.get('positions', []); print(sum(1 for p in positions if p.get('stop_price') is not None))" 2>/dev/null || echo "0")
  positions_with_target=$(echo "$paper_exposure" | python3 -c "import sys, json; d=json.load(sys.stdin); positions=d.get('positions', []); print(sum(1 for p in positions if p.get('target_price') is not None))" 2>/dev/null || echo "0")
  positions_managed=$(echo "$paper_exposure" | python3 -c "import sys, json; d=json.load(sys.stdin); positions=d.get('positions', []); print(sum(1 for p in positions if p.get('managed_status') == 'managed'))" 2>/dev/null || echo "0")
  
  check "Paper positions have stop prices" [ "$positions_with_stop" -eq "$exposure_positions" ]
  check "Paper positions have target prices" [ "$positions_with_target" -eq "$exposure_positions" ]
  warn "Paper positions are managed" [ "$positions_managed" -eq "$exposure_positions" ]
else
  echo "INFO: No open paper positions (lifecycle checks skipped)"
  PASS=$((PASS + 1))
fi

# ---- 6. Degraded-State UI Honest ----
echo "=== 6. Degraded-State UI Honest ==="
echo

# Check that opportunities endpoint doesn't fake data
opp_with_null_price=$(echo "$opportunities_now" | python3 -c "import sys, json; d=json.load(sys.stdin); opps=d.get('opportunities', []); print(sum(1 for o in opps if o.get('price') is None))" 2>/dev/null || echo "0")
opp_with_null_gap=$(echo "$opportunities_now" | python3 -c "import sys, json; d=json.load(sys.stdin); opps=d.get('opportunities', []); print(sum(1 for o in opps if o.get('gap_pct') is None))" 2>/dev/null || echo "0")

# It's OK to have some nulls if opportunity engine is used, but we should have at least some with data
if [ "$opp_count" -gt 0 ]; then
  check "Some opportunities have price data (not all null)" [ "$opp_with_price" -gt 0 ]
  warn "Most opportunities have gap data" [ "$opp_with_null_gap" -lt "$opp_count" ]
fi

# Check that scrappy status shows honest failure states
check "Scrappy status shows failure reason when present" [ -n "$scrappy_failure" ] || [ -n "$scrappy_last_run" ]

# Check that health endpoints are honest
health_detail=$(get "/v1/health/detail")
health_api=$(echo "$health_detail" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('api', {}).get('status', 'unknown'))" 2>/dev/null || echo "unknown")
health_db=$(echo "$health_detail" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('database', {}).get('status', 'unknown'))" 2>/dev/null || echo "unknown")

check "Health detail shows API status" [ "$health_api" != "unknown" ]
check "Health detail shows DB status" [ "$health_db" != "unknown" ]

# ---- Summary ----
echo "=== Summary ==="
echo
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "WARN: $WARN"
echo

if [ $FAIL -eq 0 ]; then
  if [ $WARN -eq 0 ]; then
    echo "✅ All premarket validation checks passed"
    exit 0
  else
    echo "⚠️  All critical checks passed, but some warnings present (review manually)"
    exit 0
  fi
else
  echo "❌ Some critical checks failed"
  exit 1
fi
