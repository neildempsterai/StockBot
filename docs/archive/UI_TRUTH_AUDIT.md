# UI Truth Audit - Frontend vs Backend Reality

**Date:** 2026-03-20  
**Status:** Audit complete, implementation in progress

---

## **AUDIT SUMMARY**

### **Critical Missing Truths in UI:**

1. **Command Center** - No paper exposure visibility
2. **Portfolio** - Shows raw broker positions, no lifecycle truth
3. **Signal Detail** - Raw JSON dump, no structured decision explanation
4. **System Health** - Missing paper arming state and safety posture
5. **Types** - Missing types for `/v1/paper/exposure` and `/v1/runtime/status`

---

## **PAGE-BY-PAGE AUDIT**

### **1. CommandCenter.tsx**

**Current Endpoints Used:**
- `/health`, `/health/detail`
- `/v1/metrics/summary`
- `/v1/strategies`
- `/v1/opportunities/now`, `/v1/opportunities/summary`, `/v1/opportunities/session`
- `/v1/scanner/summary`, `/v1/scanner/runs`
- `/v1/scrappy/status`
- `/v1/config`
- `/v1/paper/test/proof`

**Missing Critical Truths:**
- ❌ **No paper exposure** - `/v1/paper/exposure` not used
- ❌ **No safety strip** - Paper armed/disarmed, universe source, fallback reasons not shown prominently
- ❌ **No managed/orphaned status** - Can't see if positions are protected
- ❌ **No lifecycle status** - Can't see entry/exit order linkage
- ❌ **No runtime status** - `/v1/runtime/status` not used (has paper_armed, symbol_source, etc.)

**What Should Be Added:**
- Top safety strip showing: paper armed, paper armed reason, universe source, fallback reasons
- Live paper exposure section with all lifecycle fields
- Managed/orphaned warnings if any exist

---

### **2. Portfolio.tsx**

**Current Endpoints Used:**
- `/v1/shadow/trades`
- `/v1/metrics/summary`
- `/v1/account`
- `/v1/positions`
- `/v1/clock`
- `/v1/portfolio/history`

**Missing Critical Truths:**
- ❌ **No lifecycle data** - Uses `/v1/positions` (raw broker) instead of `/v1/paper/exposure` (lifecycle-enriched)
- ❌ **No entry thesis** - Can't see why position was opened
- ❌ **No stop/target/protection** - Exit plan not shown
- ❌ **No sizing logic** - Can't see why that qty was approved
- ❌ **No intelligence participation** - Scrappy/AI Referee not shown
- ❌ **No managed status** - Can't tell if position is protected
- ❌ **No compare-books** - `/v1/portfolio/compare-books` not used
- ❌ **No reconciliation** - `/v1/system/reconciliation` not used

**What Should Be Added:**
- Replace raw positions table with lifecycle-enriched exposure table
- Show stop/target/force-flat for each position
- Show protection mode and active status
- Show sizing summary
- Show intelligence badges
- Show managed/orphaned status
- Add compare-books summary
- Add reconciliation status

---

### **3. LiveSignalFeed.tsx**

**Current Endpoints Used:**
- `/v1/signals?limit=50`

**Missing Critical Truths:**
- ❌ **No paper order link** - Can't see if signal created a paper order
- ❌ **No lifecycle link** - Can't see if lifecycle exists
- ❌ **No intelligence summary** - Scrappy/AI Referee participation not shown
- ❌ **Limited reason codes** - Only shows first 2

**What Should Be Added:**
- Paper order indicator if `paper_order_id` exists
- Lifecycle status badge if lifecycle exists
- Intelligence participation badges
- Link to signal detail (already exists)

---

### **4. SignalDetail.tsx**

**Current Endpoints Used:**
- `/v1/signals/{signal_uuid}`

**Missing Critical Truths:**
- ❌ **Raw JSON dump** - Not operator-friendly
- ❌ **No structured decision explanation** - reason_codes, feature_snapshot not parsed
- ❌ **No lifecycle link** - Can't see if paper order/lifecycle exists
- ❌ **No intelligence detail** - Scrappy/AI Referee details not shown
- ❌ **No exit plan** - Stop/target not shown even if lifecycle exists

**What Should Be Added:**
- Structured display of reason_codes
- Feature snapshot summary
- Intelligence detail section (Scrappy/AI Referee)
- Lifecycle section if exists (stop/target/protection)
- Paper order link if exists

---

### **5. IntelligenceCenter.tsx**

**Current Endpoints Used:**
- `/v1/intelligence/recent`
- `/v1/intelligence/summary`
- `/v1/scrappy/status`
- `/v1/scrappy/auto-runs`

**Missing Critical Truths:**
- ⚠️ **Generally good** - Shows Scrappy status correctly
- ❌ **No AI Referee status** - Doesn't show AI Referee enabled/disabled state
- ❌ **No link to active paper positions** - Can't see which symbols have exposure with intelligence

**What Should Be Added:**
- AI Referee status section
- Link to symbols with active paper exposure
- Show latest intelligence for symbols with exposure

---

### **6. SystemHealth.tsx**

**Current Endpoints Used:**
- `/v1/health/detail`

**Missing Critical Truths:**
- ❌ **No paper arming state** - Doesn't use `/v1/runtime/status` which has `paper_trading_armed`
- ❌ **No paper prerequisites** - `/v1/paper/arming-prerequisites` not used
- ❌ **No operator test status** - Operator test enablement not shown
- ❌ **No safety posture** - Can't tell if platform is safe to trade
- ❌ **No reconciliation status** - `/v1/system/reconciliation` not used

**What Should Be Added:**
- Paper arming section (armed/disarmed, reason)
- Paper prerequisites check
- Operator test enablement
- Reconciliation status
- Safety posture summary

---

### **7. Missing Types**

**Types Not Defined:**
- ❌ `PaperExposureResponse` - For `/v1/paper/exposure`
- ❌ `RuntimeStatusResponse` - For `/v1/runtime/status`
- ❌ `PaperArmingPrerequisitesResponse` - For `/v1/paper/arming-prerequisites`
- ❌ `CompareBooksResponse` - For `/v1/portfolio/compare-books`
- ❌ `ReconciliationResponse` - For `/v1/system/reconciliation`

---

### **8. Missing Shared Components**

**Components Needed:**
- ❌ `ManagedStatusBadge` - Shows managed/orphaned/exited/pending/blocked
- ❌ `ProtectionModeBadge` - Shows broker_native/worker_mirrored/unprotected
- ❌ `SourceBadge` - Shows strategy_paper/operator_test/legacy_unknown
- ❌ `IntelligenceBadge` - Shows Scrappy/AI Referee participation
- ❌ `FallbackWarningBadge` - Shows static fallback warnings
- ❌ `LifecycleStatusBadge` - Shows lifecycle status
- ❌ `SizingSummary` - Shows sizing details compactly
- ❌ `SafetyStrip` - Top-of-page safety indicators

---

## **TRUTH OWNERSHIP MAP**

| Operator Question | Current Location | Should Be In |
|------------------|------------------|--------------|
| Why did we buy? | Signal detail (raw JSON) | Signal detail (structured) + Command Center exposure |
| What intelligence supported? | Not shown | Command Center + Portfolio + Signal detail |
| Scrappy involved? | Not shown | Command Center + Portfolio + Signal detail |
| AI Referee involved? | Not shown | Command Center + Portfolio + Signal detail |
| What size logic? | Not shown | Portfolio + Signal detail |
| What is stop? | Not shown | Command Center + Portfolio |
| What is target? | Not shown | Command Center + Portfolio |
| Protection mode? | Not shown | Command Center + Portfolio |
| Exit submitted? | Not shown | Command Center + Portfolio |
| Managed/orphaned? | Not shown | Command Center + Portfolio |
| Strategy vs operator? | Not shown | Command Center + Portfolio |
| Static fallback? | Health detail (buried) | Command Center safety strip + System Health |
| Paper armed? | Not shown | Command Center safety strip + System Health |
| What's blocked? | Not shown | System Health + Command Center |

---

## **MISLEADING BY OMISSION**

1. **Portfolio shows raw broker positions** - Makes it look like positions are unmanaged
2. **Command Center shows opportunities but not exposure** - Hides actual risk
3. **Signal detail is raw JSON** - Doesn't explain the decision
4. **System Health doesn't show paper state** - Can't tell if safe to trade
5. **No safety strip anywhere** - Critical warnings buried

---

## **IMPLEMENTATION PRIORITY**

1. **Phase 2** (Command Center) - Highest priority - operator's main view
2. **Phase 3** (Portfolio) - High priority - shows actual positions
3. **Phase 7** (Types/Components) - Required for Phases 2-3
4. **Phase 4** (Signals) - Medium priority - decision explanation
5. **Phase 6** (System Health) - Medium priority - safety posture
6. **Phase 5** (Intelligence) - Lower priority - already mostly good
