"""Scrappy types: symbol intelligence snapshot contract for strategy bridge."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

# Catalyst direction for gating: positive | negative | neutral | conflicting
CATALYST_DIRECTION_POSITIVE = "positive"
CATALYST_DIRECTION_NEGATIVE = "negative"
CATALYST_DIRECTION_NEUTRAL = "neutral"
CATALYST_DIRECTION_CONFLICTING = "conflicting"

SCRAPPY_VERSION = "0.1.0"


@dataclass
class SymbolIntelligenceSnapshot:
    """
    Normalized symbol-scoped intelligence from Scrappy output.
    Used only as gate/filter/tag/attribution; no trade instructions.
    """
    snapshot_id: str | None  # set after persist
    symbol: str
    snapshot_ts: datetime
    freshness_minutes: int
    catalyst_direction: str  # positive | negative | neutral | conflicting
    catalyst_strength: int  # 0..100
    sentiment_label: str | None
    evidence_count: int
    source_count: int
    source_domains: list[str]
    thesis_tags: list[str]
    headline_set: list[str]
    stale_flag: bool
    conflict_flag: bool
    raw_evidence_refs: list[dict[str, Any]]
    scrappy_run_id: str | None
    scrappy_version: str
