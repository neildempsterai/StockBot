"""Scanner types: candidate result, run result, component scores."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass
class ComponentScores:
    """Explainable score components for ranking."""
    price_score: float = 0.0
    gap_score: float = 0.0
    spread_score: float = 0.0
    volume_score: float = 0.0
    rvol_score: float = 0.0
    vwap_distance_score: float = 0.0
    news_score: float = 0.0
    scrappy_score: float = 0.0
    opening_range_score: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "price": self.price_score,
            "gap": self.gap_score,
            "spread": self.spread_score,
            "volume": self.volume_score,
            "rvol": self.rvol_score,
            "vwap_distance": self.vwap_distance_score,
            "news": self.news_score,
            "scrappy": self.scrappy_score,
            "opening_range": self.opening_range_score,
        }


@dataclass
class ScannerCandidate:
    """One symbol's scan result: score, status, filter reasons."""
    symbol: str
    total_score: float
    component_scores: ComponentScores
    reason_codes: list[str]
    candidate_status: str  # "top_candidate" | "filtered_out"
    filter_reasons: list[str]
    # Raw metrics for persistence/API
    price: Decimal | None = None
    gap_pct: float | None = None
    spread_bps: int | None = None
    dollar_volume_1m: float | None = None
    rvol_5m: float | None = None
    vwap_distance_pct: float | None = None
    news_count: int = 0
    scrappy_present: bool = False
    scrappy_catalyst_direction: str | None = None
    raw_snapshot_json: dict[str, Any] | None = None
    rank: int = 0


@dataclass
class ScannerRunResult:
    """Result of one scanner run."""
    run_id: str
    run_ts: datetime
    mode: str
    universe_mode: str
    universe_size: int
    candidates_scored: int
    top_candidates_count: int
    market_session: str
    status: str
    notes: str | None
    candidates: list[ScannerCandidate] = field(default_factory=list)
