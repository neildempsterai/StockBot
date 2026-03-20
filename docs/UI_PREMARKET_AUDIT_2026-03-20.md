# UI Premarket Activation & Truth Audit
**Date:** 2026-03-20  
**Purpose:** Audit current UX to identify gaps in premarket preparation visibility and operator truth

## Current Navigation Labels & Purpose

### Trading Section
- **Command Center** (`/command`): Main operator console
  - Shows: Paper exposure summary, system status, top opportunities
  - Missing: Premarket prep status, focus board, readiness indicators
  - Endpoints: `/v1/health`, `/v1/strategies`, `/v1/opportunities/now`, `/v1/paper/exposure`

- **Live Signals** (`/signals`): Signal feed
  - Shows: Recent signals
  - Purpose: Clear

- **Shadow Trades** (`/shadow-trades`): Shadow trade ledger
  - Purpose: Clear

- **Portfolio** (`/portfolio`): Account and positions
  - Shows: Account summary, equity curve, paper exposure table, compare books, reconciliation, shadow book
  - Missing: Full lifecycle detail prominence, premarket context
  - Endpoints: `/v1/account`, `/v1/positions`, `/v1/paper/exposure`, `/v1/portfolio/compare-books`

### Paper Account Section
- **Orders** (`/orders`): Paper orders
  - Purpose: Clear

- **Activities** (`/activities`): Account activities
  - Purpose: Clear

- **Calendar** (`/calendar`): Market calendar
  - Purpose: Clear

- **Assets** (`/assets`): Tradable assets
  - Purpose: Clear

### Analysis Section
- **Intelligence** (`/intelligence`): **VAGUE LABEL**
  - Current: Shows Scrappy automation status, AI Referee status, recent snapshots
  - Missing: Focus board, premarket readiness, why symbols are on focus, historical context
  - Endpoints: `/v1/intelligence/recent`, `/v1/intelligence/summary`, `/v1/scrappy/status`, `/v1/runtime/status`
  - Should be: "Premarket Prep" or "Focus Board"

- **AI Referee** (`/ai-referee`): **VAGUE LABEL**
  - Current: Shows recent assessments table
  - Missing: Mode summary, premarket candidates needing assessment, what it does
  - Endpoints: `/v1/ai-referee/recent`
  - Should be: "AI Assessments" or "Candidate Assessment"

- **Performance** (`/performance`): **VAGUE LABEL**
  - Current: Shows shadow and paper P&L metrics
  - Purpose: Could be clearer as "Outcomes" or "Trading Results"
  - Endpoints: `/v1/metrics/summary`, `/v1/portfolio/compare-books`, `/v1/paper/exposure`

- **Experiments** (`/experiments`): **VAGUE LABEL**
  - Current: Shows scrappy mode comparison
  - Purpose: Unclear - could be "Strategy Comparisons" or "Mode Analysis"
  - Endpoints: `/v1/metrics/compare-scrappy-modes`

### System Section
- **System Health** (`/system-health`): System status
  - Purpose: Clear

- **Strategy Lab** (`/strategy-lab`): Strategy testing
  - Purpose: Clear

- **History** (`/history`): Historical data
  - Purpose: Clear

- **Settings** (`/settings`): Configuration
  - Purpose: Clear

## Critical Operator Truths Currently Hidden

### Premarket Preparation
1. **Focus Board**: No clear view of which symbols are being researched and why
2. **Readiness Status**: No clear indicator of platform readiness for paper trading
3. **Intelligence Coverage**: No clear view of which focus symbols have fresh/stale/missing intelligence
4. **AI Assessment Coverage**: No clear view of which candidates have been assessed
5. **Historical Context**: No simple historical context (gap, recent range, volatility proxy) for focus symbols
6. **Blockers**: No clear list of what's blocking safe paper trading

### Paper Trading Lifecycle
1. **Command Center**: Shows summary but not full lifecycle detail (stop/target/protection/source)
2. **Portfolio**: Has lifecycle data but not prominently displayed
3. **Source Clarity**: Not always clear if position is strategy_paper vs operator_test
4. **Protection Status**: Not always clear if protection is active

### Intelligence & Assessment
1. **Intelligence Center**: Doesn't explain why symbols are on focus (scanner rank, opportunity source)
2. **AI Referee**: Doesn't show mode summary or premarket candidates needing assessment
3. **Coverage Gaps**: Doesn't clearly show which symbols need research

## Available Backend Endpoints

### Premarket/Scanner
- `/v1/scanner/summary` - Scanner status
- `/v1/scanner/runs` - Scanner run history
- `/v1/opportunities/now` - Current opportunities
- `/v1/opportunities/summary` - Opportunity summary
- `/v1/opportunities/session` - Current session info

### Intelligence
- `/v1/intelligence/recent` - Recent snapshots
- `/v1/intelligence/summary` - Intelligence summary
- `/v1/scrappy/status` - Scrappy automation status
- `/v1/scrappy/auto-runs` - Auto-run history

### AI Referee
- `/v1/ai-referee/recent` - Recent assessments
- `/v1/runtime/status` - Runtime status (includes AI Referee mode)

### Paper Trading
- `/v1/paper/exposure` - Full lifecycle detail
- `/v1/paper/arming-prerequisites` - Arming prerequisites
- `/v1/runtime/status` - Runtime status

## Empty/Blank States

### Intelligence Center
- Currently: "No snapshots yet" - too vague
- Should explain: Why no snapshots (scrappy disabled, no symbols, backend down)

### AI Referee
- Currently: "No referee assessments yet" - too vague
- Should explain: Why none (disabled, not run, no candidates)

### Command Center Opportunities
- Currently: Has good empty states with reasons
- Good: Shows session blocking, scanner status

## Recommendations

1. **Rename Pages**: Intelligence → "Premarket Prep", AI Referee → "AI Assessments", Performance → "Outcomes", Experiments → "Mode Analysis"
2. **Add Focus Board**: Show scanner-ranked symbols with intelligence coverage status
3. **Add Readiness Panel**: Show premarket prep status, blockers, coverage gaps
4. **Enhance Command Center**: Add premarket prep summary, full lifecycle detail for positions
5. **Enhance Portfolio**: Make lifecycle detail more prominent
6. **Add Historical Context**: Simple gap/range/volatility for focus symbols
7. **Improve Empty States**: Explain why data is missing
