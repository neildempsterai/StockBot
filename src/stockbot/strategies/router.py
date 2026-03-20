"""
Strategy router: session-aware strategy selection and evaluation.
Determines which strategies are active in the current session and routes evaluation accordingly.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from stockbot.market_sessions import current_session, et_time_in_range


@dataclass
class StrategyConfig:
    """Configuration for a strategy's session eligibility."""
    strategy_id: str
    strategy_version: str
    entry_start_et: str
    entry_end_et: str
    force_flat_et: str | None  # None = no force-flat (swing strategies)
    enabled: bool = True
    paper_enabled: bool = False
    holding_period_type: str = "intraday"  # "intraday" | "swing"
    max_hold_days: int = 0  # 0 = intraday (close same day)


def get_active_strategies(ts: datetime, configs: list[StrategyConfig]) -> list[StrategyConfig]:
    """
    Return list of strategies that are currently active (within entry window and enabled).
    """
    active = []
    for config in configs:
        if not config.enabled:
            continue
        if et_time_in_range(ts, config.entry_start_et, config.entry_end_et):
            active.append(config)
    return active


def get_strategy_priority(strategy_id: str) -> int:
    """
    Return priority for strategy selection when multiple strategies are active.
    Lower number = higher priority.
    """
    priorities = {
        "OPEN_DRIVE_MOMO": 1,
        "INTRADAY_CONTINUATION": 2,
        "INTRA_EVENT_MOMO": 3,
        "SWING_EVENT_CONTINUATION": 4,
    }
    return priorities.get(strategy_id, 99)


def should_evaluate_strategy(
    strategy_id: str,
    symbol: str,
    ts: datetime,
    already_traded_today: set[str],
    configs: list[StrategyConfig],
) -> tuple[bool, str | None]:
    """
    Determine if a strategy should evaluate a symbol at this time.
    Returns (should_evaluate, reason_if_not).
    
    Rules:
    - Strategy must be active (in entry window)
    - Strategy must be enabled
    - Symbol must not have been traded today by this strategy (one trade per symbol per strategy per day)
    """
    config = next((c for c in configs if c.strategy_id == strategy_id), None)
    if not config:
        return (False, "strategy_not_configured")
    
    if not config.enabled:
        return (False, "strategy_disabled")
    
    if not et_time_in_range(ts, config.entry_start_et, config.entry_end_et):
        return (False, "outside_entry_window")
    
    # Check if symbol already traded by this strategy today
    strategy_traded_key = f"{strategy_id}:{symbol}"
    if strategy_traded_key in already_traded_today:
        return (False, "already_traded_today")
    
    return (True, None)


def select_primary_strategy(
    active_strategies: list[StrategyConfig],
    symbol: str,
    already_traded_today: set[str],
) -> StrategyConfig | None:
    """
    Select the primary strategy to evaluate when multiple are active.
    Priority: OPEN_DRIVE_MOMO > INTRADAY_CONTINUATION > INTRA_EVENT_MOMO > SWING_EVENT_CONTINUATION.
    Also checks if symbol already traded by a strategy.
    """
    if not active_strategies:
        return None

    sorted_strategies = sorted(active_strategies, key=lambda c: get_strategy_priority(c.strategy_id))

    for config in sorted_strategies:
        strategy_traded_key = f"{config.strategy_id}:{symbol}"
        if strategy_traded_key not in already_traded_today:
            return config

    return None


def get_all_eligible_strategies(
    active_strategies: list[StrategyConfig],
    symbol: str,
    already_traded_today: set[str],
    open_positions_by_symbol: dict[str, str],
) -> list[StrategyConfig]:
    """Return ALL eligible strategies for a symbol in priority order.

    Unlike select_primary_strategy (which returns only one), this allows
    the caller to evaluate multiple strategies and pick the best signal
    via quality scoring.
    """
    if not active_strategies:
        return []
    eligible: list[StrategyConfig] = []
    for config in sorted(active_strategies, key=lambda c: get_strategy_priority(c.strategy_id)):
        strategy_traded_key = f"{config.strategy_id}:{symbol}"
        if strategy_traded_key in already_traded_today:
            continue
        conflict, _ = has_conflicting_position(symbol, config.strategy_id, open_positions_by_symbol)
        if conflict:
            continue
        eligible.append(config)
    return eligible


def has_conflicting_position(
    symbol: str,
    candidate_strategy_id: str,
    open_positions_by_symbol: dict[str, str],
) -> tuple[bool, str | None]:
    """
    Check if entering a trade would conflict with an existing position.
    Rules:
    - If symbol has an open swing position, block intraday entry on same symbol.
    - If symbol has an open intraday position, block swing entry on same symbol.
    Returns (has_conflict, reason_if_conflict).
    """
    existing_strategy = open_positions_by_symbol.get(symbol)
    if existing_strategy is None:
        return (False, None)

    SWING_STRATEGIES = {"SWING_EVENT_CONTINUATION"}
    INTRADAY_STRATEGIES = {"OPEN_DRIVE_MOMO", "INTRADAY_CONTINUATION", "INTRA_EVENT_MOMO"}

    if candidate_strategy_id in INTRADAY_STRATEGIES and existing_strategy in SWING_STRATEGIES:
        return (True, "symbol_has_open_swing_position")
    if candidate_strategy_id in SWING_STRATEGIES and existing_strategy in INTRADAY_STRATEGIES:
        return (True, "symbol_has_open_intraday_position")
    if candidate_strategy_id == existing_strategy:
        return (True, "symbol_already_has_position_same_strategy")
    return (False, None)
