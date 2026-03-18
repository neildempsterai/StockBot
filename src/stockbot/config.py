"""App config via env. v0.1: regular hours only; no extended/overnight."""
from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Alpaca (required for gateways)
    alpaca_api_key_id: str = Field(..., alias="ALPACA_API_KEY_ID")
    alpaca_api_secret_key: str = Field(..., alias="ALPACA_API_SECRET_KEY")
    alpaca_base_url: str = Field(
        default="https://paper-api.alpaca.markets",
        alias="ALPACA_BASE_URL",
    )
    alpaca_data_ws_url: str = Field(
        default="wss://stream.data.alpaca.markets/v2/iex",
        alias="ALPACA_DATA_WS_URL",
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

    # INTRA_EVENT_MOMO strategy
    stockbot_universe: str = Field(
        default="AAPL,AMD,AMZN,META,MSFT,NVDA,QQQ,SPY,TSLA",
        alias="STOCKBOT_UNIVERSE",
    )
    shadow_slippage_bps: int = Field(default=5, alias="SHADOW_SLIPPAGE_BPS")
    shadow_fee_per_share: str = Field(default="0", alias="SHADOW_FEE_PER_SHARE")
    entry_start_et: str = Field(default="09:35", alias="ENTRY_START_ET")
    entry_end_et: str = Field(default="11:30", alias="ENTRY_END_ET")
    force_flat_et: str = Field(default="15:45", alias="FORCE_FLAT_ET")

    # Scrappy strategy bridge: off | advisory | required
    scrappy_mode: str = Field(default="advisory", alias="SCRAPPY_MODE")


def get_settings() -> Settings:
    return Settings()


def get_settings_optional() -> Settings | None:
    try:
        return Settings()
    except Exception:
        return None
