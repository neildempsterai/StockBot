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
  strategies?: Array<{
    strategy_id: string;
    strategy_version: string;
    mode?: string;
    entry_window_et?: string;
    force_flat_et?: string | null;
    enabled?: boolean;
    paper_enabled?: boolean;
    holding_period_type?: 'intraday' | 'swing';
    max_hold_days?: number;
    overnight_carry?: boolean;
    note?: string;
  }>;
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
    strategy_id?: string;
    strategy_version?: string;
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
    coverage_status?: 'fresh_research' | 'carried_forward_research' | 'low_evidence' | 'no_research';
    coverage_reason?: string;
    coverage_latest_evidence_ts?: string;
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

export interface StrategyEligibility {
  eligible?: boolean;
  reason?: string | null;
  entry_window?: string;
  paper_enabled?: boolean;
  enabled?: boolean;
  holding_period_type?: 'intraday' | 'swing';
  max_hold_days?: number;
  overnight_carry?: boolean;
  force_flat_et?: string | null;
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
    strategy_eligibility?: Record<string, StrategyEligibility>;
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
  last_attempt_at?: string;
  last_run_id?: string;
  last_outcome?: string;
  last_failure_reason?: string;
  last_notes_created?: number;
  watchlist_size?: number;
  last_snapshots_updated?: number;
  last_symbols_requested?: string[];
  last_symbols_researched?: string[];
  coverage_counts?: {
    fresh_research?: number;
    carried_forward_research?: number;
    low_evidence?: number;
    no_research?: number;
  };
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

export interface PaperExposureResponse {
  positions?: PaperExposurePosition[];
  count?: number;
}

export interface PaperExposurePosition {
  symbol: string;
  side: string;
  qty: number;
  entry_ts?: string;
  source?: string;
  order_origin?: string;
  operator_intent?: string;
  strategy_id?: string;
  strategy_version?: string;
  signal_uuid?: string;
  entry_order_id?: string;
  exit_order_id?: string;
  scrappy_at_entry?: string;
  scrappy_detail?: {
    snapshot_id?: number;
    freshness_minutes?: number;
    catalyst_direction?: string;
    evidence_count?: number;
    headline_count?: number;
    stale_flag?: boolean;
    conflict_flag?: boolean;
  };
  ai_referee_at_entry?: string;
  ai_referee_detail?: {
    ran?: boolean;
    model_name?: string;
    referee_version?: string;
    decision_class?: string;
    setup_quality_score?: number;
    contradiction_flag?: boolean;
    stale_flag?: boolean;
    evidence_sufficiency?: string;
    plain_english_rationale?: string;
  };
  sizing_at_entry?: {
    equity?: number;
    buying_power?: number;
    stop_distance?: number;
    risk_per_trade_pct?: number;
    max_position_pct?: number;
    max_gross_exposure_pct?: number;
    max_symbol_exposure_pct?: number;
    max_concurrent_positions?: number;
    qty_proposed?: number;
    qty_approved?: number;
    notional_approved?: number;
    rejection_reason?: string;
  };
  unrealized_pl?: number;
  unrealized_plpc?: number;
  market_value?: number;
  current_price?: number;
  avg_entry_price?: number;
  exit_plan_status?: string;
  stop_price?: number;
  target_price?: number;
  force_flat_time?: string;
  protection_mode?: string;
  protection_active?: boolean;
  broker_protection?: string;
  managed_status?: string;
  orphaned?: boolean;
  universe_source?: string;
  static_fallback_at_entry?: boolean;
  lifecycle_status?: string;
  exit_reason?: string;
  exit_ts?: string;
  last_error?: string;
  holding_period_type?: 'intraday' | 'swing';
  max_hold_days?: number;
  entry_date?: string;
  scheduled_exit_date?: string;
  days_held?: number;
  overnight_carry?: boolean;
  overnight_carry_count?: number;
  quality_score?: number;
  trailing_stop_phase?: string;
  original_stop_price?: number;
  partial_exits_done?: string[];
  [key: string]: unknown;
}

export interface WorkerTelemetryResponse {
  positions?: Record<string, {
    quality_score?: number;
    trailing_stop_phase?: string;
    current_stop?: string;
    original_stop?: string;
    high_water_mark?: string;
    partial_exits_done?: string[];
  }>;
  regime?: {
    label?: string;
    confidence?: number;
    spy_above_vwap?: boolean;
  };
  circuit_breaker?: {
    daily_pnl?: string;
    trades_today?: number;
    wins?: number;
    losses?: number;
    breaker_active?: boolean;
    total_positions?: number;
  };
}

export interface RuntimeStatusResponse {
  strategy?: {
    id?: string;
    version?: string;
    execution_mode?: string;
    paper_execution_enabled?: boolean;
    active_strategies?: string[];
  };
  market_data?: {
    feed?: string;
    extended_hours_enabled?: boolean;
  };
  risk_management?: {
    max_daily_loss_pct?: number;
    max_portfolio_heat_pct?: number;
    max_total_concurrent_positions?: number;
    trailing_stop_enabled?: boolean;
    partial_exit_enabled?: boolean;
    min_entry_quality_score?: number;
    short_max_concurrent?: number;
    max_short_gross_exposure_pct?: number;
  };
  paper_execution?: {
    supported_end_to_end?: boolean;
    note?: string;
  };
  operator_paper_test?: {
    enabled?: boolean;
    max_qty?: number;
    max_notional?: number;
  };
  scrappy?: {
    mode?: string;
    paper_required?: boolean;
  };
  ai_referee?: {
    enabled?: boolean;
    mode?: string;
    paper_required?: boolean;
  };
  symbol_source?: {
    gateway?: {
      active_source?: string;
      active_source_label?: string;
      symbol_count?: number;
      refresh_ts?: string;
      fallback_reason?: string;
    };
    worker?: {
      active_source?: string;
      active_source_label?: string;
      symbol_count?: number;
      refresh_ts?: string;
      fallback_reason?: string;
    };
    dynamic_universe_last_updated_at?: string;
    dynamic_universe_stale_after_sec?: number;
    error?: string;
  };
  paper_trading_armed?: boolean;
  paper_armed_reason?: string;
  [key: string]: unknown;
}

export interface PaperArmingPrerequisitesResponse {
  satisfied?: boolean;
  blockers?: string[];
  checks?: Record<string, { ok?: boolean; detail?: string }>;
}

export interface CompareBooksResponse {
  shadow?: {
    trade_count?: number;
    total_net_pnl?: number;
  };
  paper?: {
    fill_count?: number;
    total_net_pnl?: number | null;
  };
  note?: string;
}

export interface ReconciliationResponse {
  status?: string;
  run_at?: string;
  orders_matched?: number;
  orders_mismatch?: number;
  positions_matched?: number;
  positions_mismatch?: number;
  details?: unknown;
}
