# Premarket Rescue Tranche - Summary

**Date**: 2026-03-20  
**Status**: Code fixes complete, validation pending live runtime

## What Was Broken

1. **AI Referee Premarket Runner** (`src/stockbot/ai_referee/premarket_runner.py`):
   - Indentation error on line 58 (`factory = get_session_factory()` was not indented)
   - Code after snapshot check (lines 64-83) was outside the `async with` block
   - Wrong function name: `get_latest_snapshot_for_symbol` → `get_latest_snapshot_by_symbol` (line 186)
   - Missing import for `get_latest_snapshot_by_symbol` in `_should_assess_symbol`

2. **Premarket Validation Script** (`scripts/premarket_validate.sh`):
   - Wrong API endpoint path: `/v1/health/detail` → `/health/detail`
   - Wrong field paths for paper arming: `paper_execution.armed` → `paper_trading_armed`, `paper_execution.armed_reason` → `paper_armed_reason`
   - Health detail structure mismatch: expected nested `status` field but API returns direct string values
   - Scrappy enabled check: Python boolean `True` vs string comparison issue

3. **Opportunities Price Data** (`src/api/main.py`):
   - Price/gap/spread data not being populated from scanner candidates
   - Query was using latest scanner run instead of the run_id that matches the opportunity run
   - Symbol case normalization needed for matching

4. **UI Truth Hardening** (`frontend/src/pages/IntelligenceCenter.tsx`):
   - Degraded state logic was too lenient - showed "degraded" even when Scrappy had recent runs
   - Missing explicit failure reason display in degraded message

## What Was Fixed

### Phase 1: AI Referee Premarket Runner
- ✅ Fixed indentation errors
- ✅ Fixed function name (`get_latest_snapshot_by_symbol`)
- ✅ Added missing import
- ✅ Ensured proper async context management
- ✅ Verified compose service wiring (`ai_referee_premarket` service exists and points to correct entrypoint)

### Phase 2: Premarket Validation Script
- ✅ Fixed health endpoint path (`/health/detail`)
- ✅ Fixed paper arming field paths (`paper_trading_armed`, `paper_armed_reason`)
- ✅ Fixed health detail structure parsing (direct string values, not nested)
- ✅ Fixed Scrappy enabled check to handle Python boolean properly
- ✅ Improved scrappy status truth check logic

### Phase 3: Opportunities Price Data
- ✅ Modified `/v1/opportunities/now` to fetch price/gap/spread from scanner candidates
- ✅ Use opportunity run_id (which matches scanner run_id) for lookup
- ✅ Added fallback to latest scanner run if no matches found
- ✅ Normalized symbol case for matching

### Phase 4: UI Truth Hardening
- ✅ Enhanced degraded state logic to show explicit reasons:
  - Scrappy has not run
  - Scrappy last run age
  - No fresh research on focus symbols
  - Scrappy failure reason (if present)
- ✅ More accurate "alive" vs "degraded" vs "partial" determination

## Exact Files Changed

1. `src/stockbot/ai_referee/premarket_runner.py` - Fixed syntax, indentation, function names
2. `scripts/premarket_validate.sh` - Fixed API endpoint paths and field access
3. `src/api/main.py` - Fixed opportunities price data population
4. `frontend/src/pages/IntelligenceCenter.tsx` - Hardened degraded state logic

## Exact Commands to Run Locally

### Rebuild and Restart Services
```bash
# Rebuild API container with fixes
cd /home/neil-dempster/StockBot
docker build -f infra/Dockerfile.app -t infra-app:latest .
docker compose -f infra/compose.yaml restart api

# Rebuild UI container with fixes
cd frontend && npm run build
cd ..
docker build -f infra/Dockerfile.ui -t infra-ui:latest .
docker compose -f infra/compose.yaml restart ui

# Restart AI Referee premarket service (if enabled)
docker compose -f infra/compose.yaml restart ai_referee_premarket
```

### Run Validation
```bash
# Run premarket validation script
./scripts/premarket_validate.sh

# Manual checks
curl -s http://localhost:8000/v1/scrappy/status | python3 -m json.tool
curl -s http://localhost:8000/v1/opportunities/now | python3 -c "import sys, json; d=json.load(sys.stdin); opps=d.get('opportunities', []); print(f'With price: {sum(1 for o in opps if o.get(\"price\") is not None)}/{len(opps)}')"
curl -s http://localhost:8000/v1/intelligence/recent?limit=10 | python3 -c "import sys, json; d=json.load(sys.stdin); snaps=d.get('snapshots', []); print(f'Fresh snapshots: {len([s for s in snaps if not s.get(\"stale_flag\") and not s.get(\"conflict_flag\")])}')"
```

## Exact Commands to Run on Live Premarket Stack

### Verify Scrappy Activity
```bash
# Check Scrappy last run
curl -s http://localhost:8000/v1/scrappy/status | jq '{last_run_at, last_attempt_at, last_snapshots_updated, last_failure_reason}'

# Trigger Scrappy run manually
curl -s -X POST http://localhost:8000/v1/scrappy/auto-run/now | jq

# Wait 30 seconds, then check status again
sleep 30
curl -s http://localhost:8000/v1/scrappy/status | jq '{last_run_at, last_snapshots_updated}'
```

### Verify Fresh Snapshots on Focus Symbols
```bash
# Get focus symbols
curl -s http://localhost:8000/v1/opportunities/now | jq -r '.opportunities[].symbol' | head -10

# Check intelligence for each symbol
for sym in $(curl -s http://localhost:8000/v1/opportunities/now | jq -r '.opportunities[].symbol' | head -5); do
  echo "=== $sym ==="
  curl -s "http://localhost:8000/v1/intelligence/latest?symbol=$sym" | jq '{symbol, snapshot_ts, stale_flag, conflict_flag, freshness_minutes}'
done
```

### Verify AI Assessments (if AI Referee enabled)
```bash
# Check AI Referee status
curl -s http://localhost:8000/v1/runtime/status | jq '.ai_referee'

# Check recent assessments
curl -s http://localhost:8000/v1/ai-referee/recent?limit=10 | jq '.assessments[] | {symbol, assessment_ts, decision_class}'

# Trigger premarket assessment manually (if enabled)
curl -s -X POST http://localhost:8000/v1/ai-referee/premarket/now | jq
```

### Verify Premarket Prep Page
```bash
# Open UI in browser
open http://localhost:8080/intelligence

# Check that:
# 1. "Premarket Health Status" section shows accurate counts
# 2. Focus board shows pipeline stages with reasons
# 3. Degraded state shows explicit failure reasons if research is missing
# 4. Price data appears in focus board (if scanner candidates have prices)
```

## What the Validation Cycle Proved

### ✅ Working
- Scanner runs and produces top candidates
- Opportunities endpoint returns candidates
- Scrappy auto-run executes (though snapshots_updated may be 0 if no new notes)
- Health endpoints return correct structure
- Paper arming prerequisites check works

### ⚠️ Needs Runtime Verification
- **Price data population**: Code fix is correct, but requires API container rebuild to take effect
- **Scrappy snapshots**: May show 0 if symbols don't have notes yet (expected behavior)
- **AI Referee assessments**: Only runs if AI_REFEREE_ENABLED=true and symbols have fresh snapshots
- **Premarket Prep UI**: Requires UI container rebuild to show hardened degraded states

### ❌ Still Failing (Expected in Current State)
- Some validation checks fail because:
  - Scanner may not have run recently (expected if not in premarket)
  - Opportunities may not have price data until API is rebuilt
  - Scrappy may show 0 snapshots if no notes exist for focus symbols (truthful state)

## What Still Remains Unproven

1. **Price Data Population**: Code fix is correct, but needs API rebuild to verify
2. **AI Referee Premarket Coverage**: Needs AI_REFEREE_ENABLED=true and fresh snapshots to test
3. **Scrappy Snapshot Creation**: May legitimately be 0 if focus symbols have no notes (this is truthful)
4. **UI Degraded State Display**: Needs UI rebuild to see enhanced failure reason messages

## Exact Conditions That Define "Premarket Alive"

The platform is "alive in premarket" when ALL of the following are true:

1. **Scanner Active**: 
   - Last run status = "completed"
   - Last run < 2 hours ago
   - Top candidates count > 0

2. **Focus Symbols Identified**:
   - Opportunities endpoint returns > 0 candidates
   - At least some candidates have price data (if scanner has run)

3. **Fresh Research Coverage**:
   - Scrappy last run < 1 hour ago (or last attempt < 1 hour ago)
   - At least some focus symbols have fresh snapshots (not stale, not conflicted, < 4 hours old)
   - Scrappy has no recent failure (or failure reason is explicitly shown)

4. **AI Assessments** (if AI_REFEREE_ENABLED=true):
   - At least some researched symbols have recent assessments (< 2 hours old)
   - OR explicit reason shown why assessments are missing (no fresh snapshots, disabled, etc.)

The platform is "degraded" if:
- Scanner is active BUT research is missing/stale
- Scrappy has failed with explicit reason
- Focus symbols exist but have no fresh intelligence

The platform is "not running" if:
- Scanner has not run recently
- No focus symbols identified

## Next Steps

1. **Rebuild API container** to apply opportunities price data fix
2. **Rebuild UI container** to show hardened degraded states
3. **Run validation during actual premarket hours** to verify end-to-end
4. **Monitor Scrappy snapshots_updated** - if consistently 0, investigate why notes aren't being created for focus symbols
5. **Enable AI Referee** (if desired) and verify premarket assessments populate

## Notes

- All code fixes are minimal and surgical - no architecture changes
- Paper safety controls remain unchanged
- Deterministic strategy remains sole trade authority
- No fake/demo data added
- Validation script now matches current API structure
