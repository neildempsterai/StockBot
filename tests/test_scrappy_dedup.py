"""Tests for Scrappy dedup: URL normalization, hash stability, reason codes, filter."""
from __future__ import annotations

import os

import pytest

from stockbot.scrappy.dedup import (
    DEDUP_DUPLICATE_IN_BATCH,
    DEDUP_JUNK_DOMAIN,
    DEDUP_MISSING_REQUIRED_METADATA,
    filter_candidates_with_reasons,
    get_min_candidates_to_proceed,
    is_junk_domain,
    normalize_url,
    url_hash,
)


def test_normalize_url() -> None:
    assert normalize_url("https://example.com/path") == "https://example.com/path"
    assert normalize_url("https://example.com/path/") == "https://example.com/path"
    assert normalize_url("https://WWW.Example.COM/Path") == "https://example.com/Path"
    assert normalize_url("https://example.com/path#section") == "https://example.com/path"
    assert normalize_url("") == ""
    assert normalize_url("https://example.com") == "https://example.com/"
    assert normalize_url("https://example.com/") == "https://example.com/"


def test_url_hash_stable() -> None:
    h1 = url_hash("https://example.com/path")
    h2 = url_hash("https://EXAMPLE.COM/path/")
    assert h1 == h2
    assert len(h1) == 32


def test_is_junk_domain() -> None:
    assert is_junk_domain("https://facebook.com/page") is True
    assert is_junk_domain("https://twitter.com/x") is True
    assert is_junk_domain("https://reuters.com/article") is False
    assert is_junk_domain("https://example.com/article") is False


def test_dedup_reason_codes() -> None:
    assert DEDUP_DUPLICATE_IN_BATCH == "duplicate_in_batch"
    assert DEDUP_JUNK_DOMAIN == "junk_domain"
    assert DEDUP_MISSING_REQUIRED_METADATA == "missing_required_metadata"


def test_filter_candidates_duplicate_in_batch() -> None:
    def never_seen(_: str) -> bool:
        return False
    def never_recrawl(_: str) -> bool:
        return False
    def no_block(_: str, item: dict | None = None) -> bool:
        return False
    def no_junk(_: str) -> bool:
        return False
    candidates = [
        {"url": "https://example.com/a", "title": "A"},
        {"url": "https://example.com/a", "title": "A again"},
    ]
    eligible, drops = filter_candidates_with_reasons(
        candidates,
        url_seen_fn=never_seen,
        url_seen_recent_fn=never_recrawl,
        policy_blocked_fn=no_block,
        junk_fn=no_junk,
        recrawl_eligible_fn=never_recrawl,
    )
    assert len(eligible) == 1
    assert len(drops) == 1
    assert drops[0]["reason"] == DEDUP_DUPLICATE_IN_BATCH


def test_filter_candidates_junk_domain() -> None:
    def never_seen(_: str) -> bool:
        return False
    def never_recrawl(_: str) -> bool:
        return False
    def no_block(_: str, item: dict | None = None) -> bool:
        return False
    candidates = [{"url": "https://facebook.com/page", "title": "FB"}]
    eligible, drops = filter_candidates_with_reasons(
        candidates,
        url_seen_fn=never_seen,
        url_seen_recent_fn=never_recrawl,
        policy_blocked_fn=no_block,
        junk_fn=lambda u: "facebook" in u,
        recrawl_eligible_fn=never_recrawl,
    )
    assert len(eligible) == 0
    assert len(drops) == 1
    assert drops[0]["reason"] == DEDUP_JUNK_DOMAIN


def test_get_min_candidates_to_proceed() -> None:
    orig = os.environ.get("SCRAPPY_DEDUP_MIN_CANDIDATES")
    try:
        os.environ["SCRAPPY_DEDUP_MIN_CANDIDATES"] = "3"
        assert get_min_candidates_to_proceed() == 3
        os.environ["SCRAPPY_DEDUP_MIN_CANDIDATES"] = "0"
        assert get_min_candidates_to_proceed() == 0
    finally:
        if orig is not None:
            os.environ["SCRAPPY_DEDUP_MIN_CANDIDATES"] = orig
        else:
            os.environ.pop("SCRAPPY_DEDUP_MIN_CANDIDATES", None)
