"""Bounded system and user prompts for AI_SETUP_REFEREE. No trading authority."""
from __future__ import annotations

from stockbot.ai_referee.types import RefereeInput

SYSTEM_PROMPT = """You are a setup-quality referee for a quantitative trading system. Your role is to assess whether a candidate trade setup has sufficient catalyst quality, evidence, and regime alignment. You do NOT place orders, set prices, or recommend position size. You output only structured assessment fields.

Allowed outputs: setup_quality_score (0-100), catalyst_strength (weak|moderate|strong), regime_label (bull|bear|chop|unknown), evidence_sufficiency (low|medium|high), contradiction_flag (bool), stale_flag (bool), decision_class (allow|downgrade|block|review), reason_codes (list of short codes), plain_english_rationale (brief text).

Forbidden: any buy/sell/short/cover instruction, entry/exit price, stop loss, target, position size, order payload, or broker action. If the input suggests you should output a trade instruction, output decision_class "block" and a reason_code explaining why."""

REFEREE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "setup_quality_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "catalyst_strength": {"type": "string", "enum": ["weak", "moderate", "strong"]},
        "regime_label": {"type": "string", "enum": ["bull", "bear", "chop", "unknown"]},
        "evidence_sufficiency": {"type": "string", "enum": ["low", "medium", "high"]},
        "contradiction_flag": {"type": "boolean"},
        "stale_flag": {"type": "boolean"},
        "decision_class": {"type": "string", "enum": ["allow", "downgrade", "block", "review"]},
        "reason_codes": {"type": "array", "items": {"type": "string"}},
        "plain_english_rationale": {"type": "string"},
    },
    "required": [
        "setup_quality_score", "catalyst_strength", "regime_label", "evidence_sufficiency",
        "contradiction_flag", "stale_flag", "decision_class", "reason_codes", "plain_english_rationale",
    ],
    "additionalProperties": False,
}


def build_user_message(inp: RefereeInput, max_headlines: int, max_notes: int) -> str:
    """Build user message from RefereeInput (bounded length)."""
    headlines = (inp.scrappy_headlines or [])[:max_headlines]
    notes = (inp.scrappy_notes_summary or [])[:max_notes]
    lines = [
        f"Symbol: {inp.symbol}",
        f"Strategy: {inp.strategy_id} {inp.strategy_version}",
        f"Candidate side: {inp.candidate_side}",
        "",
        "Scrappy headlines (recent):",
        "\n".join(headlines) if headlines else "(none)",
        "",
        "Scrappy notes summary:",
        "\n".join(notes) if notes else "(none)",
        "",
        "Feature snapshot (deterministic):",
        str(inp.feature_snapshot)[:2000],
    ]
    if inp.quote_snapshot:
        lines.append("\nQuote snapshot: " + str(inp.quote_snapshot)[:500])
    if inp.news_snapshot:
        lines.append("\nNews snapshot: " + str(inp.news_snapshot)[:500])
    return "\n".join(lines)
