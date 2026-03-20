"""Tests for entry quality scoring system."""
from decimal import Decimal
from stockbot.strategies.entry_scorer import compute_entry_score, size_multiplier_from_score, EntryScoreComponents


class TestEntryScoreComponents:
    def test_total_score_bounds(self):
        c = EntryScoreComponents()
        assert c.total_score >= 0
        assert c.total_score <= 100

    def test_all_max(self):
        c = EntryScoreComponents(
            breakout_strength=100, volume_confirmation=100,
            news_catalyst_quality=100, spread_quality=100,
            regime_alignment=100, trend_alignment=100,
            flow_imbalance=100,
        )
        assert c.total_score == 100

    def test_all_zero(self):
        c = EntryScoreComponents()
        assert c.total_score == 0

    def test_to_dict(self):
        c = EntryScoreComponents(breakout_strength=50, volume_confirmation=60)
        d = c.to_dict()
        assert "total_score" in d
        assert "breakout_strength" in d
        assert d["breakout_strength"] == 50.0


class TestSizeMultiplier:
    def test_high_score_full_size(self):
        assert size_multiplier_from_score(80) == Decimal("1.0")
        assert size_multiplier_from_score(95) == Decimal("1.0")

    def test_medium_score_reduced(self):
        assert size_multiplier_from_score(65) == Decimal("0.75")

    def test_low_score_half(self):
        assert size_multiplier_from_score(45) == Decimal("0.5")

    def test_very_low_quarter(self):
        assert size_multiplier_from_score(20) == Decimal("0.25")


class TestComputeEntryScore:
    def test_strong_long_setup(self):
        comp = compute_entry_score(
            side="buy",
            breakout_distance_vs_atr=Decimal("0.5"),
            entry_bar_rvol=Decimal("2.5"),
            news_side="long",
            news_keyword_count=3,
            catalyst_type=None,
            catalyst_strength=None,
            spread_bps=5,
            atr_bps=200,
            regime_label="trending_up",
            trend_5m="up",
            bid_ask_imbalance=Decimal("0.3"),
        )
        assert comp.total_score >= 60

    def test_conflicting_news_penalized(self):
        comp = compute_entry_score(
            side="buy",
            breakout_distance_vs_atr=Decimal("0.3"),
            entry_bar_rvol=Decimal("1.5"),
            news_side="short",
            news_keyword_count=2,
            catalyst_type=None,
            catalyst_strength=None,
            spread_bps=10,
            atr_bps=200,
            regime_label="trending_up",
            trend_5m="up",
            bid_ask_imbalance=None,
        )
        assert comp.news_catalyst_quality <= 20

    def test_wide_spread_penalized(self):
        comp = compute_entry_score(
            side="buy",
            breakout_distance_vs_atr=None,
            entry_bar_rvol=None,
            news_side="neutral",
            news_keyword_count=0,
            catalyst_type=None,
            catalyst_strength=None,
            spread_bps=40,
            atr_bps=100,
            regime_label="unknown",
            trend_5m="flat",
            bid_ask_imbalance=None,
        )
        assert comp.spread_quality < 30

    def test_short_regime_alignment(self):
        comp = compute_entry_score(
            side="sell",
            breakout_distance_vs_atr=None,
            entry_bar_rvol=None,
            news_side="short",
            news_keyword_count=1,
            catalyst_type=None,
            catalyst_strength=None,
            spread_bps=10,
            atr_bps=None,
            regime_label="trending_down",
            trend_5m="down",
            bid_ask_imbalance=Decimal("-0.4"),
        )
        assert comp.regime_alignment >= 80
        assert comp.trend_alignment >= 75
