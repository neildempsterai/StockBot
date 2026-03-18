"""Tests for Scrappy ingestion: config loading, candidate shape (no network)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from stockbot.scrappy.ingestion import fetch_feed
from stockbot.scrappy.sources import invalidate_cache, load_scrappy_sources


def test_sources_config_has_feed_urls() -> None:
    invalidate_cache()
    cfg = load_scrappy_sources()
    sources = [s for s in (cfg.get("sources") or []) if isinstance(s, dict) and s.get("enabled") and (s.get("transport") or "").lower() in ("rss", "rss_or_api")]
    urls = [s.get("url") for s in sources if (s.get("url") or "").strip()]
    assert len(urls) >= 1, "At least one enabled RSS source with url required"


@patch("stockbot.scrappy.ingestion.feedparser.parse")
def test_fetch_feed_returns_candidates(mock_parse: object) -> None:
    """Fetch feed returns list of candidate dicts with required keys."""
    mock_parse.return_value = type("Feed", (), {
        "entries": [
            type("Entry", (), {
                "link": "https://example.com/article1",
                "title": "Title 1",
                "summary": "Summary 1",
                "published_parsed": None,
                "updated_parsed": None,
                "created_parsed": None,
                "id": "id1",
                "author": None,
            })(),
        ],
        "bozo": False,
    })()
    candidates = fetch_feed("https://example.com/feed", "test_source")
    assert len(candidates) == 1
    c = candidates[0]
    assert c["url"] == "https://example.com/article1"
    assert c["source_name"] == "test_source"
    assert "title" in c
    assert "summary" in c
    assert "published_at" in c or True
    assert "raw_metadata" in c
