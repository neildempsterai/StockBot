"""Deterministic news classification for INTRA_EVENT_MOMO."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from stockbot.strategies.intra_event_momo import (
    NewsItem,
    classify_news_side,
    news_keyword_hits,
    POSITIVE_KEYWORDS,
    NEGATIVE_KEYWORDS,
)


def test_positive_news_tagging() -> None:
    items = [
        NewsItem(
            headline="Company beats earnings expectations",
            summary="Raised guidance for the year",
            published_at=datetime.now(timezone.utc),
            symbol="AAPL",
            raw={},
        )
    ]
    assert classify_news_side(items, within_minutes=60) == "long"


def test_negative_news_tagging() -> None:
    items = [
        NewsItem(
            headline="Company misses revenue targets",
            summary="Downgrade by analyst",
            published_at=datetime.now(timezone.utc),
            symbol="AAPL",
            raw={},
        )
    ]
    assert classify_news_side(items, within_minutes=60) == "short"


def test_neutral_conflicting_news_tagging() -> None:
    items = [
        NewsItem(
            headline="Company beats earnings",
            summary="But faces lawsuit and delay",
            published_at=datetime.now(timezone.utc),
            symbol="AAPL",
            raw={},
        )
    ]
    assert classify_news_side(items, within_minutes=60) == "neutral"


def test_news_keyword_hits() -> None:
    pos, neg = news_keyword_hits("Apple beats estimates and raises guidance")
    assert "beat" in pos or "raises" in pos or "raise" in pos
    pos2, neg2 = news_keyword_hits("Microsoft misses and cuts outlook")
    assert "miss" in neg2 or "cuts" in neg2
