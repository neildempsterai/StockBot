"""Tests for Scrappy source config loading (market-intel)."""
from __future__ import annotations

from stockbot.scrappy.sources import (
    get_search_config,
    invalidate_cache,
    load_scrappy_sources,
)


def test_load_scrappy_sources_has_sections() -> None:
    invalidate_cache()
    cfg = load_scrappy_sources()
    assert "sources" in cfg
    assert "search" in cfg
    assert "watchlist_rules" in cfg
    assert "dedup" in cfg
    assert "extraction" in cfg


def test_get_search_config() -> None:
    invalidate_cache()
    cfg = get_search_config()
    assert "enabled_for_low_confidence" in cfg
    assert "confidence_threshold" in cfg
    assert "max_queries_per_sprint" in cfg
    assert "max_results_per_query" in cfg
    assert 0 <= cfg["confidence_threshold"] <= 1
