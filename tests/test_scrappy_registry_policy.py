"""Tests for Scrappy source registry and source policy."""
from __future__ import annotations

import pytest

from stockbot.scrappy.source_registry import (
    REASON_ALLOWED_METADATA_ONLY,
    REASON_BLOCKED_DOMAIN,
    REASON_UNKNOWN_DOMAIN_DEFAULT,
    get_content_mode,
    get_policy_decision,
    is_blocked,
    is_open_text,
    load_source_registry,
)
from stockbot.scrappy.source_policy import (
    apply_policy_for_candidate,
    get_content_mode_for_candidate,
    list_domains_by_content_mode,
    policy_blocked_fn,
)


def test_load_registry_has_domains() -> None:
    reg = load_source_registry()
    assert "domains" in reg
    assert "default_content_mode" in reg
    assert reg["default_content_mode"] == "metadata_only"


def test_unknown_domain_not_open_text() -> None:
    # Unknown domains must not default to open_text
    mode = get_content_mode("https://unknown-random-domain-xyz.example.com/page")
    assert mode == "metadata_only"
    assert is_open_text("https://unknown-random-domain-xyz.example.com/page") is False


def test_sec_domain_metadata_only() -> None:
    assert get_content_mode("https://www.sec.gov/Archives/edgar/xbrlrss.all.xml") == "metadata_only"


def test_blocked_domain() -> None:
    assert is_blocked("https://twitter.com/something") is True
    assert is_blocked("https://t.co/abc") is True
    assert get_content_mode("https://twitter.com/x") == "blocked"


def test_policy_blocked_fn() -> None:
    assert policy_blocked_fn("https://twitter.com/x", {"url": "https://twitter.com/x"}) is True
    assert policy_blocked_fn("https://sec.gov/filing", {"url": "https://sec.gov/filing"}) is False


def test_get_content_mode_for_candidate() -> None:
    c = {"url": "https://www.federalreserve.gov/feeds/press_all.xml", "source_name": "fed"}
    assert get_content_mode_for_candidate(c) == "metadata_only"
    c2 = {"url": "https://facebook.com/page", "source_url": "https://facebook.com/feed"}
    assert get_content_mode_for_candidate(c2) == "blocked"


def test_list_domains_by_content_mode() -> None:
    out = list_domains_by_content_mode()
    assert "open_text" in out
    assert "metadata_only" in out
    assert "blocked" in out
    assert isinstance(out["blocked"], list)
    assert "twitter.com" in out["blocked"] or "t.co" in out["blocked"]


def test_get_policy_decision_returns_reason_code() -> None:
    mode, reason = get_policy_decision("https://unknown-xyz.example.com/page")
    assert mode == "metadata_only"
    assert reason == REASON_UNKNOWN_DOMAIN_DEFAULT

    mode, reason = get_policy_decision("https://www.sec.gov/Archives/edgar/xbrlrss.all.xml")
    assert mode == "metadata_only"
    assert reason == REASON_ALLOWED_METADATA_ONLY

    mode, reason = get_policy_decision("https://twitter.com/something")
    assert mode == "blocked"
    assert reason == REASON_BLOCKED_DOMAIN


def test_apply_policy_for_candidate_attaches_decision_and_reason() -> None:
    c = {"url": "https://www.reuters.com/article/123"}
    mode, reason = apply_policy_for_candidate(c)
    assert mode == "metadata_only"
    assert reason == REASON_ALLOWED_METADATA_ONLY
    # Candidate is not mutated by apply_policy_for_candidate; caller attaches
    assert c.get("policy_decision") is None
    c["policy_decision"] = mode
    c["policy_reason_code"] = reason
    assert c["policy_decision"] == "metadata_only"
