"""Market-intel note schema: catalyst taxonomy, sentiment labels, impact horizon."""
from __future__ import annotations

CATALYST_TYPES = (
    "earnings",
    "guidance",
    "sec_filing",
    "insider_activity",
    "analyst_upgrade",
    "analyst_downgrade",
    "mna",
    "product_launch",
    "partnership",
    "litigation",
    "regulation",
    "macro_rates",
    "macro_inflation",
    "macro_labor",
    "commodity_shock",
    "geopolitics",
    "short_report",
    "buyback",
    "dividend",
    "management_change",
    "unusual_volume_news_linked",
)

SENTIMENT_LABELS = ("bullish", "bearish", "neutral", "mixed")

IMPACT_HORIZON = ("immediate", "intraday", "swing", "background")


def is_valid_catalyst_type(c: str) -> bool:
    return c in CATALYST_TYPES


def is_valid_sentiment_label(s: str) -> bool:
    return s in SENTIMENT_LABELS


def is_valid_impact_horizon(h: str) -> bool:
    return h in IMPACT_HORIZON
