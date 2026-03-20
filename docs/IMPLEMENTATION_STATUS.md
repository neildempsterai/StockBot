# Emergency Rescue + Completion Tranche - Implementation Status

**Date:** 2026-03-20  
**Git Commit:** HEAD (latest push)  
**Status:** **PARTIALLY IMPLEMENTED** - Phases 0-2 complete, Phases 3-6 incomplete

---

## ✅ **PHASE 0 — INCIDENT CONTAINMENT AND DIAGNOSIS** (COMPLETE)

### 1. Global Paper Kill Switch ✅
- **Implementation:** Redis-backed (`stockbot:paper:armed`) + config (`PAPER_TRADING_ARMED`)
- **Default:** Safe (disarmed by default)
- **Endpoints:** `POST /v1/paper/arm`, `POST /v1/paper/disarm`
- **Runtime Status:** `GET /v1/runtime/status` shows `paper_trading_armed` and `paper_armed_reason`
- **Worker Blocking:** ✅ Worker checks both config and Redis before paper submission
- **Operator Test Blocking:** ✅ All operator test routes check `_paper_effective_armed()` and return 403 if disarmed
- **Files:** `src/api/main.py`, `src/worker/main.py`, `src/stockbot/execution/paper_test.py`

### 2. Order Source Classification ✅
- **Implementation:** `order_source` field: `strategy_paper` | `operator_test` | `legacy_unknown`
- **Persistence:** `PaperOrder.order_origin` and `order_intent` in DB
- **Exposure:** `GET /v1/orders` and `GET /v1/paper/exposure` show `order_source`
- **Migration:** `015_paper_order_origin_intent.py`
- **Files:** `src/api/main.py`, `src/stockbot/execution/paper_test.py`, `src/stockbot/db/models.py`

### 3. Current Exposure Diagnosis ✅
- **Endpoint:** `GET /v1/paper/exposure`
- **Fields Exposed:**
  - ✅ symbol, source, entry_ts
  - ✅ strategy_id, strategy_version, signal_uuid (when strategy-driven)
  - ✅ operator_intent (when operator_test)
  - ✅ scrappy_at_entry, scrappy_detail (snapshot_id, freshness, direction, evidence_count, headline_count, flags)
  - ✅ ai_referee_at_entry, ai_referee_detail (model, version, decision_class, score, flags, rationale)
  - ⚠️ sizing_at_entry: **NOT PERSISTED** (returns `None`)
  - ⚠️ exit_plan_status: **HARDCODED** as `"not_persisted"`
  - ⚠️ broker_protection: **HARDCODED** as `"unknown"`
  - ⚠️ orphaned: Only checks `legacy_unknown` (no exit plan check yet)
  - ⚠️ static_fallback_at_entry: **HARDCODED** as `"unknown"`
- **Files:** `src/api/main.py` (lines 825-931)

### 4. No Auto-Liquidation ✅
- **Approach:** Disarm by default, surface unmanaged exposure, provide runbook
- **Documentation:** `docs/PAPER_OPERATOR_RUNBOOK.md` section 3

---

## ✅ **PHASE 1 — FIX ORDER AUTHORITY AND GATING** (COMPLETE)

### 1. Strategy as Sole Authority ✅
- **Implementation:** Strategy logic in `src/worker/main.py`; operator test routes separate
- **Files:** `src/worker/main.py`, `src/stockbot/execution/paper_test.py`

### 2. Operator Test Routes Marked ✅
- **Implementation:** All operator test responses include `"_operator_only": True`
- **Files:** `src/stockbot/execution/paper_test.py`

### 3. Operator Test Routes Blocked by Default ✅
- **Config:** `OPERATOR_PAPER_TEST_ENABLED` (default: `false`)
- **Caps:** 
  - `OPERATOR_PAPER_TEST_MAX_QTY` (default: `1`)
  - `OPERATOR_PAPER_TEST_MAX_NOTIONAL` (default: `500.0`)
- **Implementation:** `_operator_paper_test_guard()` checks enable flag; `_apply_operator_caps()` enforces limits
- **Files:** `src/stockbot/config.py`, `src/stockbot/execution/paper_test.py`, `src/api/main.py`

### 4. Paper Arming Prerequisites ✅
- **Endpoint:** `GET /v1/paper/arming-prerequisites`
- **Checks:**
  - ✅ paper execution enabled
  - ✅ credentials configured
  - ✅ broker reachable
  - ✅ DB reachable
  - ✅ Redis reachable
  - ✅ worker heartbeat present
  - ✅ market gateway heartbeat present
  - ✅ dynamic universe available and fresh
  - ⚠️ exit protection mode: **NOT CHECKED** (Phase 3 not complete)
  - ⚠️ deterministic strategy active: **NOT CHECKED** (assumed active)
  - ⚠️ Scrappy/AI Referee required: **NOT ENFORCED** (advisory by default)
- **Files:** `src/api/main.py` (lines 967-1029)

### 5. Static Fallback Blocking ✅
- **Implementation:** `_paper_allowed_universe()` checks gateway and worker symbol source
- **Blocking:** Paper submission blocked if either on static fallback
- **Runtime Status:** `GET /v1/runtime/status` shows `symbol_source.gateway.active_source` and `symbol_source.worker.active_source`
- **Files:** `src/worker/main.py` (lines 463-500), `src/api/main.py`

---

## ✅ **PHASE 2 — MAKE SCRAPPY AND AI REFEREE WORK** (COMPLETE)

### 1. Scrappy Representation ✅
- **Persistence:** `Signal.intelligence_snapshot_id` links to `SymbolIntelligenceSnapshot`
- **Exposure:** `GET /v1/paper/exposure` shows `scrappy_at_entry` and `scrappy_detail`:
  - snapshot_id, freshness_minutes, catalyst_direction, evidence_count, headline_count, stale_flag, conflict_flag
- **Signal Detail:** Available via signal UUID lookup
- **Files:** `src/api/main.py` (lines 883-895), `src/worker/main.py` (lines 708-731)

### 2. AI Referee Representation ✅
- **Persistence:** `Signal.ai_referee_assessment_id` links to `AiRefereeAssessment`
- **Exposure:** `GET /v1/paper/exposure` shows `ai_referee_at_entry` and `ai_referee_detail`:
  - ran, model_name, referee_version, decision_class, setup_quality_score, contradiction_flag, stale_flag, evidence_sufficiency, plain_english_rationale
- **Signal Detail:** Available via signal UUID lookup
- **Files:** `src/api/main.py` (lines 896-907), `src/worker/main.py` (lines 733-799)

### 3. Runtime Truth Visibility ✅
- **Endpoint:** `GET /v1/runtime/status`
- **Shows:**
  - ✅ scrappy.mode, scrappy.required_for_paper (config-based)
  - ✅ ai_referee.enabled, ai_referee.mode, ai_referee.required_for_paper (config-based)
  - ✅ symbol_source.gateway.active_source, symbol_source.worker.active_source
  - ✅ paper_trading_armed, paper_armed_reason
  - ⚠️ exit_protection_mode: **NOT EXPOSED** (Phase 3 not complete)
  - ✅ operator_paper_test.enabled, operator_paper_test.max_qty, operator_paper_test.max_notional
- **Files:** `src/api/main.py` (lines 270-320)

---

## ❌ **PHASE 3 — FIX THE PAPER EXIT LIFECYCLE** (NOT IMPLEMENTED)

### 1. Exit Plan Persistence ❌
- **Status:** **NOT PERSISTED**
- **Current:** `exit_plan_status` hardcoded as `"not_persisted"` in exposure endpoint
- **Required:** DB model for `PaperExitPlan` with stop_price, target_price, force_flat_time, exit_mode, protection_mode
- **Missing:** Persistence at entry time in `src/worker/main.py` when paper order submitted

### 2. Broker-Native Protection ❌
- **Status:** **NOT IMPLEMENTED**
- **Current:** No bracket/OCO/OTO orders; all orders are simple market/limit
- **Required:** Extend Alpaca client to support bracket orders or attached stop-loss/take-profit
- **Files:** `src/stockbot/alpaca/client.py` (needs extension)

### 3. Mirror Shadow Exits to Paper ❌
- **Status:** **PARTIALLY IMPLEMENTED**
- **Force-Flat:** ✅ Mirrored (lines 544-558 in `src/worker/main.py`)
- **Stop Hit:** ❌ **NOT MIRRORED** - shadow engine detects stop hits but doesn't submit paper close
- **Target Hit:** ❌ **NOT MIRRORED** - shadow engine detects target hits but doesn't submit paper close
- **Required:** In `src/worker/main.py`, when `resolve_exit_conservative()` returns `exit_reason` of `"stop"` or `"target"`, submit matching paper close order
- **Files:** `src/worker/main.py` (lines 600-650 need modification), `src/stockbot/shadow/engine.py`

### 4. Lifecycle Linking ⚠️
- **Status:** **PARTIAL**
- **Entry Order:** ✅ Linked via `Signal.paper_order_id`
- **Exit Order:** ❌ **NOT LINKED** - no `PaperExitOrder` model or linking
- **Signal:** ✅ Exists
- **Shadow Trade:** ✅ Exists
- **Paper Fills:** ✅ Tracked via `PaperOrderEvent`
- **Paper Proof:** ✅ Exists via `GET /v1/paper/test/proof`
- **Reconciliation:** ✅ Exists via reconciler
- **Missing:** Exit order linking and exit plan → exit order relationship

### 5. Orphan Detection ⚠️
- **Status:** **PARTIAL**
- **Current:** Only checks `order_source == "legacy_unknown"` for orphaned flag
- **Missing:** Check for positions without live exit plan or without shadow alignment
- **Required:** Query exit plan table and shadow state to determine if position is truly orphaned

---

## ❌ **PHASE 4 — TIGHTEN RISK AND SIZING** (NOT IMPLEMENTED)

### 1. Strategy Paper Sizing Persistence ❌
- **Status:** **NOT PERSISTED**
- **Current:** `sizing_at_entry` returns `None` in exposure endpoint
- **Sizing Logic:** ✅ Exists in `src/stockbot/risk/sizing.py` and called in worker
- **Required:** Persist sizing result (account_equity, buying_power, stop_distance, risk_dollars, approved_qty, notional, rejection_reason) to `PaperOrder` or new `PaperSizing` model
- **Files:** `src/worker/main.py` (lines 871-902 compute sizing but don't persist), `src/api/main.py` (exposure endpoint can't retrieve it)

### 2. Safe Paper Defaults ⚠️
- **Status:** **CONFIG EXISTS, VISIBILITY PARTIAL**
- **Config:** ✅ Safe defaults in `src/stockbot/config.py`:
  - `risk_per_trade_pct_equity: 0.5`
  - `max_position_pct_equity: 10.0`
  - `max_concurrent_positions: 5`
  - `max_gross_exposure_pct_equity: 50.0`
  - `max_symbol_exposure_pct_equity: 20.0`
- **Runtime Status:** ⚠️ Not exposed in `GET /v1/runtime/status` or `GET /v1/config`
- **Required:** Expose paper sizing defaults in runtime status or config endpoint

### 3. Operator Test Caps ✅
- **Status:** **IMPLEMENTED**
- **Config:** `OPERATOR_PAPER_TEST_MAX_QTY=1`, `OPERATOR_PAPER_TEST_MAX_NOTIONAL=500.0`
- **Enforcement:** ✅ `_apply_operator_caps()` in `src/stockbot/execution/paper_test.py`
- **Files:** `src/stockbot/config.py`, `src/stockbot/execution/paper_test.py`

---

## ⚠️ **PHASE 5 — MAKE OPERATOR SURFACES TRUTHFUL** (PARTIALLY COMPLETE)

### 1. Signal/Order/Position Detail ⚠️
- **Status:** **PARTIAL**
- **Available:**
  - ✅ why trade happened (reason_codes, feature_snapshot via signal)
  - ✅ intelligence supported (scrappy_detail, ai_referee_detail)
  - ✅ Scrappy participation (scrappy_at_entry, scrappy_detail)
  - ✅ AI Referee participation (ai_referee_at_entry, ai_referee_detail)
  - ✅ deterministic rules (reason_codes, feature_snapshot)
  - ❌ size logic: **NOT PERSISTED** (sizing_at_entry is None)
  - ❌ exit plan: **NOT PERSISTED** (exit_plan_status is "not_persisted")
  - ❌ paper protection active: **UNKNOWN** (broker_protection is "unknown")
  - ✅ order source (strategy_paper vs operator_test)
- **Endpoints:** `GET /v1/paper/exposure`, `GET /v1/signals/{signal_uuid}`, `GET /v1/orders/{order_id}`

### 2. Command Center / Operator Surfaces ⚠️
- **Status:** **PARTIAL**
- **UI:** ✅ Rebuilt with React + Vite
- **Available:**
  - ✅ paper armed/disarmed (via runtime status)
  - ✅ dynamic universe fresh/stale/static fallback (via runtime status)
  - ✅ scanner live/blocked/empty (via health/detail)
  - ✅ scrappy live/absent/stale (via scrappy status)
  - ✅ ai referee enabled/disabled/unavailable (via runtime status)
  - ⚠️ current open paper exposure: **EXPOSED** but missing exit plan and sizing
  - ⚠️ managed vs unmanaged: **PARTIAL** (only legacy_unknown check)
  - ⚠️ route to flatten/rescue: **DOCUMENTED** but not surfaced in UI
- **Files:** `frontend/src/pages/CommandCenter.tsx`, `frontend/src/pages/SystemHealth.tsx`

### 3. No Fake Values ✅
- **Status:** **COMPLIANT**
- **Approach:** All endpoints return real data or honest "not_available"/"not_persisted" states
- **Files:** `src/api/main.py` (exposure endpoint uses real data or explicit "not_persisted"/"unknown")

---

## ⚠️ **PHASE 6 — FULL VALIDATION AND LIVE PAPER TESTING** (PARTIALLY COMPLETE)

### 1. Full-Stack Runtime Validation ✅
- **Script:** `scripts/runtime_truth_validate.sh`
- **Status:** ✅ Exists
- **Tests:** `tests/test_api_runtime_truth.py`, `tests/test_worker_universe_runtime.py`, `tests/test_gateway_symbol_refresh.py`

### 2. Contract Tests ✅
- **Tests:** `tests/test_paper_lifecycle.py` validates API contract shapes
- **Status:** ✅ Exists

### 3. Focused Tests ⚠️
- **Status:** **PARTIAL**
- **Implemented:**
  - ✅ Paper kill switch (via operator test guard checks)
  - ✅ Operator test routes blocked by default (via guard checks)
  - ✅ Paper arming prerequisites (endpoint exists)
  - ✅ Static fallback blocks paper (worker logic)
- **Missing Tests:**
  - ❌ Scrappy/AI Referee paper prerequisites (not enforced, so no test)
  - ❌ Strategy paper entry provenance (no explicit test)
  - ❌ Strategy paper stop/target/force-flat exit mirroring (not implemented)
  - ❌ Orphan detection (partial implementation)
  - ❌ Compare-books truth (reconciliation exists but no focused test)
  - ❌ Reconciliation truth (reconciler exists but no focused test)

### 4. Gated Live Paper Validation ✅
- **Script:** `scripts/paper_lifecycle_validate.sh`
- **Status:** ✅ Exists, tests four flows (buy-open, sell-close, short-open, buy-cover)
- **Gating:** ✅ Requires `ENABLE_LIVE_PAPER_VALIDATION=1` and credentials
- **Evidence:** ✅ Writes artifacts to `artifacts/paper_lifecycle_<timestamp>/`
- **Limitation:** ⚠️ Only tests operator test routes, not strategy paper entry/exit lifecycle

---

## ✅ **PHASE 7 — DOCUMENTATION AND OPERATOR RUNBOOK** (COMPLETE)

### 1-8. Runbook Coverage ✅
- **File:** `docs/PAPER_OPERATOR_RUNBOOK.md`
- **Covers:**
  - ✅ How to disarm paper immediately
  - ✅ How to identify order source (strategy_paper vs operator_test)
  - ✅ How to inspect managed/orphaned positions
  - ✅ How to see intelligence and rationale
  - ✅ How to verify exit plan (notes Phase 3 incomplete)
  - ✅ How to re-arm paper safely
  - ✅ How to run safe live paper tests
  - ✅ How to validate scanner/Scrappy/AI Referee/strategy participation
- **Additional:** `docs/INTELLIGENCE_AND_AI_REFEREE.md` exists

---

## 📊 **SUMMARY**

### ✅ **COMPLETE (Phases 0, 1, 2, 7)**
- Phase 0: Incident containment (kill switch, order classification, exposure diagnosis structure)
- Phase 1: Order authority and gating (strategy authority, operator test blocking/caps, prerequisites, static fallback blocking)
- Phase 2: Scrappy and AI Referee visibility (persistence, exposure, runtime status)
- Phase 7: Documentation (runbook complete)

### ❌ **NOT IMPLEMENTED (Phases 3, 4)**
- **Phase 3:** Paper exit lifecycle (exit plan persistence, broker-native protection, stop/target mirroring, orphan detection)
- **Phase 4:** Risk/sizing persistence and visibility (sizing not persisted, defaults not fully exposed)

### ⚠️ **PARTIALLY COMPLETE (Phases 5, 6)**
- **Phase 5:** Operator surfaces (UI rebuilt, but missing exit plan and sizing visibility)
- **Phase 6:** Validation (scripts exist, but missing focused tests for Phase 3-4 features)

---

## 🚨 **REMAINING BLOCKERS**

### Critical (Blocks "Fully Operational" Status)
1. **Exit Plan Persistence** (Phase 3.1)
   - No DB model for exit plans
   - Exit plan not persisted at entry time
   - Exposure endpoint hardcodes `"not_persisted"`

2. **Stop/Target Exit Mirroring** (Phase 3.3)
   - Shadow engine detects stop/target hits but doesn't submit paper closes
   - Only force-flat is mirrored

3. **Sizing Persistence** (Phase 4.1)
   - Sizing computed but not persisted
   - Exposure endpoint can't show sizing details

### Important (Blocks Complete Visibility)
4. **Broker-Native Protection** (Phase 3.2)
   - No bracket/OCO/OTO orders
   - All protection must be worker-mirrored

5. **Orphan Detection** (Phase 3.5)
   - Only checks `legacy_unknown`
   - Doesn't check for missing exit plans or shadow misalignment

6. **Safe Defaults Visibility** (Phase 4.2)
   - Config exists but not exposed in runtime status

---

## 📝 **DEFINITION OF DONE CHECKLIST**

1. ✅ Paper is disarmed by default or otherwise safely governed
2. ✅ Operator paper test routes are blocked by default and capped when enabled
3. ✅ Strategy paper trading cannot occur from static fallback symbols
4. ⚠️ Strategy paper trading cannot occur without explicit, visible intelligence participation rules (visible but not enforced as required)
5. ⚠️ Every paper order has full provenance and explainability (missing sizing and exit plan)
6. ❌ Every paper order has a real exit plan (not persisted)
7. ❌ Paper stop/target/force-flat lifecycle is actually implemented and traceable (only force-flat works)
8. ⚠️ Current exposure can be classified as managed or unmanaged at a glance (partial - only legacy_unknown)
9. ⚠️ Runtime/operator surfaces are truthful (missing exit plan and sizing)
10. ⚠️ Full-stack validation and safe live paper validation both pass (scripts exist but don't test Phase 3-4)

**Overall Status:** **~60% Complete** (Phases 0-2, 7 done; Phases 3-4 not done; Phases 5-6 partial)

---

## 🔧 **NEXT STEPS TO COMPLETE**

### Priority 1: Phase 3 (Exit Lifecycle)
1. Create `PaperExitPlan` DB model and migration
2. Persist exit plan at entry time in worker
3. Implement stop/target hit detection and paper close submission
4. Link exit orders to exit plans
5. Enhance orphan detection

### Priority 2: Phase 4 (Sizing Visibility)
1. Persist sizing result to `PaperOrder` or new model
2. Expose sizing in exposure endpoint
3. Expose safe defaults in runtime status

### Priority 3: Phase 5-6 (UI and Tests)
1. Wire exit plan and sizing into UI
2. Add focused tests for Phase 3-4 features
3. Enhance live validation to test strategy paper lifecycle
