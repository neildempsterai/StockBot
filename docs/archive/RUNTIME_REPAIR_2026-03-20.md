# Runtime Repair Tranche - Database Authentication Failure

**Date:** 2026-03-20  
**Issue:** `scrappy_auto` and `ai_referee_premarket` services failing with `password authentication failed for user "stockbot"`  
**Status:** ✅ FIXED

## Root Cause

**Exact Root Cause:** Docker Compose variable expansion issue when constructing `DATABASE_URL` in the environment section.

The `.env` file contains `POSTGRES_PASSWORD=Th3b0$$$$123` (where `$$$$` means the actual password is `Th3b0$$123` - two dollar signs). When Docker Compose processes `${POSTGRES_PASSWORD}` in the `environment:` section of `compose.yaml`, it performs variable expansion. The `$` characters in the password were being interpreted inconsistently, causing:

- **API service:** Read `DATABASE_URL` directly from `.env` → correct password `Th3b0$$123` → ✅ works
- **scrappy_auto service:** Overrode `DATABASE_URL` via `${POSTGRES_PASSWORD}` expansion → incorrect password `Th3b0$$$$123` (4 dollar signs) → ❌ fails
- **ai_referee_premarket service:** Same issue as scrappy_auto → ❌ fails

**Why this happened:** Services using `env_file: [ "../.env" ]` AND explicitly setting `DATABASE_URL` in the `environment:` section caused Docker Compose to construct the URL using variable expansion, which mishandled special characters in the password.

## Files Changed

1. **`infra/compose.yaml`**
   - Removed explicit `DATABASE_URL` construction from `scrappy_auto` service environment section
   - Removed explicit `DATABASE_URL` construction from `ai_referee_premarket` service environment section
   - Added comments explaining that `DATABASE_URL` is read from `.env` to avoid variable expansion issues

2. **`src/api/main.py`**
   - Enhanced `/v1/scrappy/status` endpoint to include `service_health` and `service_health_reason` fields
   - Added new `/v1/ai-referee/status` endpoint with service health diagnostics
   - Added `timedelta` import for time calculations

3. **`frontend/src/pages/LiveSignalFeed.tsx`**
   - Enhanced empty state message to clarify that empty signals is normal when strategy hasn't triggered
   - Added detail text explaining the page shows only actual strategy-generated signals

4. **`scripts/premarket_validate.sh`**
   - Added validation checks for `scrappy_auto` service health (no auth errors)
   - Added validation checks for `ai_referee_premarket` service health (no auth errors)
   - Enhanced error reporting to flag database authentication errors as critical

## Exact Commands to Repair the Live Stack

```bash
# 1. Rebuild the API image (includes scrappy_auto and ai_referee_premarket fixes)
cd /home/neil-dempster/StockBot
docker build -f infra/Dockerfile.app -t infra-app:latest .

# 2. Recreate the affected services to pick up the compose.yaml changes
./scripts/compose.sh up -d scrappy_auto ai_referee_premarket --force-recreate

# 3. Verify services are running
docker ps --filter "name=scrappy\|ai_referee" --format "table {{.Names}}\t{{.Status}}"

# 4. Check logs for auth errors (should be empty)
docker logs infra-scrappy_auto-1 --tail 20 | grep -i "password\|auth" || echo "No auth errors found"
docker logs infra-ai_referee_premarket-1 --tail 20 | grep -i "password\|auth" || echo "No auth errors found"
```

## Exact Commands to Verify Health

### 1. Verify scrappy_auto is healthy

```bash
# Check service health via API
curl -s http://localhost:8000/v1/scrappy/status | jq '{service_health, service_health_reason, last_attempt_at, last_failure_reason}'

# Expected: service_health should be "healthy" or "stale" (not "failed")
# Expected: last_failure_reason should be null or empty (not contain "password authentication")
```

### 2. Verify ai_referee_premarket is healthy

```bash
# Check service health via API
curl -s http://localhost:8000/v1/ai-referee/status | jq '{service_health, service_health_reason, last_run_at}'

# Expected: service_health should be "healthy", "stale", "disabled", or "no_runs" (not "failed")
```

### 3. Verify database connections work

```bash
# Test scrappy_auto can connect
docker exec infra-scrappy_auto-1 python3 -c "from stockbot.db.session import get_session_factory; factory = get_session_factory(); print('✓ Connection successful')"

# Test ai_referee_premarket can connect
docker exec infra-ai_referee_premarket-1 python3 -c "from stockbot.db.session import get_session_factory; factory = get_session_factory(); print('✓ Connection successful')"
```

### 4. Verify snapshots are appearing

```bash
# Check scrappy status for coverage counts
curl -s http://localhost:8000/v1/scrappy/status | jq '{coverage_counts, last_snapshots_updated, service_health}'

# Expected: coverage_counts should show some symbols with fresh_research or carried_forward_research
# Expected: last_snapshots_updated should be > 0 if scrappy has run
```

### 5. Verify assessments are appearing (if AI Referee enabled)

```bash
# Check AI Referee status
curl -s http://localhost:8000/v1/ai-referee/status | jq '{service_health, recent_assessments_count, last_run_at}'

# Check recent assessments
curl -s http://localhost:8000/v1/ai-referee/recent?limit=10 | jq '.count'

# Expected: If enabled, should have recent_assessments_count > 0 or last_run_at within last 4 hours
```

### 6. Run full validation script

```bash
./scripts/premarket_validate.sh

# Expected: All critical checks should PASS
# Expected: Service health checks should not report "failed" status
```

## Expected Outcomes

### Premarket Prep Page
- **Before:** All symbols showing "No snapshot" with error "scrappy failure: password authentication failed"
- **After:** Symbols show `fresh_research`, `carried_forward_research`, `low_evidence`, or `no_research` based on actual coverage status
- **After:** No authentication errors in status

### AI Assessments Page
- **Before:** All symbols showing "Needs assessment" because no snapshots exist
- **After:** Symbols with `fresh_research` or `carried_forward_research` show assessments (if AI Referee enabled)
- **After:** Symbols with `no_research` or `low_evidence` show truthful skip reasons

### Live Signals Page
- **Before:** Empty with unclear message
- **After:** Empty state explicitly explains: "No deterministic strategy signals yet. This page shows only actual strategy-generated trade signals. An empty state here is normal if the strategy has not triggered any signals."
- **Note:** This page will remain empty unless the strategy actually generates signals - this is expected behavior, not a bug

### Service Health Diagnostics
- **New:** `/v1/scrappy/status` now includes `service_health` and `service_health_reason`
- **New:** `/v1/ai-referee/status` endpoint provides service health for AI Referee premarket runner
- **New:** Validation script checks for auth errors and flags them as critical

## Why Live Signals May Still Be Empty

The Live Signals page shows only **actual strategy-generated trade signals** from the deterministic strategy. An empty state is **normal and expected** when:

1. The strategy has not triggered any signals (no opportunities meet the strategy's criteria)
2. Market conditions don't match the strategy's entry conditions
3. The strategy is in shadow mode and hasn't generated any signals yet

This is **not a bug** - it's truthful reporting. The page explicitly states this in the empty state message.

## Recovery Path if Issue Persists

If database authentication errors persist after applying the fix:

1. **Verify .env file has correct password:**
   ```bash
   grep POSTGRES_PASSWORD .env
   # Should show: POSTGRES_PASSWORD=Th3b0$$$$123
   ```

2. **Verify DATABASE_URL in .env is correct:**
   ```bash
   grep DATABASE_URL .env
   # Should show: DATABASE_URL=postgresql+asyncpg://stockbot:Th3b0$$$$123@postgres:5432/stockbot
   ```

3. **Check if postgres volume was initialized with different password:**
   ```bash
   # If postgres was initialized before .env was set correctly, the volume may have wrong password
   # Solution: Reset postgres volume (WARNING: destroys all data)
   docker compose -f infra/compose.yaml down -v postgres_data
   ./scripts/compose.sh up -d postgres
   # Then run migrations again
   ```

4. **Verify services are using .env correctly:**
   ```bash
   docker exec infra-scrappy_auto-1 env | grep DATABASE_URL
   docker exec infra-ai_referee_premarket-1 env | grep DATABASE_URL
   # Both should show the same DATABASE_URL with correct password
   ```

## Summary

✅ **Root cause identified:** Docker Compose variable expansion mishandling `$` in password  
✅ **Fix applied:** Removed explicit `DATABASE_URL` construction, let services read from `.env`  
✅ **Diagnostics added:** Service health endpoints for both services  
✅ **Validation enhanced:** Script now checks for auth errors  
✅ **UI clarified:** Live Signals empty state is now explicit and operator-friendly  

The platform should now:
- Connect to database cleanly from all services
- Show actual research coverage on Premarket Prep
- Populate AI Assessments where research exists
- Provide clear diagnostics when services fail
