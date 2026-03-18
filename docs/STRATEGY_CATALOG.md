# Strategy Catalog

## INTRA_EVENT_MOMO / 0.1.0

Status: active-development  
Mode: shadow-only  
Broker/Data: Alpaca paper trading integration present, but scheduled strategy runs do not place orders  
Feed: Alpaca stocks + news, `feed=iex`  
Session: regular US market hours only  
Entry window: 09:35–11:30 America/New_York  
Universe: configured by `STOCKBOT_UNIVERSE`

Thesis:
Trade liquid intraday continuation only when price, volume, spread, opening-range structure, and fresh news catalyst agree.

Deterministic inputs:
- latest quote / trade / minute bar
- prior close
- session VWAP
- opening range high/low from first 5 minutes
- relative volume
- Alpaca news headline/summary keyword tagging

Signal rules:
- Long only when breakout above opening-range high, above VWAP, with positive news tag.
- Short only when breakdown below opening-range low, below VWAP, with negative news tag.
- One trade max per symbol per day.
- No pyramiding.
- Force flat by 15:45 ET.
- Scrappy gating (when SCRAPPY_MODE != off): long allowed only when catalyst_direction is positive or neutral; short only when negative or neutral; reject on conflict, stale, or (if required) missing snapshot. Signal persists intelligence_snapshot_id when Scrappy snapshot was used.

Shadow fills:
- ideal mode
- realistic mode using bid/ask + slippage + fees

Audit requirements:
Persist strategy_id, strategy_version, reason_codes, feature_snapshot, quote_snapshot, feed, signal_ts, entry_ts, exit_ts, fill assumptions, and PnL.
