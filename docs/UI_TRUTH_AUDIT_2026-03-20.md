# UI Truth Audit - March 20, 2026

## Executive Summary

This audit reviews the current UI state against the 16 critical operator questions and identifies gaps, duplications, and misleading omissions.

## Operator Questions Checklist

### ✅ = Fully Answerable | ⚠️ = Partially Answerable | ❌ = Not Answerable

1. **What positions are open right now?** ✅
   - Command Center: Live Paper Exposure table
   - Portfolio: Paper Exposure & Lifecycle table
   - Both use `/v1/paper/exposure`

2. **Why does each one exist?** ⚠️
   - Shows source (strategy_paper/operator_test/legacy_unknown)
   - Shows signal_uuid link
   - **GAP**: Missing clear "thesis" or "reason_codes" summary in exposure table

3. **Did it come from strategy_paper or operator_test?** ✅
   - SourceBadge shows this clearly
   - Command Center and Portfolio both display

4. **What intelligence supported it?** ⚠️
   - IntelligenceBadge shows Scrappy/AI Referee participation
   - **GAP**: Missing detailed rationale/evidence in exposure table (only in Details column)

5. **Was Scrappy involved?** ✅
   - IntelligenceBadge shows scrappy_at_entry status
   - Shows stale/conflict flags

6. **Was AI Referee involved?** ✅
   - IntelligenceBadge shows ai_referee_at_entry status
   - Shows ran/not_run

7. **What size was approved and why?** ⚠️
   - SizingSummary component shows sizing_at_entry
   - **GAP**: Compact view may hide details; full sizing rationale not always visible

8. **What is the stop?** ✅
   - Stop price shown in both tables

9. **What is the target?** ✅
   - Target price shown in both tables

10. **What is the force-flat time?** ✅
    - Force-flat time shown in Portfolio table
    - **GAP**: Not shown in Command Center exposure table

11. **What protection mode is active?** ✅
    - ProtectionModeBadge shows mode and active status

12. **Has an exit order already been submitted?** ⚠️
    - exit_order_id shown in Details column
    - **GAP**: Not prominently visible; requires clicking Details

13. **Is the trade managed, pending, exited, blocked, unmanaged, or orphaned?** ✅
    - ManagedStatusBadge shows status clearly
    - LifecycleStatusBadge shows lifecycle state

14. **Did it come from a fresh dynamic universe or static fallback?** ✅
    - static_fallback_at_entry flag shown
    - universe_source shown
    - SafetyStrip shows gateway/worker source

15. **Is paper trading armed right now, and why?** ✅
    - SafetyStrip shows armed/disarmed
    - Shows armed_reason
    - System Health shows prerequisites

16. **If something is unsafe, what exactly is blocked?** ✅
    - SafetyStrip shows blockers
    - System Health shows detailed prerequisites
    - Warnings shown for orphaned/unmanaged positions

## Page-by-Page Audit

### Command Center (`/command`)

**Endpoints Used:**
- `/v1/health`
- `/v1/metrics/summary`
- `/v1/strategies`
- `/v1/opportunities/now`
- `/v1/scanner/summary`
- `/v1/scanner/runs`
- `/v1/opportunities/summary`
- `/v1/opportunities/session`
- `/v1/scrappy/status`
- `/v1/config`
- `/v1/health/detail`
- `/v1/paper/test/proof`
- `/v1/paper/exposure` ✅
- `/v1/account` ✅
- `/v1/positions` ✅
- `/v1/orders?status=closed` ✅
- `/v1/runtime/status` (via SafetyStrip) ✅

**What's Good:**
- SafetyStrip at top shows critical safety status
- Live Paper Exposure section prominently displayed
- Real Paper Trading section separated from Shadow
- Shows all lifecycle fields

**What's Missing:**
- Force-flat time not in exposure table
- Exit order ID not prominently visible
- Missing "why we bought" summary (reason_codes)
- Orphaned count not in SafetyStrip

**What's Misleading:**
- Shadow metrics still prominent (though separated)
- No clear visual hierarchy emphasizing real trades

### Portfolio (`/portfolio`)

**Endpoints Used:**
- `/v1/shadow/trades`
- `/v1/metrics/summary`
- `/v1/account` ✅
- `/v1/positions` ✅
- `/v1/clock`
- `/v1/portfolio/history`
- `/v1/paper/exposure` ✅
- `/v1/portfolio/compare-books` ✅
- `/v1/system/reconciliation` ✅

**What's Good:**
- Paper Exposure & Lifecycle table comprehensive
- Shows P&L data (unrealized_pl, unrealized_plpc, market_value)
- Shows all lifecycle fields
- Compare books and reconciliation shown

**What's Missing:**
- Exit order ID visibility could be better
- Missing "why we bought" summary in table
- Force-flat time shown but could be more prominent

**What's Misleading:**
- Shadow Book section at bottom might be confused with real trades
- Paper account section shows broker data but lifecycle is separate section

### Live Signal Feed (`/signals`)

**Endpoints Used:**
- `/v1/signals?limit=50`

**What's Good:**
- Shows recent signals
- Links to signal detail

**What's Missing:**
- No indication if signal generated a paper order
- No lifecycle status
- No visual distinction for open-paper signals
- Missing intelligence participation indicators

**What's Misleading:**
- Signals appear equal; no way to see which ones resulted in trades

### Signal Detail (`/signals/:uuid`)

**Endpoints Used:**
- `/v1/signals/{uuid}`

**What's Good:**
- Shows signal details
- Shows intelligence snapshot
- Shows AI referee assessment
- Shows paper_order_id if present

**What's Missing:**
- No lifecycle status link
- No exit plan summary (stop/target/protection)
- No link to paper exposure if position is open
- Missing "why we bought" summary (reason_codes could be more prominent)

**What's Misleading:**
- Paper order link exists but lifecycle status not shown

### Intelligence Center (`/intelligence`)

**Endpoints Used:**
- `/v1/intelligence/recent`
- `/v1/intelligence/summary`
- `/v1/scrappy/status`
- `/v1/scrappy/auto-runs`
- `/v1/runtime/status`

**What's Good:**
- Shows recent snapshots
- Shows Scrappy status
- Shows automation status

**What's Missing:**
- No indication of which symbols have open paper exposure
- No link to positions for symbols with exposure
- Missing live trading context

**What's Misleading:**
- Manual run button might suggest manual mode is primary

### AI Referee (`/ai-referee`)

**Endpoints Used:**
- `/v1/ai-referee/recent?limit=20`

**What's Good:**
- Shows recent assessments
- Shows decision and rationale

**What's Missing:**
- No indication of which symbols have open paper exposure
- No link to positions
- Missing live trading context

### System Health (`/system-health`)

**Endpoints Used:**
- `/v1/health/detail`
- `/v1/runtime/status` ✅
- `/v1/paper/arming-prerequisites` ✅
- `/v1/system/reconciliation` ✅

**What's Good:**
- Shows paper trading safety posture
- Shows prerequisites and blockers
- Shows reconciliation status
- Shows symbol source and fallback

**What's Missing:**
- Orphaned exposure count not shown
- Lifecycle warnings not shown
- Broker reachability detail could be clearer

### Orders (`/orders`)

**Endpoints Used:**
- `/v1/orders?status=...&limit=100`

**What's Good:**
- Shows all orders
- Shows P&L calculations
- Shows order details

**What's Missing:**
- No link to lifecycle if order is part of lifecycle
- No link to signal if order came from signal
- Missing source (strategy_paper/operator_test) prominently

### Other Pages

- **Shadow Trades**: Clearly labeled as simulation ✅
- **Performance**: Shows shadow metrics, clearly labeled ✅
- **Activities**: Shows account activities
- **Calendar**: Market calendar
- **Assets**: Asset master
- **Settings**: Configuration
- **Strategy Lab**: Strategy development
- **History**: Historical data
- **Experiments**: Experimental features

## Critical Gaps Identified

1. **Exit Order ID Visibility**: Shown in Details column but not prominently
2. **Force-Flat Time**: Missing from Command Center exposure table
3. **"Why We Bought" Summary**: Reason codes not prominently shown in exposure tables
4. **Open-Paper Signal Indication**: Signals that resulted in open positions not visually distinct
5. **Orphaned Count in SafetyStrip**: Not shown in top safety strip
6. **Live Trading Context in Intelligence Pages**: No indication of which symbols have open exposure
7. **Lifecycle Links**: Signal detail doesn't link to lifecycle/position

## Duplications

- Paper Exposure shown in both Command Center and Portfolio (acceptable - different contexts)
- Shadow metrics shown in multiple places (acceptable - clearly labeled)

## Misleading Omissions

- Signal feed doesn't show which signals resulted in trades
- Intelligence pages don't show live trading context
- Exit order status not prominently visible

## Recommendations

1. Add exit_order_id column to Command Center exposure table
2. Add force-flat time to Command Center exposure table
3. Add reason_codes summary to exposure tables
4. Make open-paper signals visually distinct in signal feed
5. Add orphaned count to SafetyStrip
6. Add live trading context to Intelligence Center and AI Referee pages
7. Add lifecycle links to Signal Detail page
8. Enhance exit plan visibility in Signal Detail
