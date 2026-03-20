# UI Information Architecture Cleanup Summary

## What Was Duplicated Before

### 1. Live Paper Exposure Table
- **Command Center**: Full 15-column table with all lifecycle details
- **Portfolio**: Full 19-column table with P&L data
- **Impact**: Operator saw same data twice, cluttered Command Center

### 2. Paper Account KPIs
- **Command Center**: "Real Paper Trading" section (Equity, Cash, Open Positions, Closed Orders, Portfolio Value)
- **Portfolio**: "Paper Account" section (Equity, Cash, Buying power, Open positions, Market)
- **Impact**: Redundant account summary in Command Center

### 3. Shadow Metrics
- **Command Center**: "Shadow Trading (Simulation)" KPI cards
- **Portfolio**: "Shadow Book" KPI cards
- **Impact**: Shadow data shown in both places

### 4. System Status Details
- **Command Center**: Multiple sections (System Status, Execution & modes, Scanner Status, Scanner History, Scrappy automation, Paper test proof)
- **System Health**: Comprehensive health details
- **Impact**: Command Center overloaded with system details better suited for System Health page

## New Page Ownership Model

### Command Center = Live Operator Console
**Purpose**: Quick status, critical alerts, top opportunities

**What Stays:**
- SafetyStrip (critical safety status)
- Paper Exposure Summary (condensed: counts, orphaned warning, link to Portfolio)
- Critical warnings (orphaned, static fallback, no protection)
- Top Opportunities Now (scanner-ranked candidates)
- Minimal System Status (API OK, Strategy active, Session) with link to System Health

**What Was Removed/Moved:**
- ✅ Full Live Paper Exposure table → Portfolio (canonical detail)
- ✅ Real Paper Trading KPI block → Portfolio
- ✅ Shadow Trading section → Portfolio
- ✅ Paper test proof → System Health
- ✅ Scanner history → System Health
- ✅ Scrappy automation details → Intelligence Center (already there)
- ✅ Execution & modes → System Health
- ✅ Scanner Status → System Health
- ✅ Quick Links section → Removed (navigation already in sidebar)

### Portfolio = Full Paper Account + Lifecycle Detail
**Purpose**: Complete lifecycle inspection, account details, reconciliation

**What Stays:**
- Paper Account KPIs (Equity, Cash, Buying power, Open positions, Market)
- Equity Curve (portfolio value over time)
- Full Paper Exposure & Lifecycle table (canonical - 19 columns with P&L)
- Compare Books (paper vs shadow summary)
- Reconciliation (latest reconciliation run)
- Shadow Book summary

**Enhancements:**
- Enhanced critical warnings (orphaned count, static fallback count, no protection count)
- Clear subtitle: "canonical view for all position inspection"
- Prominent link from Command Center

### Orders = Broker/Order Ledger
**Purpose**: Order history, source tracking, signal links

**Status**: Already well-defined, no changes needed

### Signals = Trade Rationale and Signal Lifecycle
**Purpose**: Why trades happened, signal detail, lifecycle links

**Status**: Already well-defined, no changes needed

### Intelligence = Scrappy Context
**Purpose**: Intelligence snapshots, live position context

**Status**: Already well-defined, no changes needed

### AI Referee = Assessment Context
**Purpose**: AI Referee assessments, live position context

**Status**: Already well-defined, no changes needed

### System Health = Safety Blockers and Runtime Status
**Purpose**: Complete system status, prerequisites, blockers

**What Was Added (moved from Command Center):**
- ✅ Paper test proof section
- ✅ Scanner history section
- ✅ Execution & modes section
- ✅ Scanner Status section

**What Stays:**
- Paper Trading Safety Posture
- Services status
- Symbol Source & Universe
- Paper Exposure Status
- Reconciliation

## Visual Hierarchy Improvements

### Critical Alerts (Dominant - Red/Warning)
- Orphaned/unmanaged exposure → Shown prominently in Command Center summary and Portfolio table
- Static fallback at entry → Warning banner in both pages
- No protection → Warning banner in both pages
- Paper disarmed → SafetyStrip
- Broker unavailable → SafetyStrip and System Health
- Reconciliation mismatch → System Health

### Important Context (Second - Badges/Status)
- Source (strategy_paper/operator_test) → Badge in tables
- Managed status → Badge in tables
- Protection mode → Badge in tables
- Intelligence participation → Badge in tables

### Detail (Third - Small text/links)
- Sizing → Compact summary in tables
- Raw IDs → Small text in Details column
- Timestamps → Small text in Entry column

## Exact Files Changed

### Frontend
1. **`frontend/src/pages/CommandCenter.tsx`**
   - Removed: Full Live Paper Exposure table (15 columns)
   - Removed: Real Paper Trading KPI section
   - Removed: Shadow Trading section
   - Removed: Paper test proof section
   - Removed: Scanner history section
   - Removed: Scrappy automation section
   - Removed: Execution & modes section
   - Removed: Scanner Status section
   - Removed: Quick Links section
   - Added: Condensed Paper Exposure Summary (4 KPIs + warnings + link to Portfolio)
   - Simplified: System Status to 3 KPIs with link to System Health
   - Removed unused imports and queries

2. **`frontend/src/pages/Portfolio.tsx`**
   - Enhanced: Critical warnings with counts
   - Enhanced: Subtitle to clarify canonical role
   - No structural changes (already had full table)

3. **`frontend/src/pages/SystemHealth.tsx`**
   - Added: Paper test proof section
   - Added: Scanner history section
   - Added: Execution & modes section
   - Added: Scanner Status section
   - Added imports for moved data

4. **`frontend/src/pages/IntelligenceCenter.tsx`**
   - Minor: Updated section title from "Scrappy intelligence" to "Scrappy Automation" for consistency

### Documentation
- **`docs/UI_CLEANUP_PLAN.md`** - Cleanup plan document
- **`docs/UI_CLEANUP_SUMMARY.md`** - This summary document

## What Moved Off Command Center

1. **Full Live Paper Exposure table** → Portfolio (canonical detail)
2. **Real Paper Trading KPI block** → Portfolio
3. **Shadow Trading section** → Portfolio
4. **Paper test proof** → System Health
5. **Scanner history** → System Health
6. **Execution & modes** → System Health
7. **Scanner Status** → System Health
8. **Quick Links** → Removed (sidebar navigation sufficient)

## What Stayed on Command Center

1. **SafetyStrip** - Critical safety status
2. **Paper Exposure Summary** - Condensed view (counts, warnings, link to Portfolio)
3. **Critical warnings** - Orphaned, static fallback, no protection
4. **Top Opportunities Now** - Scanner-ranked candidates
5. **Minimal System Status** - API, Strategy, Session (with link to System Health)

## Why the UI is Now Easier to Operate During Market Hours

### Before (Cluttered)
- Command Center had 10+ sections
- Full lifecycle table duplicated in Command Center and Portfolio
- System details mixed with operator console
- Hard to find critical alerts
- Information overload

### After (Focused)
- **Command Center**: 3 focused sections (Exposure Summary, System Status, Opportunities)
- **Portfolio**: Clear canonical detail page for lifecycle inspection
- **System Health**: All system details in one place
- **Critical alerts**: Prominently displayed in Command Center summary
- **Clear navigation**: Links guide operator to detail pages

### Operator Flow
1. **Command Center** → See critical alerts, exposure summary, top opportunities
2. **Portfolio** → Click link to see full lifecycle detail
3. **System Health** → Click link to see full system status
4. **Orders/Signals/Intelligence** → Clear roles, no duplication

## Definition of Done - Status

✅ **Command Center feels focused** - Reduced from 10+ sections to 3 core sections
✅ **Portfolio feels authoritative** - Clear canonical role, enhanced warnings
✅ **Orders/Signals/Intelligence/AI pages have clear roles** - No changes needed, already clear
✅ **No critical truth is hidden** - All critical alerts prominently displayed
✅ **Duplicated sections are reduced sharply** - Full table only in Portfolio, summary in Command Center

## Navigation Flow

**Command Center → Portfolio**: Direct link in Paper Exposure Summary
**Command Center → System Health**: Direct link in System Status
**Portfolio → Orders**: Via order IDs in Details column
**Portfolio → Signals**: Via signal links in Details column
**Orders → Signals**: Via signal links in Source column

All navigation is 1-2 clicks as required.
