/**
 * API response types for StockBot backend. Match backend response shapes.
 */

export interface HealthResponse {
  status?: string;
}

export interface ConfigResponse {
  FEED?: string;
  EXECUTION_MODE?: string;
  PAPER_EXECUTION_ENABLED?: boolean;
  PAPER_TRADING_ARMED?: boolean;
  SCRAPPY_MODE?: string;
  AI_REFEREE_ENABLED?: boolean;
  AI_REFEREE_MODE?: string;
  [key: string]: unknown;
}

export interface StrategiesResponse {
  strategies?: Array<{ strategy_id: string; strategy_version: string; mode?: string }>;
}

export interface HealthDetailResponse {
  api?: string;
  database?: string;
  redis?: string;
  worker?: string;
  alpaca_gateway?: string;
  gateway_symbol_count?: number;
  gateway_symbol_refresh_ts?: string;
  gateway_symbol_source?: string;
  gateway_fallback_reason?: string;
  dynamic_symbols_available?: boolean;
  worker_universe_count?: number;
  worker_universe_source?: string;
  worker_universe_refresh_ts?: string;
  worker_fallback_reason?: string;
  [key: string]: unknown;
}

export interface MetricsSummaryResponse {
  signals_total?: number;
  shadow_trades_total?: number;
  total_net_pnl_shadow?: number;
  signals_with_scrappy_snapshot?: number;
  signals_without_scrappy_snapshot?: number;
  scrappy_gate_rejections?: Record<string, number>;
  [key: string]: unknown;
}

export interface ShadowTradesResponse {
  trades: Array<{
    signal_uuid: string;
    execution_mode?: string;
    entry_ts?: string;
    exit_ts?: string;
    entry_price?: number;
    exit_price?: number;
    qty?: number;
    gross_pnl?: number;
    net_pnl?: number;
    exit_reason?: string;
    scrappy_mode?: string;
  }>;
  count?: number;
}

export interface PaperAccountResponse {
  equity?: string | number;
  cash?: string | number;
  buying_power?: string | number;
  [key: string]: unknown;
}

export interface PaperPositionsResponse {
  positions?: Array<{
    symbol: string;
    qty?: number | string;
    market_value?: string | number;
    unrealized_pl?: string | number;
    unrealized_plpc?: string | number;
    [key: string]: unknown;
  }>;
}

export interface MarketClockResponse {
  is_open?: boolean;
  next_open?: string;
  next_close?: string;
  [key: string]: unknown;
}

export interface PortfolioHistoryResponse {
  timestamp?: number[];
  equity?: number[];
  profit_loss?: number[];
  [key: string]: unknown;
}

export interface IntelligenceRecentResponse {
  snapshots?: Array<{
    id: number;
    symbol: string;
    catalyst_strength?: string;
    catalyst_direction?: string;
    sentiment_label?: string;
    evidence_count?: number;
    source_count?: number;
    stale_flag?: boolean;
    conflict_flag?: boolean;
    snapshot_ts?: string;
    [key: string]: unknown;
  }>;
}

export interface IntelligenceSummaryResponse {
  snapshots_total?: number;
  symbols_with_snapshot?: number;
  [key: string]: unknown;
}

export interface PaperOrdersResponse {
  orders?: PaperOrder[];
  count?: number;
}

export interface PaperOrder {
  id?: string;
  symbol?: string;
  side?: string;
  qty?: number | string;
  filled_qty?: number | string;
  order_type?: string;
  type?: string;
  status?: string;
  filled_avg_price?: string | number;
  created_at?: string;
  [key: string]: unknown;
}

export interface AccountActivitiesResponse {
  activities?: AccountActivity[];
  next_page_token?: string;
  [key: string]: unknown;
}

export interface AccountActivity {
  id?: string;
  activity_type?: string;
  transaction_time?: string;
  date?: string;
  symbol?: string;
  side?: string;
  qty?: string | number;
  price?: string | number;
  net_amount?: string | number;
  [key: string]: unknown;
}

export interface PaperTestProofResponse {
  intents?: string[];
  proof?: Record<string, { symbol?: string; side?: string; qty?: number; status?: string; order_id?: string }>;
}

export interface OpportunitiesNowResponse {
  opportunities?: Array<{
    symbol: string;
    rank?: number;
    total_score?: number;
    semantic_score?: number;
    candidate_source?: string;
    price?: number;
    gap_pct?: number;
    spread_bps?: number;
    scrappy_present?: boolean;
    scrappy_catalyst_direction?: string;
    scrappy_stale_flag?: boolean;
    scrappy_conflict_flag?: boolean;
    inclusion_reasons?: string[];
    reason_codes?: string[];
    [key: string]: unknown;
  }>;
  updated_at?: string;
  run_id?: string;
}

export interface OpportunitiesSummaryResponse {
  source?: string;
  reason?: string;
  reason_if_blocked?: string;
  top_count?: number;
  top_scrappy_count?: number;
  scanner_session_allowed?: boolean;
  [key: string]: unknown;
}

export interface OpportunitiesSessionResponse {
  session?: string;
  [key: string]: unknown;
}

export interface ScannerSummaryResponse {
  last_run_ts?: string;
  last_run_status?: string;
  top_count?: number;
  rejection_reasons?: Record<string, number>;
  [key: string]: unknown;
}

export interface ScannerRunsResponse {
  runs?: Array<{
    run_id: string;
    run_ts?: string;
    status?: string;
    universe_size?: number;
    candidates_scored?: number;
    top_candidates_count?: number;
    market_session?: string;
    [key: string]: unknown;
  }>;
}

export interface ScrappyStatusResponse {
  scrappy_auto_enabled?: boolean;
  last_run_at?: string;
  last_notes_created?: number;
  watchlist_size?: number;
  last_snapshots_updated?: number;
  [key: string]: unknown;
}

export interface ScrappyAutoRunsResponse {
  runs?: Array<{ run_id?: string; run_ts?: string; [key: string]: unknown }>;
}

export interface BacktestStatusResponse {
  available?: boolean;
  message?: string;
  sessions?: Array<{ id: string; date_utc?: string; description?: string }>;
}

export interface ScannerRunHistoricalResponse {
  run_ids?: string[];
  [key: string]: unknown;
}
