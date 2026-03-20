# Premarket Operator Runbook

Short runbook for operating StockBot during premarket hours. Focuses on what "alive" means, what to check, and how to troubleshoot.

## What "Alive in Premarket" Looks Like

The platform is **"alive"** when all of the following are true:

1. **Scanner is live**: Last run completed successfully, has top candidates (> 0)
2. **Opportunity engine is active**: Has source (not "none"), has top candidates, opportunities have price/gap/spread data
3. **Scrappy auto-run is recent**: Last successful run < 2 hours ago, snapshots updated > 0
4. **Focus symbols have fresh research**: Symbols with fresh (non-stale, non-conflicted) Scrappy snapshots
5. **UI shows "Premarket alive"**: Green status indicator in Premarket Prep page

### Healthy State Indicators

- **Premarket Prep page** (`/intelligence`):
  - "Premarket Health Status" section shows recent timestamps (< 2 hours)
  - "Premarket alive" status (green border)
  - Scanner: "Live" (green), recent last run
  - Scrappy Auto: "On" (green), recent last run
  - Fresh Intelligence count > 0 (green)
  - Missing Intelligence count = 0 or low
  - Focus Board: All symbols show price/gap/spread, pipeline stages "ready"/"watch"/"researched"

- **Command Center** (`/command`):
  - Premarket Prep Summary shows focus symbols count > 0
  - Fresh intelligence count > 0
  - Scanner status: "Live"
  - Scrappy auto-run: "On" with recent timestamp

## What Counts/Timestamps Should Move

### During Premarket (4:00 AM - 9:30 AM ET)

**Every 2-5 minutes:**
- Scanner last run timestamp should update
- Opportunity engine last run timestamp should update
- Focus symbols list may change (new symbols appear/disappear)

**Every 30 minutes (or when symbols change):**
- Scrappy last run timestamp should update
- Scrappy snapshots updated count should increase
- Fresh intelligence count should increase
- Missing intelligence count should decrease

**Every hour (if AI Referee enabled):**
- AI Referee assessment count may increase for focus symbols with fresh research

### What to Watch

- **Scanner last run**: Should be < 5 minutes old during active premarket
- **Scrappy last run**: Should be < 2 hours old (refreshes every 30 min or when symbols change)
- **Opportunity updated_at**: Should be < 5 minutes old
- **Focus symbols count**: Should be > 0 if scanner is live
- **Fresh intelligence count**: Should increase as Scrappy runs
- **Missing intelligence count**: Should decrease as Scrappy runs

## What Blocked States Mean

### "Premarket Degraded" (Red)

**Meaning**: Scanner is active but research coverage is missing or stale.

**Causes**:
- Scrappy auto-run hasn't run recently (> 2 hours)
- Scrappy auto-run is failing (check last failure reason)
- Focus symbols changed but Scrappy hasn't refreshed yet
- Scrappy is enabled but not running (check Docker logs)

**What to do**:
1. Check Scrappy status: `curl http://localhost:8000/v1/scrappy/status | jq`
2. Check last failure reason: Look for `last_failure_reason` in status
3. Check Docker logs: `docker logs stockbot-scrappy_auto-1 --tail 50`
4. Manually trigger: `curl -X POST http://localhost:8000/v1/scrappy/auto-run/now`
5. If still failing, check Redis/DB connectivity and Scrappy service health

### "Premarket Not Running" (Red)

**Meaning**: Scanner is inactive or no focus symbols.

**Causes**:
- Scanner hasn't run yet (bootstrap not complete)
- Scanner is blocked by session (outside premarket/regular hours)
- Scanner is failing (check scanner logs)
- No symbols in watchlist/universe

**What to do**:
1. Check scanner status: `curl http://localhost:8000/v1/scanner/summary | jq`
2. Check session: `curl http://localhost:8000/v1/runtime/status | jq '.market_data.session'`
3. Check scanner logs: `docker logs stockbot-scanner-1 --tail 50`
4. Manually trigger: `curl -X POST http://localhost:8000/v1/scanner/run/now`
5. Check watchlist/universe: Ensure symbols are available

### "Premarket Partial" (Yellow)

**Meaning**: Scanner is active but no focus symbols or research yet.

**Causes**:
- Scanner just started (bootstrap in progress)
- Opportunity engine hasn't produced candidates yet
- Scrappy hasn't run yet (waiting for first run)

**What to do**:
- Wait 2-5 minutes for first scanner/opportunity run
- Check if Scrappy bootstrap is complete (should run after 30s delay)
- If persists > 10 minutes, check scanner/opportunity logs

## What to Do If Scanner Is Live But Research Is Stale/Missing

### Symptoms
- Scanner shows "Live" with recent runs
- Focus symbols exist (> 0)
- Fresh intelligence count = 0
- Missing intelligence count = focus symbols count
- Scrappy last run > 2 hours ago

### Diagnosis Steps

1. **Check Scrappy auto-run status**:
   ```bash
   curl http://localhost:8000/v1/scrappy/status | jq
   ```
   - Look for `scrappy_auto_enabled: true`
   - Check `last_run_at` timestamp
   - Check `last_failure_reason` if present
   - Check `last_attempt_at` vs `last_run_at` (if different, runs are being skipped)

2. **Check Scrappy Docker logs**:
   ```bash
   docker logs stockbot-scrappy_auto-1 --tail 100 | grep scrappy_auto
   ```
   - Look for "scrappy_auto top symbols unchanged, skipping run" (may be blocking)
   - Look for exceptions or errors
   - Check if it's actually running (should see periodic log entries)

3. **Check Redis for symbol list**:
   ```bash
   docker exec stockbot-redis-1 redis-cli GET "stockbot:scanner:top_symbols"
   ```
   - Should return JSON array of symbols
   - If empty, scanner hasn't published symbols yet

4. **Manually trigger Scrappy**:
   ```bash
   curl -X POST http://localhost:8000/v1/scrappy/auto-run/now
   ```
   - Check response for `run_id` or `skipped` reason
   - Wait 1-2 minutes, then check status again

### Fixes

**If Scrappy is skipping due to "symbols unchanged"**:
- This should be fixed by the time-based refresh (30 min during premarket)
- If still happening, check that `is_premarket()` is returning true
- Check Redis for `stockbot:scrappy_auto:last_run_ts` and verify it's old enough

**If Scrappy is failing**:
- Check `last_failure_reason` in status
- Common causes:
  - Redis connection issues
  - DB connection issues
  - No symbols available (scanner not running)
  - Scrappy service crash (check Docker logs)

**If Scrappy hasn't run at all**:
- Check Docker service is running: `docker ps | grep scrappy_auto`
- Check service logs for startup errors
- Verify `SCRAPPY_AUTO_ENABLED=true` in `.env`
- Check bootstrap delay (30s) has passed

## What to Do If AI Referee Has No Coverage

### Symptoms
- AI Referee is enabled
- Focus symbols have fresh research
- But no AI assessments exist for focus symbols
- Pipeline stages show "researched" but not "ready"

### Diagnosis Steps

1. **Check AI Referee status**:
   ```bash
   curl http://localhost:8000/v1/runtime/status | jq '.ai_referee'
   ```
   - Verify `enabled: true`
   - Check `mode` (advisory vs required)
   - Check if API key is configured

2. **Check recent assessments**:
   ```bash
   curl http://localhost:8000/v1/ai-referee/recent?limit=10 | jq
   ```
   - Should show recent assessments if any exist
   - Check timestamps (should be recent if running)

3. **Check if AI Referee is being triggered**:
   - AI Referee is currently only triggered from worker when evaluating signals
   - No proactive premarket assessment service exists yet
   - This is expected behavior until Phase 3 (AI Referee premarket coverage) is implemented

### Current Limitation

**AI Referee does not proactively assess focus symbols during premarket**. It only runs when:
- Worker evaluates a signal for a symbol
- Signal has sufficient research (Scrappy snapshot)
- AI Referee is enabled and not blocked

### Workaround

- AI Referee will assess symbols when signals are generated (during market hours)
- For premarket prep, focus on ensuring Scrappy research is fresh
- Pipeline stage "researched" is acceptable for premarket; "ready" requires AI assessment which happens at signal time

### Future (Phase 3)

When AI Referee premarket coverage is implemented:
- Focus symbols with fresh research will be automatically assessed
- Assessments will appear in `/ai-referee/recent`
- Pipeline stages will show "ready" for assessed symbols

## Quick Validation Commands

### Check Overall Premarket Health
```bash
./scripts/premarket_validate.sh
```

### Check Individual Components
```bash
# Scanner
curl http://localhost:8000/v1/scanner/summary | jq

# Opportunities
curl http://localhost:8000/v1/opportunities/summary | jq
curl http://localhost:8000/v1/opportunities/now | jq '.opportunities[0:3]'

# Scrappy
curl http://localhost:8000/v1/scrappy/status | jq

# AI Referee
curl http://localhost:8000/v1/runtime/status | jq '.ai_referee'
curl http://localhost:8000/v1/ai-referee/recent?limit=5 | jq

# Paper arming
curl http://localhost:8000/v1/paper/arming-prerequisites | jq
```

### Manual Triggers (if needed)
```bash
# Trigger scanner
curl -X POST http://localhost:8000/v1/scanner/run/now

# Trigger Scrappy auto-run
curl -X POST http://localhost:8000/v1/scrappy/auto-run/now
```

## Expected Timestamps During Premarket

| Component | Update Frequency | Max Age (Healthy) |
|-----------|------------------|-------------------|
| Scanner last run | Every 2-5 min | < 5 minutes |
| Opportunity updated_at | Every 2-5 min | < 5 minutes |
| Scrappy last run | Every 30 min or on symbol change | < 2 hours |
| Scrappy last attempt | Every 30 min or on symbol change | < 2 hours |
| AI Referee assessments | On signal evaluation (not proactive) | N/A (not required for premarket) |

## Summary

**Premarket is "alive" when**:
- ✅ Scanner running every 2-5 minutes
- ✅ Opportunity engine producing focus symbols
- ✅ Scrappy refreshing every 30 minutes (or when symbols change)
- ✅ Focus symbols have fresh research coverage
- ✅ UI shows "Premarket alive" status

**If degraded**:
1. Check Scrappy status and logs
2. Verify scanner is running
3. Check Redis/DB connectivity
4. Manually trigger if needed
5. Review failure reasons

**If AI Referee has no coverage**:
- This is expected until Phase 3 implementation
- Focus on ensuring Scrappy research is fresh
- AI assessments happen at signal time, not proactively during premarket
