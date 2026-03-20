# UI Fixes Screenshots - March 20, 2026

This folder contains full-page screenshots of all StockBot UI pages captured after the comprehensive UI truth and operator-visibility enhancements.

## Screenshots Included

1. **CommandCenter.png** - Command Center with Live Paper Exposure, SafetyStrip enhancements, and real paper trading metrics
2. **LiveSignalFeed.png** - Signal feed with status indicators showing open positions
3. **IntelligenceCenter.png** - Intelligence Center with live position context for symbols
4. **AiReferee.png** - AI Referee page with live position context
5. **Portfolio.png** - Portfolio page with comprehensive lifecycle view and P&L data
6. **Orders.png** - Orders page with source column and signal links
7. **SystemHealth.png** - System Health with paper exposure status section
8. **ShadowTrades.png** - Shadow trades page
9. **Performance.png** - Performance metrics page
10. **Experiments.png** - Experiments page
11. **StrategyLab.png** - Strategy Lab page
12. **History.png** - History page
13. **Settings.png** - Settings page
14. **Activities.png** - Activities page
15. **Calendar.png** - Calendar page
16. **Assets.png** - Assets page

## Key Enhancements Captured

### Command Center
- Live Paper Exposure table with Force-Flat and Exit Order columns
- SafetyStrip showing open positions count and orphaned count
- Real Paper Trading section separated from Shadow Trading

### Signal Detail (not in screenshots, but accessible)
- Lifecycle information display
- Exit Plan & Protection section
- Links to entry/exit orders

### Signal Feed
- Status column showing "Open Position" or "Order Filled" badges
- Visual highlighting of signals with open positions

### Intelligence Pages
- Live Position column showing position details
- Visual highlighting of symbols with open exposure
- Links to Portfolio for positions

### Portfolio
- Comprehensive lifecycle view with all exit plan details
- P&L data (unrealized_pl, unrealized_plpc, market_value)
- Compare books and reconciliation status

### Orders
- Source column showing strategy_paper/operator_test/legacy_unknown
- Signal links when available

### System Health
- Paper Exposure Status section
- Orphaned/unmanaged count warnings
- Broker reachability status

## Capture Details

- **Date**: March 20, 2026
- **UI URL**: http://localhost:5173 (or configured UI_URL)
- **Viewport**: 1920x1080
- **Format**: Full-page PNG screenshots
- **Tool**: Puppeteer

## Related Documentation

- `docs/UI_TRUTH_AUDIT_2026-03-20.md` - Comprehensive UI audit
- `docs/UI_TRUTH_IMPLEMENTATION_SUMMARY.md` - Implementation summary
