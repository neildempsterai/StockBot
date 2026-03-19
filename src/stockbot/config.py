"""App config via env. v0.1: regular hours only; no extended/overnight."""
from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Alpaca (required for gateways/worker; API can run without for read-only UI)
    alpaca_api_key_id: str = Field(default="", alias="ALPACA_API_KEY_ID")
    alpaca_api_secret_key: str = Field(default="", alias="ALPACA_API_SECRET_KEY")
    alpaca_base_url: str = Field(
        default="https://paper-api.alpaca.markets",
        alias="ALPACA_BASE_URL",
    )
    alpaca_data_base_url: str = Field(
        default="https://data.alpaca.markets",
        alias="ALPACA_DATA_BASE_URL",
    )
    alpaca_data_ws_url: str = Field(
        default="wss://stream.data.alpaca.markets/v2/iex",
        alias="ALPACA_DATA_WS_URL",
    )
    alpaca_news_ws_url: str = Field(
        default="wss://stream.data.alpaca.markets/v1beta1/news",
        alias="ALPACA_NEWS_WS_URL",
    )
    alpaca_trading_ws_url: str = Field(
        default="wss://paper-api.alpaca.markets/stream",
        alias="ALPACA_TRADING_WS_URL",
    )

    # Feed: IEX only for v0.1 Basic/paper
    feed: Literal["iex"] = Field(default="iex", alias="FEED")

    # Redis (fan-out, streams)
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Postgres (ledger, reconciler)
    database_url: str = Field(
        default="postgresql+asyncpg://stockbot:stockbot@localhost:5432/stockbot",
        alias="DATABASE_URL",
    )

    # v0.1: regular hours only
    extended_hours_enabled: bool = Field(default=False, alias="EXTENDED_HOURS_ENABLED")

    # Execution: shadow (no broker orders) | paper (place paper orders when enabled)
    execution_mode: Literal["shadow", "paper"] = Field(default="shadow", alias="EXECUTION_MODE")
    paper_execution_enabled: bool = Field(default=False, alias="PAPER_EXECUTION_ENABLED")
    order_type_default: Literal["market", "limit"] = Field(default="market", alias="ORDER_TYPE_DEFAULT")
    paper_allow_shorts: bool = Field(default=False, alias="PAPER_ALLOW_SHORTS")

    # Risk / sizing (paper mode)
    risk_per_trade_pct_equity: float = Field(default=0.5, alias="RISK_PER_TRADE_PCT_EQUITY")
    max_position_pct_equity: float = Field(default=10.0, alias="MAX_POSITION_PCT_EQUITY")
    max_gross_exposure_pct_equity: float = Field(default=50.0, alias="MAX_GROSS_EXPOSURE_PCT_EQUITY")
    max_symbol_exposure_pct_equity: float = Field(default=20.0, alias="MAX_SYMBOL_EXPOSURE_PCT_EQUITY")
    max_concurrent_positions: int = Field(default=5, alias="MAX_CONCURRENT_POSITIONS")
    default_stop_buffer_bps: int = Field(default=50, alias="DEFAULT_STOP_BUFFER_BPS")
    default_limit_price_offset_bps: int = Field(default=5, alias="DEFAULT_LIMIT_PRICE_OFFSET_BPS")

    # Polling / snapshot intervals (seconds)
    portfolio_snapshot_interval_sec: int = Field(default=60, alias="PORTFOLIO_SNAPSHOT_INTERVAL_SEC")
    account_poll_interval_sec: int = Field(default=60, alias="ACCOUNT_POLL_INTERVAL_SEC")

    # Backtest / research defaults
    backtest_default_lookback_years: float = Field(default=1.0, alias="BACKTEST_DEFAULT_LOOKBACK_YEARS")
    backtest_default_universe: str = Field(
        default="AAPL,AMD,AMZN,META,MSFT,NVDA,QQQ,SPY,TSLA",
        alias="BACKTEST_DEFAULT_UNIVERSE",
    )
    backtest_default_feed: str = Field(default="iex", alias="BACKTEST_DEFAULT_FEED")

    # INTRA_EVENT_MOMO strategy (fallback when scanner disabled or static mode)
    stockbot_universe: str = Field(
        default="AAPL,AMD,AMZN,META,MSFT,NVDA,QQQ,SPY,TSLA",
        alias="STOCKBOT_UNIVERSE",
    )

    # Opportunity engine: two-way discovery (market + semantic); strategy remains signal authority
    opportunity_engine_enabled: bool = Field(default=True, alias="OPPORTUNITY_ENGINE_ENABLED")
    opportunity_engine_mode: Literal["market_only", "semantic_only", "blended"] = Field(
        default="blended", alias="OPPORTUNITY_ENGINE_MODE"
    )
    opportunity_blend_market_weight: float = Field(default=0.65, alias="OPPORTUNITY_BLEND_MARKET_WEIGHT")
    opportunity_blend_semantic_weight: float = Field(default=0.35, alias="OPPORTUNITY_BLEND_SEMANTIC_WEIGHT")

    # Scrappy auto-run: proactive enrichment of top candidates (no manual click required)
    scrappy_auto_enabled: bool = Field(default=True, alias="SCRAPPY_AUTO_ENABLED")
    scrappy_auto_refresh_sec: int = Field(default=120, alias="SCRAPPY_AUTO_REFRESH_SEC")
    scrappy_auto_top_symbols: int = Field(default=15, alias="SCRAPPY_AUTO_TOP_SYMBOLS")
    scrappy_auto_trigger_mode: Literal["scanner_top", "news_top", "blended"] = Field(
        default="blended", alias="SCRAPPY_AUTO_TRIGGER_MODE"
    )

    # Session and extended hours (paper/strategy constraints)
    session_mode: str = Field(default="auto", alias="SESSION_MODE")
    extended_hours_paper_enabled: bool = Field(default=False, alias="EXTENDED_HOURS_PAPER_ENABLED")
    extended_hours_limit_only: bool = Field(default=True, alias="EXTENDED_HOURS_LIMIT_ONLY")

    # Scanner / opportunity discovery (dynamic candidate layer; strategy remains signal authority)
    scanner_enabled: bool = Field(default=True, alias="SCANNER_ENABLED")
    scanner_mode: Literal["static", "dynamic", "hybrid"] = Field(default="dynamic", alias="SCANNER_MODE")
    scanner_universe_mode: Literal["watchlist", "liquid_us_equities", "custom"] = Field(
        default="liquid_us_equities", alias="SCANNER_UNIVERSE_MODE"
    )
    scanner_custom_universe: str = Field(default="", alias="SCANNER_CUSTOM_UNIVERSE")
    scanner_max_symbols: int = Field(default=500, alias="SCANNER_MAX_SYMBOLS")
    scanner_top_candidates: int = Field(default=25, alias="SCANNER_TOP_CANDIDATES")
    scanner_min_price: float = Field(default=5.0, alias="SCANNER_MIN_PRICE")
    scanner_max_price: float = Field(default=500.0, alias="SCANNER_MAX_PRICE")
    scanner_min_dollar_volume_1m: float = Field(default=500_000.0, alias="SCANNER_MIN_DOLLAR_VOLUME_1M")
    scanner_min_rvol_5m: float = Field(default=1.2, alias="SCANNER_MIN_RVOL_5M")
    scanner_max_spread_bps: int = Field(default=35, alias="SCANNER_MAX_SPREAD_BPS")
    scanner_min_gap_pct: float = Field(default=0.5, alias="SCANNER_MIN_GAP_PCT")
    scanner_require_news: bool = Field(default=False, alias="SCANNER_REQUIRE_NEWS")
    scanner_require_scrappy: bool = Field(default=False, alias="SCANNER_REQUIRE_SCRAPPY")
    scanner_refresh_sec: int = Field(default=60, alias="SCANNER_REFRESH_SEC")
    scanner_premarket_enabled: bool = Field(default=True, alias="SCANNER_PREMARKET_ENABLED")
    scanner_regular_hours_enabled: bool = Field(default=True, alias="SCANNER_REGULAR_HOURS_ENABLED")
    scanner_after_hours_enabled: bool = Field(default=False, alias="SCANNER_AFTER_HOURS_ENABLED")
    scanner_overnight_enabled: bool = Field(default=False, alias="SCANNER_OVERNIGHT_ENABLED")
    scanner_include_etfs: bool = Field(default=True, alias="SCANNER_INCLUDE_ETFS")
    scanner_max_news_candidates: int = Field(default=50, alias="SCANNER_MAX_NEWS_CANDIDATES")
    scanner_price_lookback_bars: int = Field(default=20, alias="SCANNER_PRICE_LOOKBACK_BARS")
    scanner_news_lookback_minutes: int = Field(default=60, alias="SCANNER_NEWS_LOOKBACK_MINUTES")
    scanner_use_snapshot_bootstrap: bool = Field(default=True, alias="SCANNER_USE_SNAPSHOT_BOOTSTRAP")
    scanner_max_scrappy_symbols: int = Field(default=30, alias="SCANNER_MAX_SCRAPPY_SYMBOLS")
    scanner_max_worker_symbols: int = Field(default=25, alias="SCANNER_MAX_WORKER_SYMBOLS")
    scanner_history_default_lookback_days: int = Field(default=30, alias="SCANNER_HISTORY_DEFAULT_LOOKBACK_DAYS")
    scanner_bootstrap_on_start: bool = Field(default=True, alias="SCANNER_BOOTSTRAP_ON_START")
    opportunity_bootstrap_on_start: bool = Field(default=True, alias="OPPORTUNITY_BOOTSTRAP_ON_START")
    scrappy_bootstrap_on_start: bool = Field(default=True, alias="SCRAPPY_BOOTSTRAP_ON_START")

    # Market gateway: dynamic symbol refresh without restart
    market_gateway_symbol_refresh_sec: int = Field(default=60, alias="MARKET_GATEWAY_SYMBOL_REFRESH_SEC")
    market_gateway_force_reconnect_on_symbol_change: bool = Field(
        default=True, alias="MARKET_GATEWAY_FORCE_RECONNECT_ON_SYMBOL_CHANGE"
    )
    market_gateway_max_symbols: int = Field(default=50, alias="MARKET_GATEWAY_MAX_SYMBOLS")
    scanner_top_stale_sec: int = Field(
        default=900,
        alias="SCANNER_TOP_STALE_SEC",
    )  # max age for Redis top_symbols before static fallback

    shadow_slippage_bps: int = Field(default=5, alias="SHADOW_SLIPPAGE_BPS")
    shadow_fee_per_share: str = Field(default="0", alias="SHADOW_FEE_PER_SHARE")
    entry_start_et: str = Field(default="09:35", alias="ENTRY_START_ET")
    entry_end_et: str = Field(default="11:30", alias="ENTRY_END_ET")
    force_flat_et: str = Field(default="15:45", alias="FORCE_FLAT_ET")

    # Scrappy strategy bridge: off | advisory | required
    scrappy_mode: str = Field(default="advisory", alias="SCRAPPY_MODE")

    # AI_SETUP_REFEREE: bounded reasoning over Scrappy + market state (no order authority)
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")
    ai_referee_auth: str = Field(default="api_key", alias="AI_REFEREE_AUTH")  # api_key | oauth
    ai_referee_enabled: bool = Field(default=False, alias="AI_REFEREE_ENABLED")
    ai_referee_mode: str = Field(default="off", alias="AI_REFEREE_MODE")  # off | advisory | required
    ai_referee_model: str = Field(default="gpt-4o-mini", alias="AI_REFEREE_MODEL")  # e.g. gpt-5.4 for OAuth
    ai_referee_timeout_seconds: int = Field(default=15, alias="AI_REFEREE_TIMEOUT_SECONDS")
    ai_referee_max_input_headlines: int = Field(default=20, alias="AI_REFEREE_MAX_INPUT_HEADLINES")
    ai_referee_max_input_notes: int = Field(default=30, alias="AI_REFEREE_MAX_INPUT_NOTES")
    ai_referee_require_json: bool = Field(default=True, alias="AI_REFEREE_REQUIRE_JSON")


def get_settings() -> Settings:
    return Settings()


def get_settings_optional() -> Settings | None:
    try:
        return Settings()
    except Exception:
        return None
