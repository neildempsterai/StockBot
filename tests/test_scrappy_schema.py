"""Tests for Scrappy note schema: catalyst taxonomy, sentiment, validation."""
from __future__ import annotations

from stockbot.scrappy.schema import (
    CATALYST_TYPES,
    SENTIMENT_LABELS,
    is_valid_catalyst_type,
    is_valid_impact_horizon,
    is_valid_sentiment_label,
)


def test_catalyst_types_include_required() -> None:
    assert "earnings" in CATALYST_TYPES
    assert "sec_filing" in CATALYST_TYPES
    assert "macro_rates" in CATALYST_TYPES


def test_sentiment_labels() -> None:
    assert set(SENTIMENT_LABELS) == {"bullish", "bearish", "neutral", "mixed"}


def test_is_valid_catalyst_type() -> None:
    assert is_valid_catalyst_type("earnings") is True
    assert is_valid_catalyst_type("sec_filing") is True
    assert is_valid_catalyst_type("unknown") is False


def test_is_valid_sentiment_label() -> None:
    assert is_valid_sentiment_label("bullish") is True
    assert is_valid_sentiment_label("neutral") is True
    assert is_valid_sentiment_label("invalid") is False


def test_is_valid_impact_horizon() -> None:
    assert is_valid_impact_horizon("immediate") is True
    assert is_valid_impact_horizon("swing") is True
    assert is_valid_impact_horizon("other") is False
