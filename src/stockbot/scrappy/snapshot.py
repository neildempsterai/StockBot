"""Build symbol-scoped intelligence snapshots from Scrappy notes. Deterministic scoring; no trade instructions."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from stockbot.scrappy.types import (
    CATALYST_DIRECTION_CONFLICTING,
    CATALYST_DIRECTION_NEGATIVE,
    CATALYST_DIRECTION_NEUTRAL,
    CATALYST_DIRECTION_POSITIVE,
    SCRAPPY_VERSION,
    SymbolIntelligenceSnapshot,
)

# Sentiment -> catalyst direction mapping (deterministic)
SENTIMENT_TO_DIRECTION = {
    "bullish": CATALYST_DIRECTION_POSITIVE,
    "positive": CATALYST_DIRECTION_POSITIVE,
    "bearish": CATALYST_DIRECTION_NEGATIVE,
    "negative": CATALYST_DIRECTION_NEGATIVE,
    "neutral": CATALYST_DIRECTION_NEUTRAL,
    "mixed": CATALYST_DIRECTION_CONFLICTING,
    "conflicting": CATALYST_DIRECTION_CONFLICTING,
}

# Default when evidence is sparse
DEFAULT_DIRECTION = CATALYST_DIRECTION_NEUTRAL
DEFAULT_STRENGTH = 0
STALE_MINUTES = 120  # snapshot older than this -> stale_flag True
CONFLICT_THRESHOLD = 2  # if both positive and negative notes above this -> conflicting


def build_snapshot_from_notes(
    symbol: str,
    notes: list[Any],
    scrappy_run_id: str | None = None,
    snapshot_ts: datetime | None = None,
    *,
    stale_minutes: int = STALE_MINUTES,
) -> SymbolIntelligenceSnapshot:
    """
    Build a single symbol-scoped snapshot from market_intel_notes.
    Deterministic: aggregate sentiment, set stale/conflict flags, preserve evidence refs.
    Safe default when notes is empty.
    """
    ts = snapshot_ts or datetime.now(UTC)
    if not notes:
        return SymbolIntelligenceSnapshot(
            snapshot_id=None,
            symbol=symbol,
            snapshot_ts=ts,
            freshness_minutes=0,
            catalyst_direction=DEFAULT_DIRECTION,
            catalyst_strength=DEFAULT_STRENGTH,
            sentiment_label="neutral",
            evidence_count=0,
            source_count=0,
            source_domains=[],
            thesis_tags=[],
            headline_set=[],
            stale_flag=True,
            conflict_flag=False,
            raw_evidence_refs=[],
            scrappy_run_id=scrappy_run_id,
            scrappy_version=SCRAPPY_VERSION,
        )

    directions: list[str] = []
    headlines: list[str] = []
    domains: set[str] = set()
    tags: set[str] = set()
    evidence_refs: list[dict[str, Any]] = []
    oldest_ts: datetime | None = None

    for n in notes:
        sent = (getattr(n, "sentiment_label", None) or getattr(n, "sentiment_label", "") or "").strip().lower()
        direction = SENTIMENT_TO_DIRECTION.get(sent, CATALYST_DIRECTION_NEUTRAL)
        directions.append(direction)
        if getattr(n, "title", None):
            headlines.append(str(n.title)[:256])
        if getattr(n, "source_name", None):
            domains.add(str(n.source_name))
        if getattr(n, "catalyst_type", None):
            tags.add(str(n.catalyst_type))
        if getattr(n, "source_url", None):
            evidence_refs.append({
                "source_url": getattr(n, "source_url", ""),
                "source_name": getattr(n, "source_name", ""),
                "title": getattr(n, "title", ""),
                "sentiment_label": getattr(n, "sentiment_label", ""),
            })
        created = getattr(n, "created_at", None)
        if created and (oldest_ts is None or created < oldest_ts):
            oldest_ts = created

    pos_count = sum(1 for d in directions if d == CATALYST_DIRECTION_POSITIVE)
    neg_count = sum(1 for d in directions if d == CATALYST_DIRECTION_NEGATIVE)
    neu_count = sum(1 for d in directions if d == CATALYST_DIRECTION_NEUTRAL)

    if pos_count >= CONFLICT_THRESHOLD and neg_count >= CONFLICT_THRESHOLD:
        catalyst_direction = CATALYST_DIRECTION_CONFLICTING
        conflict_flag = True
    elif pos_count > neg_count and pos_count > neu_count:
        catalyst_direction = CATALYST_DIRECTION_POSITIVE
        conflict_flag = False
    elif neg_count > pos_count and neg_count > neu_count:
        catalyst_direction = CATALYST_DIRECTION_NEGATIVE
        conflict_flag = False
    elif neu_count >= pos_count and neu_count >= neg_count:
        catalyst_direction = CATALYST_DIRECTION_NEUTRAL
        conflict_flag = False
    else:
        catalyst_direction = DEFAULT_DIRECTION
        conflict_flag = False

    # Strength 0..100 from evidence count and imbalance
    total = len(notes)
    imbalance = abs(pos_count - neg_count)
    catalyst_strength = min(100, (total * 5) + (imbalance * 10))

    if oldest_ts:
        delta = ts - oldest_ts
        freshness_minutes = int(delta.total_seconds() / 60)
    else:
        freshness_minutes = 0
    stale_flag = freshness_minutes > stale_minutes

    sentiment_label = "neutral"
    if catalyst_direction == CATALYST_DIRECTION_POSITIVE:
        sentiment_label = "positive"
    elif catalyst_direction == CATALYST_DIRECTION_NEGATIVE:
        sentiment_label = "negative"
    elif catalyst_direction == CATALYST_DIRECTION_CONFLICTING:
        sentiment_label = "mixed"

    return SymbolIntelligenceSnapshot(
        snapshot_id=None,
        symbol=symbol,
        snapshot_ts=ts,
        freshness_minutes=freshness_minutes,
        catalyst_direction=catalyst_direction,
        catalyst_strength=catalyst_strength,
        sentiment_label=sentiment_label,
        evidence_count=len(evidence_refs),
        source_count=len(domains),
        source_domains=sorted(domains),
        thesis_tags=sorted(tags),
        headline_set=headlines[:20],
        stale_flag=stale_flag,
        conflict_flag=conflict_flag,
        raw_evidence_refs=evidence_refs,
        scrappy_run_id=scrappy_run_id,
        scrappy_version=SCRAPPY_VERSION,
    )
