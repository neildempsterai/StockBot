"""Shared types for all strategy modules."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalResult:
    """Result of strategy evaluation: no signal, or long/short with reason codes."""
    side: str | None  # None | "buy" | "sell"
    reason_codes: list[str]
    feature_snapshot: dict[str, Any]
    passes_filters: bool
    reject_reason: str | None
    quality_score: int = 0  # 0-100 entry quality score
    quality_components: dict[str, Any] = field(default_factory=dict)
