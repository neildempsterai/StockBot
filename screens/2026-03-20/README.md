# StockBot UI Screenshots - March 20, 2026

Full UI review screenshots captured for all pages in the StockBot application.

## Screenshots Captured

1. **CommandCenter.png** - `/command` - Main command center with real paper trading and shadow metrics
2. **LiveSignalFeed.png** - `/signals` - Live signal feed showing trading signals
3. **IntelligenceCenter.png** - `/intelligence` - Intelligence center with Scrappy snapshots
4. **AiReferee.png** - `/ai-referee` - AI Referee assessments and decisions
5. **Performance.png** - `/performance` - Performance metrics and shadow P&L
6. **Experiments.png** - `/experiments` - Experimental features and tests
7. **Portfolio.png** - `/portfolio` - Portfolio view with paper account, positions, and lifecycle
8. **ShadowTrades.png** - `/shadow-trades` - Shadow trading ledger (simulation only)
9. **SystemHealth.png** - `/system-health` - System health and status monitoring
10. **StrategyLab.png** - `/strategy-lab` - Strategy development and testing
11. **History.png** - `/history` - Historical data and backtests
12. **Settings.png** - `/settings` - Application settings and configuration
13. **Orders.png** - `/orders` - Paper orders with P&L calculations
14. **Activities.png** - `/activities` - Account activities and transactions
15. **Calendar.png** - `/calendar` - Market calendar and events
16. **Assets.png** - `/assets` - Available assets on Alpaca

## Key UI Changes Made Today

### Command Center
- **Separated Real Paper Trading from Shadow Trading**
  - Real Paper Trading section shows actual broker data (Equity, Cash, Positions, Orders)
  - Shadow Trading section clearly labeled as simulation
  - Warning note explaining the difference

### Portfolio Page
- **Fixed layout**: Paper account cards now display in single row (5 cards)
- **Added P&L columns**: Entry Price, Current Price, Market Value, Unrealized P&L, P&L %

### Orders Page
- **Added P&L columns**: Trade Value, Realized P&L, P&L %
- **Fixed P&L logic**: Only SELL orders show realized P&L (matching with BUY orders using FIFO)

### Paper Exposure
- **Added P&L data**: All position data now includes unrealized_pl, unrealized_plpc, market_value, current_price, avg_entry_price

## Notes for Review

- All screenshots are full-page captures (1920x1080 viewport, full page height)
- Screenshots were taken with 2-3 second delays to allow content to load
- Each page was scrolled to bottom and back to top to trigger lazy-loaded content
- UI is running on `http://localhost:8080`

## Next Steps

Review each screenshot to identify:
- UI/UX issues
- Missing information
- Confusing labels or sections
- Data display problems
- Layout issues
- Shadow vs Paper confusion (should be resolved)
