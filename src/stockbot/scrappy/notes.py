"""Structured note generation: dedup_hash, validation, build from candidate, optional LLM draft."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime
from decimal import Decimal
from typing import Any

from stockbot.scrappy.dedup import normalize_url
from stockbot.scrappy.schema import (
    is_valid_catalyst_type,
    is_valid_impact_horizon,
    is_valid_sentiment_label,
)
from stockbot.scrappy.source_policy import get_content_mode_for_candidate

logger = logging.getLogger(__name__)

# Strict JSON schema for LLM note draft (summary, why_this_matters only)
NOTE_DRAFT_JSON_SCHEMA_KEYS = ("summary", "why_this_matters")
MAX_SUMMARY_CHARS = 5000
MAX_WHY_MATTERS_CHARS = 2000


def dedup_hash_from_candidate(candidate: dict[str, Any]) -> str:
    """Stable hash for idempotent note insert: normalized_url + published_at."""
    url = normalize_url((candidate.get("url") or candidate.get("source_url") or "").strip())
    pub = candidate.get("published_at")
    if isinstance(pub, datetime):
        pub = pub.isoformat()
    elif pub is None:
        pub = ""
    raw = f"{url}|{pub}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]


def extract_symbols_from_text(text: str, max_symbols: int = 8) -> list[str]:
    """Simple ticker extraction: all-caps 1-5 letter words that look like tickers."""
    if not text:
        return []
    # Match standalone all-caps words of 1-5 chars (common ticker pattern)
    pattern = r"\b([A-Z]{1,5})\b"
    candidates = re.findall(pattern, text)
    # Filter out common non-tickers
    skip = {"I", "A", "CEO", "CFO", "IPO", "SEC", "ETF", "USA", "US", "EU", "GDP", "CPI", "FDA", "IRS"}
    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        if c in skip or c in seen:
            continue
        seen.add(c)
        out.append(c)
        if len(out) >= max_symbols:
            break
    return out


def build_note_from_candidate(
    candidate: dict[str, Any],
    scrappy_run_id: str,
    *,
    primary_symbol: str | None = None,
    symbol_context: list[str] | None = None,
) -> dict[str, Any]:
    """
    Build a market_intel_note payload from candidate. Validates and sets defaults.
    content_mode from candidate's policy_decision (set by run_service); dedup_hash from candidate.
    """
    content_mode = (candidate.get("policy_decision") or get_content_mode_for_candidate(candidate))
    dhash = dedup_hash_from_candidate(candidate)
    title = (candidate.get("title") or "")[:512]
    # Use full_text from open_text fetch when present
    summary = (candidate.get("full_text") or candidate.get("summary") or "")[:5000]
    source_url = (candidate.get("url") or candidate.get("source_url") or "").strip()
    source_name = (candidate.get("source_name") or "unknown").strip()
    published_at = candidate.get("published_at")
    if isinstance(published_at, str):
        try:
            published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except Exception:
            published_at = None
    if not source_url:
        raise ValueError("source_url required")
    # Extract symbols from title + summary
    combined = f"{title} {summary}"
    detected = extract_symbols_from_text(combined)
    if symbol_context and not primary_symbol and detected:
        for s in symbol_context:
            if s in detected:
                primary_symbol = s
                break
    if not primary_symbol and detected:
        primary_symbol = detected[0]
    # Infer catalyst from source/focus
    catalyst_type = "sec_filing" if "sec.gov" in source_url.lower() else "regulation"
    if "federalreserve" in source_url.lower() or "bls" in source_url.lower():
        catalyst_type = "macro_rates"
    # Default sentiment
    sentiment_label = "neutral"
    confidence = Decimal("0.6")
    impact_horizon = "background"
    return {
        "source_name": source_name,
        "source_url": source_url,
        "published_at": published_at,
        "title": title or None,
        "summary": summary or None,
        "evidence_snippets": [summary[:500]] if summary else None,
        "detected_symbols": detected if detected else None,
        "primary_symbol": primary_symbol,
        "sector_tags": None,
        "theme_tags": candidate.get("focus_tags") or None,
        "catalyst_type": catalyst_type,
        "sentiment_label": sentiment_label,
        "sentiment_score": Decimal("0"),
        "confidence": confidence,
        "impact_horizon": impact_horizon,
        "why_this_matters": None,
        "expires_at": None,
        "content_mode": content_mode,
        "dedup_hash": dhash,
        "raw_metadata": candidate.get("raw_metadata") or {},
        "scrappy_run_id": scrappy_run_id,
    }


def _parse_and_validate_note_draft_json(raw: str) -> dict[str, str] | None:
    """
    Parse LLM output as JSON and validate against note-draft schema.
    Returns dict with only summary and why_this_matters (validated) or None if invalid.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    # Allow single JSON object possibly wrapped in markdown code block
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                raw = part
                break
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    out: dict[str, str] = {}
    for key in NOTE_DRAFT_JSON_SCHEMA_KEYS:
        val = data.get(key)
        if val is None:
            continue
        if not isinstance(val, str):
            continue
        s = val.strip()
        if key == "summary":
            out["summary"] = s[:MAX_SUMMARY_CHARS]
        elif key == "why_this_matters":
            out["why_this_matters"] = s[:MAX_WHY_MATTERS_CHARS]
    return out if out else None


def draft_note_with_llm(payload: dict[str, Any], max_summary_chars: int = 5000) -> dict[str, Any]:
    """
    Call router structured_note_draft; expect JSON only. Validate and apply only validated fields.
    On malformed JSON or invalid schema, return payload unchanged (deterministic fallback).
    Never insert notes that violate schema; invalid LLM output does not alter required fields.
    """
    try:
        from stockbot.scrappy.llm.router import call, get_route
    except ImportError:
        return payload
    if get_route("structured_note_draft") is None:
        return payload
    title = (payload.get("title") or "")[:512]
    summary = (payload.get("summary") or "")[:8000]
    source = (payload.get("source_url") or "")[:200]
    prompt = f"""Title: {title}

Source: {source}

Raw summary or excerpt:
{summary}

Return a single JSON object with exactly two string fields:
- "summary": 2-4 sentences for a market-intel note.
- "why_this_matters": 1-2 sentences on relevance for trading context.

Output ONLY valid JSON, no other text. Example:
{{"summary": "...", "why_this_matters": "..."}}"""
    system = "You are a market-intel analyst. Respond with valid JSON only. Be concise and factual."
    text, meta = call("structured_note_draft", prompt, system=system)
    if not meta.get("success") or not (text or "").strip():
        return payload
    parsed = _parse_and_validate_note_draft_json(text)
    if not parsed:
        logger.warning("draft_note_with_llm: invalid or malformed JSON, using deterministic fields only")
        return payload
    out = dict(payload)
    if "summary" in parsed:
        out["summary"] = parsed["summary"][:max_summary_chars]
    if "why_this_matters" in parsed:
        out["why_this_matters"] = parsed["why_this_matters"]
    return out


def validate_note_payload(payload: dict[str, Any]) -> None:
    """Raise ValueError if required fields missing or invalid."""
    if not (payload.get("source_url") and payload.get("source_name")):
        raise ValueError("source_url and source_name required")
    if not payload.get("dedup_hash"):
        raise ValueError("dedup_hash required")
    c = payload.get("catalyst_type")
    if c and not is_valid_catalyst_type(c):
        raise ValueError(f"invalid catalyst_type: {c}")
    s = payload.get("sentiment_label")
    if s and not is_valid_sentiment_label(s):
        raise ValueError(f"invalid sentiment_label: {s}")
    h = payload.get("impact_horizon")
    if h and not is_valid_impact_horizon(h):
        raise ValueError(f"invalid impact_horizon: {h}")
    mode = payload.get("content_mode")
    if mode and mode not in ("open_text", "metadata_only", "blocked"):
        raise ValueError(f"invalid content_mode: {mode}")
