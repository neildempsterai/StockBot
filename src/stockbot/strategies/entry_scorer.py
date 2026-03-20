"""
Entry quality scoring system.
Scores each signal 0-100 based on technical, volume, news, spread, regime, and trend factors.
Score modulates position size and gates marginal setups.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class EntryScoreComponents:
    """Breakdown of entry quality score."""
    breakout_strength: float = 0.0     # 0-100: how far past breakout level vs ATR
    volume_confirmation: float = 0.0   # 0-100: RVol on entry bar
    news_catalyst_quality: float = 0.0 # 0-100: catalyst type, strength, freshness
    spread_quality: float = 0.0        # 0-100: tightness vs ATR
    regime_alignment: float = 0.0      # 0-100: trade direction vs regime
    trend_alignment: float = 0.0       # 0-100: trade direction vs 5m EMA cross
    flow_imbalance: float = 0.0        # 0-100: bid/ask size imbalance

    WEIGHTS = {
        "breakout_strength": 0.25,
        "volume_confirmation": 0.20,
        "news_catalyst_quality": 0.15,
        "spread_quality": 0.10,
        "regime_alignment": 0.10,
        "trend_alignment": 0.10,
        "flow_imbalance": 0.10,
    }

    @property
    def total_score(self) -> int:
        raw = (
            self.breakout_strength * self.WEIGHTS["breakout_strength"]
            + self.volume_confirmation * self.WEIGHTS["volume_confirmation"]
            + self.news_catalyst_quality * self.WEIGHTS["news_catalyst_quality"]
            + self.spread_quality * self.WEIGHTS["spread_quality"]
            + self.regime_alignment * self.WEIGHTS["regime_alignment"]
            + self.trend_alignment * self.WEIGHTS["trend_alignment"]
            + self.flow_imbalance * self.WEIGHTS["flow_imbalance"]
        )
        return max(0, min(100, int(raw)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "breakout_strength": round(self.breakout_strength, 1),
            "volume_confirmation": round(self.volume_confirmation, 1),
            "news_catalyst_quality": round(self.news_catalyst_quality, 1),
            "spread_quality": round(self.spread_quality, 1),
            "regime_alignment": round(self.regime_alignment, 1),
            "trend_alignment": round(self.trend_alignment, 1),
            "flow_imbalance": round(self.flow_imbalance, 1),
            "total_score": self.total_score,
        }


def size_multiplier_from_score(score: int) -> Decimal:
    """Map entry quality score to position size multiplier.

    80+: full size (1.0x)
    60-79: 75% size
    40-59: 50% size
    <40: rejected (should not reach sizing)
    """
    if score >= 80:
        return Decimal("1.0")
    if score >= 60:
        return Decimal("0.75")
    if score >= 40:
        return Decimal("0.5")
    return Decimal("0.25")


CATALYST_TYPE_SCORES: dict[str, int] = {
    "earnings": 20,
    "guidance": 15,
    "fda_approval": 20,
    "fda approved": 20,
    "mna": 15,
    "analyst_upgrade": 10,
    "analyst_downgrade": 10,
    "product_launch": 10,
    "partnership": 8,
    "buyback": 5,
    "dividend": 3,
    "management_change": 5,
    "secondary_offering": -15,
    "share_offering": -15,
    "litigation": -10,
    "regulation": -10,
    "short_report": -10,
    "sec_filing": 3,
    "insider_activity": 5,
    "unusual_volume_news_linked": 5,
}


def compute_entry_score(
    *,
    side: str,
    breakout_distance_vs_atr: Decimal | None,
    entry_bar_rvol: Decimal | None,
    news_side: str,
    news_keyword_count: int,
    catalyst_type: str | None,
    catalyst_strength: int | None,
    spread_bps: int,
    atr_bps: int | None,
    regime_label: str,
    trend_5m: str,
    bid_ask_imbalance: Decimal | None,
) -> EntryScoreComponents:
    """Compute entry quality score from all available signal context."""
    comp = EntryScoreComponents()

    if breakout_distance_vs_atr is not None and breakout_distance_vs_atr > 0:
        comp.breakout_strength = min(100.0, float(breakout_distance_vs_atr * 100))
    elif breakout_distance_vs_atr is not None:
        comp.breakout_strength = max(0.0, 50.0 + float(breakout_distance_vs_atr * 50))
    else:
        comp.breakout_strength = 50.0

    if entry_bar_rvol is not None:
        comp.volume_confirmation = min(100.0, float(entry_bar_rvol) * 40.0)
    else:
        comp.volume_confirmation = 50.0

    news_base = 50.0
    if side == "buy" and news_side == "long":
        news_base = 70.0 + min(30.0, news_keyword_count * 5.0)
    elif side == "sell" and news_side == "short":
        news_base = 70.0 + min(30.0, news_keyword_count * 5.0)
    elif news_side == "neutral":
        news_base = 40.0
    elif (side == "buy" and news_side == "short") or (side == "sell" and news_side == "long"):
        news_base = 10.0
    if catalyst_type and catalyst_type in CATALYST_TYPE_SCORES:
        news_base = max(0.0, min(100.0, news_base + CATALYST_TYPE_SCORES[catalyst_type]))
    if catalyst_strength is not None:
        news_base = max(0.0, min(100.0, news_base + catalyst_strength * 2))
    comp.news_catalyst_quality = news_base

    if atr_bps and atr_bps > 0:
        spread_vs_atr = spread_bps / atr_bps
        comp.spread_quality = max(0.0, min(100.0, (1.0 - spread_vs_atr * 2) * 100))
    else:
        comp.spread_quality = max(0.0, min(100.0, (1.0 - spread_bps / 50.0) * 100))

    if side == "buy":
        if regime_label == "trending_up":
            comp.regime_alignment = 85.0
        elif regime_label == "trending_down":
            comp.regime_alignment = 25.0
        elif regime_label == "choppy":
            comp.regime_alignment = 40.0
        else:
            comp.regime_alignment = 50.0
    else:
        if regime_label == "trending_down":
            comp.regime_alignment = 85.0
        elif regime_label == "trending_up":
            comp.regime_alignment = 25.0
        elif regime_label == "choppy":
            comp.regime_alignment = 40.0
        else:
            comp.regime_alignment = 50.0

    if side == "buy":
        if trend_5m == "up":
            comp.trend_alignment = 80.0
        elif trend_5m == "down":
            comp.trend_alignment = 20.0
        else:
            comp.trend_alignment = 50.0
    else:
        if trend_5m == "down":
            comp.trend_alignment = 80.0
        elif trend_5m == "up":
            comp.trend_alignment = 20.0
        else:
            comp.trend_alignment = 50.0

    if bid_ask_imbalance is not None:
        if side == "buy":
            comp.flow_imbalance = max(0.0, min(100.0, 50.0 + float(bid_ask_imbalance) * 50.0))
        else:
            comp.flow_imbalance = max(0.0, min(100.0, 50.0 - float(bid_ask_imbalance) * 50.0))
    else:
        comp.flow_imbalance = 50.0

    return comp
