# Current-State Strategy Audit

## Strategy: INTRA_EVENT_MOMO / 0.1.0

### Entry Window
- **Start**: 09:35 ET
- **End**: 11:30 ET
- **Force Flat**: 15:45 ET
- **Current Session**: Regular hours (outside entry window at time of audit)

### Price Range Constraints
- **MIN_PRICE**: $5.00
- **MAX_PRICE**: $500.00
- **Current rejection count**: 657 rejections for `price_out_of_range`

### Other Filter Constraints
- **MIN_DOLLAR_VOLUME_1M**: $1,000,000 (rejection count: 3,496)
- **MAX_SPREAD_BPS**: 20 bps
- **MIN_ABS_GAP_PCT**: 1.0%
- **MIN_REL_VOLUME_5M**: 1.5x
- **News requirement**: Must have directional news (long/short), rejects neutral

### Current Rejection Landscape (from runtime)
1. **outside_entry_window**: 5,744 rejections (dominant - platform is outside 09:35-11:30 window)
2. **dollar_volume_below_min**: 3,496 rejections
3. **price_out_of_range**: 657 rejections

### Strategy Logic
- **Long entry**: News side = "long", close > opening_range_high, price > VWAP
- **Short entry**: News side = "short", close < opening_range_low, price < VWAP
- **Stop/Target**: Long stop = OR low, target = entry + 2R*(entry - OR low). Short stop = OR high, target = entry - 2R*(OR high - entry)

### Available Feature Data (from FeatureSet)
- Opening range (high/low from first 5 minutes)
- Session VWAP
- Gap % from prev close
- Spread (bps)
- Dollar volume (1m)
- Relative volume (5m)
- Latest bid/ask/last
- News side classification (long/short/neutral)
- News keyword hits

### Database Schema
- All tables already have `strategy_id` and `strategy_version` fields:
  - `signals` table
  - `fills` table
  - `shadow_trades` table
  - `paper_lifecycles` table

### UI Pages (strategy-aware)
- **LiveSignalFeed**: Shows signals but not segmented by strategy
- **SignalDetail**: Shows strategy_id and strategy_version
- **Performance**: Shows aggregate metrics, not strategy-segmented
- **CommandCenter**: Shows rejection summary but not strategy-specific
- **SystemHealth**: Shows runtime status but not strategy routing

### Scanner/Opportunities
- Currently surfaces 25 opportunities
- Price ranges: $8.71 - $24.94 observed
- Gap ranges: 0.56% - 1.63% observed
- **Issue**: Scanner shows symbols that worker rejects for time window or price range mismatch

### Why Platform Not Trading
1. **Primary**: Outside entry window (09:35-11:30) - 5,744 rejections
2. **Secondary**: Dollar volume below minimum - 3,496 rejections
3. **Tertiary**: Price out of range - 657 rejections

### Available Data for Later-Session Strategy
- All FeatureSet data available throughout session
- Opening range persists (can be used for later-session reference)
- VWAP continues updating
- News classification available
- Volume/liquidity metrics available
- Scrappy intelligence available
- No new architecture needed - can build continuation strategy using existing pipeline

## Strategy: SWING_EVENT_CONTINUATION / 0.1.0

### Entry Window
- **Start**: 13:00 ET
- **End**: 15:30 ET
- **Force Flat**: None (overnight carry expected)
- **Holding Period**: 1-5 trading days

### Differences from Intraday Strategies
- No intraday force-flat; positions carry overnight
- `holding_period_type: "swing"` — distinct lifecycle tracking
- `max_hold_days: 5` — forced exit after 5 trading days
- Separate risk controls with lower defaults
- Uses daily bar data (prior day OHLC, 2-day low) not just intraday features
- Catalyst requirement: Scrappy positive strength ≥ 3 (higher threshold)

### Filter Thresholds
- **MIN_PRICE**: $5.00
- **MAX_PRICE**: $500.00
- **MIN_AVG_DAILY_DOLLAR_VOLUME**: $5,000,000
- **MAX_SPREAD_BPS**: 30 bps
- **MAX_GAP_FROM_PREV_CLOSE_PCT**: 10.0%
- **MAX_EXTENSION_FROM_REFERENCE_PCT**: 15.0%
- **MIN_REL_VOLUME_5M**: 1.0x
- **MIN_CATALYST_STRENGTH**: 3

### Daily Structure Requirements (must meet at least one)
1. **Strong close**: Current price in top 25% of today's range
2. **Reclaim**: Price at or above prior day high (within 0.5% tolerance)
3. **VWAP hold**: Price above VWAP and above prior close

### Stop / Target
- Long stop: Prior day low × 0.995 (or 2-day low × 0.995, whichever is tighter)
- Target: Entry + 2R (R = entry - stop)
- Fallback if no prior data: 3% stop from entry

### Lifecycle Fields (added to PaperLifecycle)
- `holding_period_type` — "intraday" or "swing"
- `max_hold_days` — max trading days before forced exit
- `entry_date` — date of entry (for day counting)
- `scheduled_exit_date` — max exit date
- `days_held` — current days held
- `overnight_carry` — whether position carried overnight
- `overnight_carry_count` — number of overnight carries

### Rollout
- **Shadow-only** by default
- Paper requires `STRATEGY_SWING_EVENT_CONTINUATION_PAPER_ENABLED=true`
- Default paper: disabled
