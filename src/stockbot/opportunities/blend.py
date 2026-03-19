"""Blend market and semantic candidates into one ranked opportunity list."""
from __future__ import annotations

from stockbot.opportunities.types import OpportunityCandidate

def blend_candidates(
    market_candidates: list[OpportunityCandidate],
    semantic_candidates: list[OpportunityCandidate],
    market_weight: float = 0.6,
    semantic_weight: float = 0.4,
    top_n: int = 25,
) -> list[OpportunityCandidate]:
    """
    Merge market and semantic lists, score by weighted sum, return top_n.
    Deterministic and explainable; no opaque ML.
    """
    by_symbol: dict[str, OpportunityCandidate] = {}
    for c in market_candidates:
        m = c.market_score if c.market_score else c.total_score
        s = c.semantic_score if c.semantic_score else 0.0
        c.market_score = m
        c.semantic_score = s
        c.candidate_source = "market"
        by_symbol[c.symbol] = c
    for c in semantic_candidates:
        s = c.semantic_score if c.semantic_score else c.total_score
        m = c.market_score if c.market_score else 0.0
        if c.symbol in by_symbol:
            existing = by_symbol[c.symbol]
            existing.semantic_score = s
            existing.candidate_source = "blended"
            existing.news_count = max(existing.news_count, c.news_count)
            existing.scrappy_present = existing.scrappy_present or c.scrappy_present
            existing.inclusion_reasons = list(set(existing.inclusion_reasons + c.inclusion_reasons))
        else:
            c.market_score = m
            c.semantic_score = s
            c.candidate_source = "semantic"
            by_symbol[c.symbol] = c
    for c in by_symbol.values():
        c.total_score = market_weight * c.market_score + semantic_weight * c.semantic_score
    ranked = sorted(by_symbol.values(), key=lambda x: -x.total_score)
    for i, c in enumerate(ranked[:top_n], start=1):
        c.rank = i
    return ranked[:top_n]
