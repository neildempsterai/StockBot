"""Strict typed models for AI referee input and assessment. No order/trading authority."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class RefereeInput:
    """Input assembled for the referee: Scrappy snapshot + features + strategy metadata."""
    symbol: str
    strategy_id: str
    strategy_version: str
    scrappy_snapshot_id: int | None
    scrappy_run_id: str | None
    scrappy_headlines: list[str]
    scrappy_notes_summary: list[str]
    feature_snapshot: dict[str, Any]
    quote_snapshot: dict[str, Any] | None
    news_snapshot: dict[str, Any] | None
    candidate_side: str  # "buy" | "sell"


CATALYST_STRENGTH = ("weak", "moderate", "strong")
REGIME_LABEL = ("bull", "bear", "chop", "unknown")
EVIDENCE_SUFFICIENCY = ("low", "medium", "high")
DECISION_CLASS = ("allow", "downgrade", "block", "review")


@dataclass
class RefereeAssessment:
    """Structured referee output only. No prices, no order instructions."""
    assessment_id: str
    assessment_ts: datetime
    symbol: str
    strategy_id: str
    strategy_version: str
    scrappy_snapshot_id: int | None
    scrappy_run_id: str | None
    model_name: str
    referee_version: str
    setup_quality_score: int  # 0..100
    catalyst_strength: str  # weak | moderate | strong
    regime_label: str  # bull | bear | chop | unknown
    evidence_sufficiency: str  # low | medium | high
    contradiction_flag: bool
    stale_flag: bool
    decision_class: str  # allow | downgrade | block | review
    reason_codes: list[str]
    plain_english_rationale: str
    raw_response_json: dict[str, Any]
