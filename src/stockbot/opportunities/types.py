"""Opportunity candidate and run types for blended ranking."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

CandidateSource = str  # "market" | "semantic" | "blended"


@dataclass
class OpportunityCandidate:
    """One symbol with market + semantic scores and explainable reasons."""
    symbol: str
    total_score: float
    market_score: float
    semantic_score: float
    candidate_source: CandidateSource
    inclusion_reasons: list[str] = field(default_factory=list)
    filter_reasons: list[str] = field(default_factory=list)
    component_scores: dict[str, float] = field(default_factory=dict)
    current_session: str = ""
    scrappy_present: bool = False
    news_count: int = 0
    freshness_minutes: int | None = None
    rank: int = 0
    raw_json: dict[str, Any] | None = None
