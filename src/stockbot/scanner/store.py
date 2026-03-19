"""Scanner persistence: runs, candidates, toplist snapshots."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stockbot.db.models import ScannerRun, ScannerCandidateRow, ScannerToplistSnapshot
from stockbot.scanner.types import ScannerRunResult, ScannerCandidate, ComponentScores


async def create_scanner_run(
    session: AsyncSession,
    run_id: str,
    run_ts: datetime,
    mode: str,
    universe_mode: str,
    universe_size: int,
    candidates_scored: int,
    top_candidates_count: int,
    market_session: str,
    status: str,
    notes: str | None = None,
) -> ScannerRun:
    row = ScannerRun(
        run_id=run_id,
        run_ts=run_ts,
        mode=mode,
        universe_mode=universe_mode,
        universe_size=universe_size,
        candidates_scored=candidates_scored,
        top_candidates_count=top_candidates_count,
        market_session=market_session,
        status=status,
        notes=notes,
    )
    session.add(row)
    await session.flush()
    return row


async def insert_scanner_candidates(
    session: AsyncSession,
    run_id: str,
    candidates: list[ScannerCandidate],
) -> None:
    for c in candidates:
        row = ScannerCandidateRow(
            run_id=run_id,
            symbol=c.symbol,
            rank=c.rank,
            total_score=c.total_score,
            component_scores_json=c.component_scores.to_dict() if c.component_scores else None,
            reason_codes_json=c.reason_codes,
            filter_reasons_json=c.filter_reasons,
            candidate_status=c.candidate_status,
            price=c.price,
            gap_pct=c.gap_pct,
            spread_bps=c.spread_bps,
            dollar_volume_1m=c.dollar_volume_1m,
            rvol_5m=c.rvol_5m,
            vwap_distance_pct=c.vwap_distance_pct,
            news_count=c.news_count,
            scrappy_present=c.scrappy_present,
            scrappy_catalyst_direction=c.scrappy_catalyst_direction,
            raw_snapshot_json=c.raw_snapshot_json,
        )
        session.add(row)
    await session.flush()


async def insert_toplist_snapshot(
    session: AsyncSession,
    snapshot_ts: datetime,
    symbols: list[str],
    run_id: str | None,
) -> ScannerToplistSnapshot:
    row = ScannerToplistSnapshot(
        snapshot_ts=snapshot_ts,
        symbols_json=symbols,
        run_id=run_id,
    )
    session.add(row)
    await session.flush()
    return row


async def get_latest_scanner_run(session: AsyncSession) -> ScannerRun | None:
    q = select(ScannerRun).order_by(ScannerRun.run_ts.desc()).limit(1)
    r = await session.execute(q)
    return r.scalar_one_or_none()


LIVE_MODE_EXCLUDE = "historical"


async def get_latest_live_scanner_run(session: AsyncSession) -> ScannerRun | None:
    """Latest scanner run that is not historical (live/dynamic only)."""
    q = (
        select(ScannerRun)
        .where(ScannerRun.mode != LIVE_MODE_EXCLUDE)
        .order_by(ScannerRun.run_ts.desc())
        .limit(1)
    )
    r = await session.execute(q)
    return r.scalar_one_or_none()


async def get_latest_live_toplist_snapshot(session: AsyncSession) -> ScannerToplistSnapshot | None:
    """Latest toplist snapshot whose run_id is not historical (no hist_*)."""
    from sqlalchemy import or_
    q = (
        select(ScannerToplistSnapshot)
        .where(
            or_(
                ScannerToplistSnapshot.run_id.is_(None),
                ~ScannerToplistSnapshot.run_id.like("hist_%"),
            )
        )
        .order_by(ScannerToplistSnapshot.snapshot_ts.desc())
        .limit(1)
    )
    r = await session.execute(q)
    return r.scalar_one_or_none()


async def get_scanner_run_by_id(session: AsyncSession, run_id: str) -> ScannerRun | None:
    q = select(ScannerRun).where(ScannerRun.run_id == run_id)
    r = await session.execute(q)
    return r.scalar_one_or_none()


async def get_scanner_runs(
    session: AsyncSession,
    limit: int = 50,
    status: str | None = None,
) -> list[ScannerRun]:
    q = select(ScannerRun).order_by(ScannerRun.run_ts.desc()).limit(limit)
    if status:
        q = q.where(ScannerRun.status == status)
    r = await session.execute(q)
    return list(r.scalars().all())


async def get_candidates_for_run(
    session: AsyncSession,
    run_id: str,
    *,
    status: str | None = None,
    limit: int = 500,
) -> list[ScannerCandidateRow]:
    q = select(ScannerCandidateRow).where(ScannerCandidateRow.run_id == run_id).order_by(ScannerCandidateRow.rank).limit(limit)
    if status:
        q = q.where(ScannerCandidateRow.candidate_status == status)
    r = await session.execute(q)
    return list(r.scalars().all())


async def get_latest_toplist_snapshot(session: AsyncSession) -> ScannerToplistSnapshot | None:
    q = select(ScannerToplistSnapshot).order_by(ScannerToplistSnapshot.snapshot_ts.desc()).limit(1)
    r = await session.execute(q)
    return r.scalar_one_or_none()


def _row_to_candidate(r: ScannerCandidateRow) -> dict[str, Any]:
    return {
        "run_id": r.run_id,
        "symbol": r.symbol,
        "rank": r.rank,
        "total_score": r.total_score,
        "component_scores": r.component_scores_json or {},
        "reason_codes": r.reason_codes_json or [],
        "filter_reasons": r.filter_reasons_json or [],
        "candidate_status": r.candidate_status,
        "price": float(r.price) if r.price is not None else None,
        "gap_pct": r.gap_pct,
        "spread_bps": r.spread_bps,
        "dollar_volume_1m": r.dollar_volume_1m,
        "rvol_5m": r.rvol_5m,
        "vwap_distance_pct": r.vwap_distance_pct,
        "news_count": r.news_count or 0,
        "scrappy_present": r.scrappy_present or False,
        "scrappy_catalyst_direction": r.scrappy_catalyst_direction,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _row_to_scanner_candidate(r: ScannerCandidateRow) -> ScannerCandidate:
    """Convert persisted row to ScannerCandidate for opportunity re-blend."""
    comp = r.component_scores_json or {}
    scores = ComponentScores(
        price_score=float(comp.get("price", 0)),
        gap_score=float(comp.get("gap", 0)),
        spread_score=float(comp.get("spread", 0)),
        volume_score=float(comp.get("volume", 0)),
        rvol_score=float(comp.get("rvol", 0)),
        vwap_distance_score=float(comp.get("vwap_distance", 0)),
        news_score=float(comp.get("news", 0)),
        scrappy_score=float(comp.get("scrappy", 0)),
        opening_range_score=float(comp.get("opening_range", 0)),
    )
    from decimal import Decimal
    return ScannerCandidate(
        symbol=r.symbol,
        total_score=float(r.total_score) if r.total_score is not None else 0.0,
        component_scores=scores,
        reason_codes=list(r.reason_codes_json or []),
        candidate_status=r.candidate_status or "filtered_out",
        filter_reasons=list(r.filter_reasons_json or []),
        price=Decimal(str(r.price)) if r.price is not None else None,
        gap_pct=r.gap_pct,
        spread_bps=r.spread_bps,
        dollar_volume_1m=r.dollar_volume_1m,
        rvol_5m=r.rvol_5m,
        vwap_distance_pct=r.vwap_distance_pct,
        news_count=r.news_count or 0,
        scrappy_present=r.scrappy_present or False,
        scrappy_catalyst_direction=r.scrappy_catalyst_direction,
        rank=r.rank or 0,
    )


async def get_latest_scanner_result(session: AsyncSession) -> ScannerRunResult | None:
    """Load latest scanner run and its candidates as ScannerRunResult for re-blend (e.g. manual trigger)."""
    run = await get_latest_scanner_run(session)
    if not run:
        return None
    rows = await get_candidates_for_run(session, run.run_id, status="top_candidate", limit=500)
    candidates = [_row_to_scanner_candidate(r) for r in rows]
    return ScannerRunResult(
        run_id=run.run_id,
        run_ts=run.run_ts,
        mode=run.mode or "dynamic",
        universe_mode=run.universe_mode or "liquid_us_equities",
        universe_size=run.universe_size or 0,
        candidates_scored=run.candidates_scored or 0,
        top_candidates_count=run.top_candidates_count or 0,
        market_session=run.market_session or "unknown",
        status=run.status or "completed",
        notes=run.notes,
        candidates=candidates,
    )


async def get_latest_live_scanner_result(session: AsyncSession) -> ScannerRunResult | None:
    """Load latest live (non-historical) scanner run and candidates. Use for current opportunity truth."""
    run = await get_latest_live_scanner_run(session)
    if not run:
        return None
    rows = await get_candidates_for_run(session, run.run_id, status="top_candidate", limit=500)
    candidates = [_row_to_scanner_candidate(r) for r in rows]
    return ScannerRunResult(
        run_id=run.run_id,
        run_ts=run.run_ts,
        mode=run.mode or "dynamic",
        universe_mode=run.universe_mode or "liquid_us_equities",
        universe_size=run.universe_size or 0,
        candidates_scored=run.candidates_scored or 0,
        top_candidates_count=run.top_candidates_count or 0,
        market_session=run.market_session or "unknown",
        status=run.status or "completed",
        notes=run.notes,
        candidates=candidates,
    )
