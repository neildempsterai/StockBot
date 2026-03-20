# UI Information Architecture Cleanup Plan

## Current Duplications Identified

### 1. Live Paper Exposure Table
- **Command Center**: Full table with 15 columns
- **Portfolio**: Full table with 19 columns (includes P&L)
- **Decision**: Keep full table only in Portfolio. Command Center shows condensed summary with link.

### 2. Paper Account KPIs
- **Command Center**: "Real Paper Trading" section (Equity, Cash, Open Positions, Closed Orders, Portfolio Value)
- **Portfolio**: "Paper Account" section (Equity, Cash, Buying power, Open positions, Market)
- **Decision**: Keep only in Portfolio. Command Center shows count and link.

### 3. Shadow Metrics
- **Command Center**: "Shadow Trading (Simulation)" KPI cards
- **Portfolio**: "Shadow Book" KPI cards
- **Decision**: Keep in Portfolio only. Command Center removes.

### 4. System Status
- **Command Center**: System Status section (API, Strategy, Mode, Session)
- **System Health**: Comprehensive health details
- **Decision**: Keep minimal status in Command Center, full details in System Health.

## New Page Ownership Model

### Command Center = Live Operator Console
**Purpose**: Quick status, critical alerts, top opportunities

**Keep:**
- SafetyStrip
- Condensed paper exposure summary (count, orphaned warning, link to Portfolio)
- Critical warnings (orphaned, static fallback, paper disarmed)
- Top Opportunities Now
- Minimal system status (API OK, Strategy active)

**Remove/Move:**
- Full Live Paper Exposure table → Portfolio
- Real Paper Trading KPI block → Portfolio
- Shadow Trading section → Portfolio
- Paper test proof → System Health
- Scanner history → System Health
- Scrappy automation details → Intelligence Center
- Execution & modes → System Health
- Scanner Status → System Health

### Portfolio = Full Paper Account + Lifecycle Detail
**Purpose**: Complete lifecycle inspection, account details, reconciliation

**Keep:**
- Paper Account KPIs
- Equity Curve
- Full Paper Exposure & Lifecycle table (canonical)
- Compare Books
- Reconciliation
- Shadow Book summary

**Enhance:**
- Make it clear this is the detail page
- Add prominent link from Command Center

### Orders = Broker/Order Ledger
**Purpose**: Order history, source tracking, signal links

**Keep:**
- All order details
- Source column
- Signal links

### Signals = Trade Rationale and Signal Lifecycle
**Purpose**: Why trades happened, signal detail, lifecycle links

**Keep:**
- Signal feed with status
- Signal detail with lifecycle

### Intelligence = Scrappy Context
**Purpose**: Intelligence snapshots, live position context

**Keep:**
- Recent snapshots
- Live position indicators

### AI Referee = Assessment Context
**Purpose**: AI Referee assessments, live position context

**Keep:**
- Recent assessments
- Live position indicators

### System Health = Safety Blockers and Runtime Status
**Purpose**: Complete system status, prerequisites, blockers

**Keep:**
- All current health details
- Paper arming prerequisites
- Service status
- Symbol source details
- Paper exposure status
- Reconciliation

**Add:**
- Paper test proof (moved from Command Center)
- Scanner history (moved from Command Center)
- Execution & modes (moved from Command Center)
- Scanner Status (moved from Command Center)

## Visual Hierarchy Improvements

### Critical Alerts (Dominant)
- Orphaned/unmanaged exposure
- No protection
- Static fallback at entry
- Paper disarmed
- Broker unavailable
- Reconciliation mismatch

### Important Context (Second)
- Source
- Managed status
- Protection mode
- Intelligence participation

### Detail (Third)
- Sizing
- Raw IDs
- Timestamps

## Implementation Steps

1. Simplify Command Center
2. Enhance Portfolio as canonical detail page
3. Move sections to appropriate pages
4. Improve visual hierarchy
5. Tighten labels
6. Test navigation
