"""Tests for Scrappy note generation: dedup_hash, validation, build from candidate, strict JSON draft."""
from __future__ import annotations

import pytest

from stockbot.scrappy.notes import (
    _parse_and_validate_note_draft_json,
    build_note_from_candidate,
    dedup_hash_from_candidate,
    draft_note_with_llm,
    extract_symbols_from_text,
    validate_note_payload,
)


def test_dedup_hash_stable() -> None:
    c = {
        "url": "https://example.com/article",
        "source_url": "https://example.com/feed",
        "published_at": "2024-01-15T12:00:00Z",
    }
    h1 = dedup_hash_from_candidate(c)
    h2 = dedup_hash_from_candidate(c)
    assert h1 == h2
    assert len(h1) == 64


def test_dedup_hash_different_url_different_hash() -> None:
    c1 = {"url": "https://a.com/1", "published_at": None}
    c2 = {"url": "https://a.com/2", "published_at": None}
    assert dedup_hash_from_candidate(c1) != dedup_hash_from_candidate(c2)


def test_extract_symbols_from_text() -> None:
    assert "AAPL" in extract_symbols_from_text("AAPL reported earnings")
    assert "MSFT" in extract_symbols_from_text("MSFT and GOOG lead tech")
    # Common words filtered out
    assert "CEO" not in extract_symbols_from_text("The CEO said AAPL is strong")


def test_build_note_from_candidate() -> None:
    c = {
        "url": "https://sec.gov/Archives/edgar/123",
        "source_name": "sec_edgar",
        "source_url": "https://sec.gov/feed",
        "published_at": "2024-01-01T00:00:00Z",
        "title": "10-K Filing",
        "summary": "Annual report",
        "raw_metadata": {},
    }
    payload = build_note_from_candidate(c, "run-456")
    assert payload["source_name"] == "sec_edgar"
    assert payload["source_url"] == "https://sec.gov/Archives/edgar/123"
    assert payload["title"] == "10-K Filing"
    assert payload["dedup_hash"]
    assert payload["content_mode"] in ("open_text", "metadata_only")
    assert payload["catalyst_type"] == "sec_filing"
    assert payload["scrappy_run_id"] == "run-456"


def test_validate_note_payload_ok() -> None:
    payload = {
        "source_url": "https://example.com",
        "source_name": "test",
        "dedup_hash": "a" * 64,
        "catalyst_type": "earnings",
        "sentiment_label": "neutral",
        "impact_horizon": "swing",
        "content_mode": "metadata_only",
    }
    validate_note_payload(payload)


def test_validate_note_payload_missing_required() -> None:
    with pytest.raises(ValueError, match="source_url"):
        validate_note_payload({"source_name": "x", "dedup_hash": "a" * 64})
    with pytest.raises(ValueError, match="dedup_hash"):
        validate_note_payload({"source_url": "https://x.com", "source_name": "x"})


def test_validate_note_payload_invalid_catalyst() -> None:
    with pytest.raises(ValueError, match="catalyst_type"):
        validate_note_payload({
            "source_url": "https://x.com",
            "source_name": "x",
            "dedup_hash": "a" * 64,
            "catalyst_type": "invalid_cat",
        })


def test_parse_and_validate_note_draft_json_success() -> None:
    raw = '{"summary": "A brief summary.", "why_this_matters": "Relevant for context."}'
    out = _parse_and_validate_note_draft_json(raw)
    assert out is not None
    assert out.get("summary") == "A brief summary."
    assert out.get("why_this_matters") == "Relevant for context."


def test_parse_and_validate_note_draft_json_with_code_block() -> None:
    raw = '```json\n{"summary": "S.", "why_this_matters": "W."}\n```'
    out = _parse_and_validate_note_draft_json(raw)
    assert out is not None
    assert out.get("summary") == "S."
    assert out.get("why_this_matters") == "W."


def test_parse_and_validate_note_draft_json_failure_invalid_json() -> None:
    assert _parse_and_validate_note_draft_json("SUMMARY: foo\nWHY_THIS_MATTERS: bar") is None
    assert _parse_and_validate_note_draft_json("not json at all") is None
    assert _parse_and_validate_note_draft_json("") is None
    assert _parse_and_validate_note_draft_json('{"other": "key"}') is None


def test_parse_and_validate_note_draft_json_truncates_long_fields() -> None:
    long_summary = "x" * 10000
    raw = f'{{"summary": "{long_summary}", "why_this_matters": "short"}}'
    out = _parse_and_validate_note_draft_json(raw)
    assert out is not None
    assert len(out["summary"]) == 5000
    assert out["why_this_matters"] == "short"


def test_draft_note_malformed_json_fallback() -> None:
    """Malformed LLM output parses as None; valid JSON parses to dict. Deterministic fallback in draft_note_with_llm uses only validated fields."""
    result = _parse_and_validate_note_draft_json("SUMMARY: text\nWHY_THIS_MATTERS: other")
    assert result is None
    out = _parse_and_validate_note_draft_json('{"summary": "New", "why_this_matters": "W"}')
    assert out and out["summary"] == "New"


def test_build_note_uses_policy_decision_when_set() -> None:
    """content_mode should come from candidate's policy_decision when set."""
    c = {
        "url": "https://sec.gov/Archives/edgar/123",
        "source_name": "sec_edgar",
        "published_at": "2024-01-01T00:00:00Z",
        "title": "10-K",
        "summary": "Report",
        "policy_decision": "metadata_only",
        "policy_reason_code": "allowed_metadata_only",
    }
    payload = build_note_from_candidate(c, "run-456")
    assert payload["content_mode"] == "metadata_only"
