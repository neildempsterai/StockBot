# Premarket Activation Rescue - 2026-03-20

## What Was Broken Before

1. **Scrappy Auto-Run Blocking**: The auto-runner had a "skip if symbols unchanged" optimization that prevented it from running during premarket when the symbol list was stable. This caused:
   - Last run timestamps to be stale (e.g., 14h ago)
   - Fresh intelligence count to be 0
   - Missing intelligence count to equal the entire focus list
   - Platform to feel "dead" before market open

2. **Opportunity Engine Missing Market Data**: When using the opportunity engine path (`/v1/opportunities/now`), price, gap_pct, and spread_bps were returned as `null` even though the scanner had this data. This made the focus board look empty and uninformative.

3. **Scrappy Status API Incomplete**: The status API didn't show:
   - Last attempt timestamp (only last successful run)
   - Last failure reason
   - Symbols requested vs symbols researched
   - Last outcome code

4. **UI Missing Pipeline Stages**: The Premarket Prep page didn't clearly show:
   - Where each symbol is stuck in the pipeline
   - Explicit reasoning for each stage
   - Overall premarket health status
   - Critical timestamps for scanner/opportunity/scrappy runs

5. **Snapshots Updated Not Tracked**: The `snapshots_updated` counter wasn't being calculated in the scrappy run service return value.

## What Now Makes the Platform Feel Alive in Premarket

### Phase 1: Fixed Scrappy Premarket Activity ✅

**File**: `src/stockbot/scrappy/auto_runner.py`

- **Removed blocking optimization**: Added time-based refresh logic during premarket. Even if symbols are unchanged, Scrappy will refresh if the last run was > 30 minutes ago during premarket.
- **Added failure tracking**: Now tracks:
  - `last_attempt_ts`: When Scrappy last tried to run (even if skipped/failed)
  - `last_failure_reason`: Explicit reason if the last run failed
  - `last_symbols_requested`: Symbols that were requested for research
  - `last_symbols_researched`: Symbols that were successfully researched
  - `last_outcome`: Outcome code from the last run

**Key Changes**:
- `_should_refresh_during_premarket()`: Checks if refresh is needed based on time (premarket) or symbol change (other sessions)
- `run_scrappy_auto_once()`: Now tracks attempt timestamps and failure reasons
- `_persist_auto_run()`: Handles failure cases and persists them

### Phase 2: Enhanced Scrappy Coverage Status ✅

**File**: `src/api/main.py` (endpoint `/v1/scrappy/status`)

- Enhanced status response to include:
  - `last_attempt_at`: Last time Scrappy tried to run
  - `last_failure_reason`: Why the last run failed (if any)
  - `last_outcome`: Outcome code (success_useful_output, failed, etc.)
  - `last_symbols_requested`: List of symbols requested
  - `last_symbols_researched`: List of symbols successfully researched

### Phase 3: Fixed Opportunity/Focus Board Data Quality ✅

**File**: `src/api/main.py` (endpoint `/v1/opportunities/now`)

- **Fixed missing price/gap/spread**: When using the opportunity engine path, the API now fetches market data (price, gap_pct, spread_bps) from the latest live scanner run for each symbol.
- This ensures the focus board shows real market context even when using the opportunity engine.

**Implementation**:
- Fetches latest live scanner result
- Looks up scanner candidates for each opportunity symbol
- Populates price, gap_pct, spread_bps from scanner data

### Phase 4: Fixed Snapshots Updated Tracking ✅

**File**: `src/stockbot/scrappy/run_service.py`

- Added `snapshots_updated` counter that tracks how many symbol snapshots were successfully persisted during a Scrappy run.
- This counter is now returned in the run result and exposed via the status API.

### Phase 5: Enhanced Premarket Prep UI with Pipeline Stages ✅

**File**: `frontend/src/pages/IntelligenceCenter.tsx`

- **Pipeline Stage Display**: Each focus symbol now shows:
  - **discovered**: Symbol found by scanner but no research yet
  - **missing**: No Scrappy snapshot - needs research
  - **stale**: Snapshot stale or conflicted
  - **researched**: Research complete, awaiting AI assessment
  - **ready**: Research fresh, AI assessed
  - **watch**: Research fresh, no AI assessment yet
  - **active**: Open paper position exists
  - **blocked**: Unknown/error state

- **Explicit Stage Reasoning**: Each symbol shows why it's in that stage:
  - "No Scrappy snapshot - needs research"
  - "Snapshot stale - research outdated"
  - "Snapshot conflicted - mixed signals"
  - "Research complete, awaiting AI assessment"
  - "Research fresh, AI assessed"
  - etc.

### Phase 6: Added Critical Premarket Health Visibility ✅

**File**: `frontend/src/pages/IntelligenceCenter.tsx`

- **Premarket Health Status Section**: New section showing:
  - Scanner last run timestamp and status
  - Opportunity last run timestamp and source
  - Scrappy last successful run and snapshot count
  - Scrappy last failure reason (if any)
  - Focus symbols count
  - Symbols with fresh research count
  - Symbols needing research count
  - Symbols assessed by AI count

- **Overall Premarket Alive Status**: Dynamic status indicator:
  - **"Premarket alive"** (green): Scanner active, focus symbols identified, fresh research coverage
  - **"Premarket degraded"** (red): Scanner active but research coverage missing or stale
  - **"Premarket partial"** (yellow): Scanner active but no focus symbols or research yet
  - **"Premarket not running"** (red): Scanner inactive

- **Enhanced Scrappy Status Display**: Shows:
  - Last successful run timestamp
  - Last attempt timestamp (if different)
  - Last failure reason (if any)
  - Symbols requested in last run

## Exact Files Changed

1. `src/stockbot/scrappy/auto_runner.py`
   - Added time-based refresh logic for premarket
   - Added failure tracking and attempt timestamps
   - Enhanced Redis state tracking

2. `src/api/main.py`
   - Enhanced `/v1/scrappy/status` endpoint with failure tracking
   - Fixed `/v1/opportunities/now` to fetch price/gap/spread from scanner

3. `src/stockbot/scrappy/run_service.py`
   - Added `snapshots_updated` counter tracking

4. `frontend/src/pages/IntelligenceCenter.tsx`
   - Added pipeline stage display with explicit reasoning
   - Added premarket health status section
   - Added overall "premarket alive" status indicator
   - Enhanced Scrappy status display

5. `frontend/src/types/api.ts`
   - Updated `ScrappyStatusResponse` interface with new fields

## Exact Commands to Validate During Premarket

### 1. Check Scrappy Auto-Run Status
```bash
curl http://localhost:8000/v1/scrappy/status | jq
```

**Expected Output** (when healthy):
```json
{
  "scrappy_auto_enabled": true,
  "last_run_at": "2026-03-20T09:15:00Z",
  "last_attempt_at": "2026-03-20T09:15:00Z",
  "last_outcome": "success_useful_output",
  "last_failure_reason": null,
  "last_snapshots_updated": 12,
  "last_symbols_requested": ["AAPL", "MSFT", "GOOGL", ...],
  "last_symbols_researched": ["AAPL", "MSFT", "GOOGL", ...]
}
```

### 2. Check Opportunities with Market Data
```bash
curl http://localhost:8000/v1/opportunities/now | jq '.opportunities[0:3]'
```

**Expected Output** (when healthy):
```json
{
  "opportunities": [
    {
      "symbol": "AAPL",
      "rank": 1,
      "total_score": 0.85,
      "price": 175.50,
      "gap_pct": 2.3,
      "spread_bps": 5,
      "scrappy_present": true,
      ...
    },
    ...
  ]
}
```

### 3. Check Premarket Prep UI
- Navigate to `http://localhost:8080/intelligence`
- Verify:
  - "Premarket Health Status" section shows recent timestamps
  - Focus board shows price/gap/spread for all symbols
  - Pipeline stages show explicit reasoning
  - Overall status shows "Premarket alive" when healthy

### 4. Check Docker Logs for Scrappy Auto-Run
```bash
docker logs stockbot-scrappy_auto-1 --tail 50 | grep scrappy_auto
```

**Expected Output** (when running):
```
INFO scrappy_auto run_id=abc123 outcome=success_useful_output notes_created=15 snapshots_updated=12 symbols_requested=15
```

## Exact UI States That Should Now Appear When System Is Healthy

### Healthy State ("Premarket Alive")
- **Premarket Health Status**: Green border, "✓ Premarket alive: Scanner active, focus symbols identified, fresh research coverage"
- **Scanner**: "Live" (green), shows recent last run timestamp
- **Scrappy Auto**: "On" (green), shows recent last run (< 1 hour ago)
- **Fresh Intelligence**: Count > 0 (green)
- **Missing Intelligence**: Count = 0 or low
- **Focus Board**: All symbols show:
  - Price, gap %, spread bps populated
  - Scrappy snapshot present (not stale/conflicted)
  - Pipeline stage: "ready", "watch", or "researched"
  - Explicit reasoning shown

### Degraded State ("Premarket Degraded")
- **Premarket Health Status**: Red border, "⚠ Premarket degraded: Scanner active but research coverage missing or stale"
- **Scanner**: "Live" (green)
- **Scrappy Auto**: "On" but last run > 1 hour ago OR shows failure reason
- **Fresh Intelligence**: Count = 0 or very low (red)
- **Missing Intelligence**: Count > 0 (red)
- **Focus Board**: Symbols show:
  - Price/gap/spread may be populated
  - Many symbols with pipeline stage "missing" or "stale"
  - Explicit reasoning: "No Scrappy snapshot - needs research" or "Snapshot stale"

### Not Running State ("Premarket Not Running")
- **Premarket Health Status**: Red border, "○ Premarket not running"
- **Scanner**: "Inactive" or "Empty"
- **Scrappy Auto**: "On" but no recent runs
- **Focus Board**: Empty or shows "No focus symbols available"

## Remaining Blockers

1. **AI Referee Premarket Coverage** (Phase 3 - pending):
   - AI Referee is currently only triggered from the worker when evaluating signals
   - No proactive premarket assessment service exists
   - Focus symbols with fresh research are not automatically assessed
   - **Recommendation**: Add a lightweight premarket AI Referee runner or API endpoint that can assess top focus symbols with sufficient research

2. **Tests and Validation** (Phase 7 - pending):
   - No automated tests for premarket activation
   - No validation script to verify premarket health
   - **Recommendation**: Add practical tests for:
     - Scrappy auto-run time-based refresh during premarket
     - Opportunity engine price/gap/spread population
     - UI pipeline stage rendering
     - Health status calculation

3. **Operator Documentation** (Phase 8 - pending):
   - No operator-facing doc explaining premarket "alive" criteria
   - No runbook for troubleshooting premarket issues
   - **Recommendation**: Create `docs/PREMARKET_OPERATOR_GUIDE.md` with:
     - What "alive" means in premarket
     - Expected timestamps and counts
     - Troubleshooting steps for common issues

## Definition of Done Status

✅ **Premarket is "alive" when**:
- Scanner/opportunity are updating
- Scrappy last successful run is recent (< 1 hour)
- Focus symbols have fresh research coverage
- Focus board shows real market context (price/gap/spread)
- UI clearly tells operator what is ready vs missing
- Degraded states are explicit and actionable

⚠️ **Remaining**:
- AI assessments exist for assessable focus symbols (requires Phase 3 completion)
- Tests cover premarket activation (requires Phase 7)
- Operator documentation exists (requires Phase 8)

## Next Steps

1. **Immediate**: Test the changes during actual premarket hours to verify:
   - Scrappy auto-run refreshes every 30 minutes even if symbols unchanged
   - Focus board shows price/gap/spread for all symbols
   - UI shows accurate pipeline stages and health status

2. **Short-term**: Complete Phase 3 (AI Referee premarket coverage) if needed for full premarket activation

3. **Medium-term**: Add tests and operator documentation for long-term maintainability
