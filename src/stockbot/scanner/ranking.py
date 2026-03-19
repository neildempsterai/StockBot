"""Ranking engine: deterministic opportunity score and filter reasons."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from stockbot.alpaca.types import Snapshot
from stockbot.scanner.types import ComponentScores, ScannerCandidate


def _spread_bps(snap: Snapshot | None) -> int | None:
    if not snap or not snap.latest_quote:
        return None
    q = snap.latest_quote
    mid = (float(q.bid_price) + float(q.ask_price)) / 2
    if mid <= 0:
        return None
    spread = float(q.ask_price) - float(q.bid_price)
    return int(round(spread / mid * 10000))


def _price(snap: Snapshot | None) -> Decimal | None:
    if not snap:
        return None
    if snap.latest_trade:
        return snap.latest_trade.price
    if snap.latest_quote:
        return (snap.latest_quote.bid_price + snap.latest_quote.ask_price) / 2
    if snap.daily_bar:
        return snap.daily_bar.close
    return None


def _gap_pct(price: Decimal | None, prev_close: Decimal | None) -> float | None:
    if price is None or prev_close is None or prev_close == 0:
        return None
    return float((price - prev_close) / prev_close * 100)


def rank_candidate(
    symbol: str,
    snapshot: Snapshot | None,
    *,
    prev_close: Decimal | None = None,
    dollar_volume_1m: float | None = None,
    rvol_5m: float | None = None,
    vwap_distance_pct: float | None = None,
    news_count: int = 0,
    scrappy_present: bool = False,
    scrappy_catalyst_direction: str | None = None,
    # Config thresholds
    min_price: float = 5.0,
    max_price: float = 2000.0,
    min_dollar_volume_1m: float = 1_000_000.0,
    min_rvol_5m: float = 0.3,
    max_spread_bps: int = 100,
    min_gap_pct: float = -10.0,
    require_news: bool = False,
    require_scrappy: bool = False,
) -> ScannerCandidate:
    """
    Compute deterministic opportunity score and filter status.
    Returns ScannerCandidate with total_score, component_scores, reason_codes, filter_reasons, candidate_status.
    """
    price = _price(snapshot)
    spread_bps = _spread_bps(snapshot)
    gap_pct = _gap_pct(price, prev_close) if price and prev_close else None

    filter_reasons: list[str] = []
    # Hard filters
    if price is None:
        filter_reasons.append("no_price")
    else:
        p = float(price)
        if p < min_price:
            filter_reasons.append("below_min_price")
        if p > max_price:
            filter_reasons.append("above_max_price")
    if dollar_volume_1m is not None and dollar_volume_1m < min_dollar_volume_1m:
        filter_reasons.append("low_dollar_volume")
    if rvol_5m is not None and rvol_5m < min_rvol_5m:
        filter_reasons.append("low_rvol")
    if spread_bps is not None and spread_bps > max_spread_bps:
        filter_reasons.append("wide_spread")
    if gap_pct is not None and gap_pct < min_gap_pct:
        filter_reasons.append("gap_below_min")
    if require_news and news_count == 0:
        filter_reasons.append("no_news")
    if require_scrappy and not scrappy_present:
        filter_reasons.append("no_scrappy")

    if filter_reasons:
        return ScannerCandidate(
            symbol=symbol,
            total_score=0.0,
            component_scores=ComponentScores(),
            reason_codes=[],
            candidate_status="filtered_out",
            filter_reasons=filter_reasons,
            price=price,
            gap_pct=gap_pct,
            spread_bps=spread_bps,
            dollar_volume_1m=dollar_volume_1m,
            rvol_5m=rvol_5m,
            vwap_distance_pct=vwap_distance_pct,
            news_count=news_count,
            scrappy_present=scrappy_present,
            scrappy_catalyst_direction=scrappy_catalyst_direction,
            raw_snapshot_json=_snapshot_to_json(snapshot) if snapshot else None,
        )

    # Component scores (0–1 style; higher = better opportunity)
    comp = ComponentScores()
    reason_codes: list[str] = []

    if price is not None:
        p = float(price)
        if min_price <= p <= max_price:
            comp.price_score = 1.0 - min(1.0, (p - min_price) / (max_price - min_price)) * 0.5
            reason_codes.append("price_ok")
    if gap_pct is not None:
        if gap_pct > 0:
            comp.gap_score = min(1.0, gap_pct / 5.0)
            reason_codes.append("gap_up")
        else:
            comp.gap_score = max(0.0, 1.0 + gap_pct / 10.0)
    if spread_bps is not None:
        comp.spread_score = max(0.0, 1.0 - spread_bps / max_spread_bps)
        reason_codes.append("spread_ok")
    if dollar_volume_1m is not None:
        comp.volume_score = min(1.0, dollar_volume_1m / (min_dollar_volume_1m * 10))
        reason_codes.append("volume_ok")
    if rvol_5m is not None:
        comp.rvol_score = min(1.0, rvol_5m / 2.0)
        reason_codes.append("rvol_ok")
    if vwap_distance_pct is not None:
        comp.vwap_distance_score = max(0.0, 1.0 - abs(vwap_distance_pct) / 2.0)
    if news_count > 0:
        comp.news_score = min(1.0, news_count / 5.0)
        reason_codes.append("has_news")
    if scrappy_present:
        comp.scrappy_score = 0.8
        if scrappy_catalyst_direction in ("positive", "negative"):
            comp.scrappy_score = 1.0
        reason_codes.append("scrappy_ok")

    total = (
        comp.price_score * 0.1
        + comp.gap_score * 0.2
        + comp.spread_score * 0.15
        + comp.volume_score * 0.15
        + comp.rvol_score * 0.15
        + comp.vwap_distance_score * 0.1
        + comp.news_score * 0.05
        + comp.scrappy_score * 0.1
    )

    return ScannerCandidate(
        symbol=symbol,
        total_score=round(total, 4),
        component_scores=comp,
        reason_codes=reason_codes,
        candidate_status="top_candidate",
        filter_reasons=[],
        price=price,
        gap_pct=gap_pct,
        spread_bps=spread_bps,
        dollar_volume_1m=dollar_volume_1m,
        rvol_5m=rvol_5m,
        vwap_distance_pct=vwap_distance_pct,
        news_count=news_count,
        scrappy_present=scrappy_present,
        scrappy_catalyst_direction=scrappy_catalyst_direction,
        raw_snapshot_json=_snapshot_to_json(snapshot) if snapshot else None,
    )


def _snapshot_to_json(snap: Snapshot | None) -> dict[str, Any] | None:
    if not snap:
        return None
    out: dict[str, Any] = {"symbol": snap.symbol, "feed": snap.feed}
    if snap.latest_trade:
        out["latest_trade"] = {"p": float(snap.latest_trade.price), "s": float(snap.latest_trade.size)}
    if snap.latest_quote:
        q = snap.latest_quote
        out["latest_quote"] = {"bp": float(q.bid_price), "ap": float(q.ask_price)}
    if snap.daily_bar:
        b = snap.daily_bar
        out["daily_bar"] = {"o": float(b.open), "h": float(b.high), "l": float(b.low), "c": float(b.close), "v": b.volume}
    if snap.prev_daily_bar:
        b = snap.prev_daily_bar
        out["prev_daily_bar"] = {"o": float(b.open), "h": float(b.high), "l": float(b.low), "c": float(b.close), "v": b.volume}
    return out


def select_top_candidates(
    candidates: list[ScannerCandidate],
    top_n: int,
) -> list[ScannerCandidate]:
    """Sort by total_score descending and assign rank; return top_n with status top_candidate."""
    scored = [c for c in candidates if c.candidate_status == "top_candidate"]
    scored.sort(key=lambda x: (-x.total_score, x.symbol))
    for i, c in enumerate(scored[:top_n], start=1):
        c.rank = i
    return scored[:top_n]
