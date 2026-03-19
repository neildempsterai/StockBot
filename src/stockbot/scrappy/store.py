"""Scrappy persistence: scrappy_urls, scrappy_runs, market_intel_notes, symbol_intelligence_snapshots."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stockbot.scrappy.types import SymbolIntelligenceSnapshot
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from stockbot.db.models import (
    MarketIntelNote,
    ScrappyGateRejection,
    ScrappyRun,
    ScrappySourceHealth,
    ScrappyUrl,
    WatchlistSymbol,
)
from stockbot.db.models import (
    SymbolIntelligenceSnapshot as SymbolIntelligenceSnapshotRow,
)


def _now_utc() -> datetime:
    return datetime.now(UTC)


async def upsert_scrappy_url(
    session: AsyncSession,
    url_hash: str,
    normalized_url: str,
    source_name: str,
    *,
    relevant: bool | None = None,
    last_drop_reason: str | None = None,
    symbol_tags: list[str] | None = None,
    theme_tags: list[str] | None = None,
) -> None:
    """Insert or update scrappy_urls. last_seen_at updated on conflict."""
    stmt = insert(ScrappyUrl).values(
        url_hash=url_hash,
        normalized_url=normalized_url,
        source_name=source_name,
        first_seen_at=_now_utc(),
        last_seen_at=_now_utc(),
        relevant=relevant,
        last_drop_reason=last_drop_reason,
        symbol_tags=symbol_tags,
        theme_tags=theme_tags,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["url_hash"],
        set_={
            ScrappyUrl.last_seen_at: stmt.excluded.last_seen_at,
        },
    )
    await session.execute(stmt)
    await session.commit()


async def get_url_seen(session: AsyncSession, url: str, url_hash: str) -> bool:
    """True if url_hash exists in scrappy_urls."""
    from stockbot.scrappy.dedup import url_hash as hash_fn
    h = url_hash or hash_fn(url)
    r = await session.execute(select(ScrappyUrl).where(ScrappyUrl.url_hash == h).limit(1))
    return r.scalars().first() is not None


async def get_seen_url_hashes(session: AsyncSession, url_hashes: list[str]) -> set[str]:
    """Return set of url_hashes that exist in scrappy_urls."""
    if not url_hashes:
        return set()
    r = await session.execute(
        select(ScrappyUrl.url_hash).where(ScrappyUrl.url_hash.in_(url_hashes))
    )
    return set(r.scalars().all())


async def create_scrappy_run(
    session: AsyncSession,
    run_type: str,
    *,
    candidate_url_count: int = 0,
    post_dedup_count: int = 0,
    notes_created: int = 0,
    policy_blocked_count: int = 0,
    metadata_only_count: int = 0,
    open_text_count: int = 0,
    notes_attempted_count: int = 0,
    notes_rejected_count: int = 0,
    drop_reason_counts: dict | None = None,
    model_provider: str | None = None,
    selected_model: str | None = None,
    actual_model_used: str | None = None,
    selection_reason: str | None = None,
    outcome_code: str | None = None,
    run_scope: dict | None = None,
    errors: str | None = None,
) -> str:
    """Create scrappy_runs row; return run_id."""
    run_id = str(uuid4())
    row = ScrappyRun(
        run_id=run_id,
        run_type=run_type,
        started_at=_now_utc(),
        candidate_url_count=candidate_url_count,
        post_dedup_count=post_dedup_count,
        notes_created=notes_created,
        policy_blocked_count=policy_blocked_count,
        metadata_only_count=metadata_only_count,
        open_text_count=open_text_count,
        notes_attempted_count=notes_attempted_count,
        notes_rejected_count=notes_rejected_count,
        drop_reason_counts=drop_reason_counts,
        model_provider=model_provider,
        selected_model=selected_model,
        actual_model_used=actual_model_used,
        selection_reason=selection_reason,
        outcome_code=outcome_code,
        run_scope=run_scope,
        errors=errors,
    )
    session.add(row)
    await session.commit()
    return run_id


async def finish_scrappy_run(
    session: AsyncSession,
    run_id: str,
    outcome_code: str,
    *,
    post_dedup_count: int | None = None,
    notes_created: int | None = None,
    policy_blocked_count: int | None = None,
    metadata_only_count: int | None = None,
    open_text_count: int | None = None,
    notes_attempted_count: int | None = None,
    notes_rejected_count: int | None = None,
    errors: str | None = None,
) -> None:
    """Set finished_at, outcome_code, and optional counters/errors for run."""
    r = await session.execute(select(ScrappyRun).where(ScrappyRun.run_id == run_id).limit(1))
    row = r.scalars().first()
    if row:
        row.finished_at = _now_utc()
        row.outcome_code = outcome_code
        if post_dedup_count is not None:
            row.post_dedup_count = post_dedup_count
        if notes_created is not None:
            row.notes_created = notes_created
        if policy_blocked_count is not None:
            row.policy_blocked_count = policy_blocked_count
        if metadata_only_count is not None:
            row.metadata_only_count = metadata_only_count
        if open_text_count is not None:
            row.open_text_count = open_text_count
        if notes_attempted_count is not None:
            row.notes_attempted_count = notes_attempted_count
        if notes_rejected_count is not None:
            row.notes_rejected_count = notes_rejected_count
        if errors is not None:
            row.errors = errors
        await session.commit()


async def get_note_by_dedup_hash(session: AsyncSession, dedup_hash: str) -> MarketIntelNote | None:
    """Return existing note by dedup_hash if any."""
    r = await session.execute(
        select(MarketIntelNote).where(MarketIntelNote.dedup_hash == dedup_hash).limit(1)
    )
    return r.scalars().first()


async def insert_market_intel_note(
    session: AsyncSession,
    *,
    note_id: str | None = None,
    source_name: str,
    source_url: str,
    published_at: datetime | None = None,
    title: str | None = None,
    summary: str | None = None,
    evidence_snippets: list[str] | None = None,
    detected_symbols: list[str] | None = None,
    primary_symbol: str | None = None,
    sector_tags: list[str] | None = None,
    theme_tags: list[str] | None = None,
    catalyst_type: str | None = None,
    sentiment_label: str | None = None,
    sentiment_score: Decimal | float | None = None,
    confidence: Decimal | float | None = None,
    expires_at: datetime | None = None,
    raw_metadata: dict | None = None,
    scrappy_run_id: str | None = None,
    content_mode: str | None = None,
    dedup_hash: str | None = None,
    why_this_matters: str | None = None,
    impact_horizon: str | None = None,
) -> str:
    """Insert market_intel_note. Idempotent by dedup_hash: if present and exists, return existing note_id."""
    if dedup_hash:
        existing = await get_note_by_dedup_hash(session, dedup_hash)
        if existing:
            return existing.note_id
    nid = note_id or str(uuid4())
    score = Decimal(str(sentiment_score)) if sentiment_score is not None else None
    conf = Decimal(str(confidence)) if confidence is not None else None
    row = MarketIntelNote(
        note_id=nid,
        source_name=source_name,
        source_url=source_url,
        published_at=published_at,
        title=title,
        summary=summary,
        evidence_snippets=evidence_snippets,
        detected_symbols=detected_symbols,
        primary_symbol=primary_symbol,
        sector_tags=sector_tags,
        theme_tags=theme_tags,
        catalyst_type=catalyst_type,
        sentiment_label=sentiment_label,
        sentiment_score=score,
        confidence=conf,
        expires_at=expires_at,
        raw_metadata=raw_metadata,
        scrappy_run_id=scrappy_run_id,
        content_mode=content_mode,
        dedup_hash=dedup_hash,
        why_this_matters=why_this_matters,
        impact_horizon=impact_horizon,
    )
    session.add(row)
    await session.commit()
    return nid


async def get_recent_notes(
    session: AsyncSession,
    limit: int = 50,
    symbol: str | None = None,
    run_id: str | None = None,
    catalyst_type: str | None = None,
    sentiment_label: str | None = None,
    content_mode: str | None = None,
    since: datetime | None = None,
) -> list[MarketIntelNote]:
    """Return recent market_intel_notes with optional filters."""
    q = select(MarketIntelNote).order_by(MarketIntelNote.created_at.desc()).limit(limit * 2)
    if symbol:
        q = q.where(MarketIntelNote.primary_symbol == symbol)
    if run_id:
        q = q.where(MarketIntelNote.scrappy_run_id == run_id)
    if catalyst_type:
        q = q.where(MarketIntelNote.catalyst_type == catalyst_type)
    if sentiment_label:
        q = q.where(MarketIntelNote.sentiment_label == sentiment_label)
    if content_mode:
        q = q.where(MarketIntelNote.content_mode == content_mode)
    if since:
        q = q.where(MarketIntelNote.created_at >= since)
    r = await session.execute(q)
    return list(r.scalars().all())[:limit]


async def get_recent_runs(
    session: AsyncSession,
    limit: int = 50,
    run_type: str | None = None,
) -> list[ScrappyRun]:
    """Return recent scrappy_runs for telemetry/audit."""
    q = select(ScrappyRun).order_by(ScrappyRun.started_at.desc()).limit(limit)
    if run_type:
        q = q.where(ScrappyRun.run_type == run_type)
    r = await session.execute(q)
    return list(r.scalars().all())


async def count_notes(session: AsyncSession) -> int:
    """Total count of market_intel_notes."""
    from sqlalchemy import func
    r = await session.execute(select(func.count(MarketIntelNote.id)))
    val = r.scalars().first()
    return int(val or 0)


# ----- Watchlist -----


async def get_watchlist_symbols(session: AsyncSession) -> list[str]:
    """Return list of symbols in watchlist (for POST /scrappy/run/watchlist)."""
    r = await session.execute(
        select(WatchlistSymbol.symbol).order_by(WatchlistSymbol.added_at.asc())
    )
    return [row for row in r.scalars().all()]


async def add_watchlist_symbol(
    session: AsyncSession,
    symbol: str,
    *,
    source: str | None = "manual",
) -> None:
    """Add symbol to watchlist; no-op if already present."""
    from sqlalchemy.dialects.postgresql import insert
    stmt = insert(WatchlistSymbol).values(
        symbol=symbol.strip().upper()[:32],
        source=source,
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=["symbol"])
    await session.execute(stmt)
    await session.commit()


# ----- Per-source health -----


async def upsert_source_health(
    session: AsyncSession,
    source_name: str,
    *,
    success: bool | None = None,
    fetch_success: bool | None = None,
    fetch_failure: bool | None = None,
    fetch_success_count_delta: int = 0,
    fetch_failure_count_delta: int = 0,
    candidate_count_delta: int = 0,
    post_dedup_count_delta: int = 0,
    notes_inserted_delta: int = 0,
    last_error_code: str | None = None,
    last_error_message: str | None = None,
) -> None:
    """
    Record source health. success = fetch_success when not otherwise specified (legacy single attempt).
    fetch_success_count_delta/fetch_failure_count_delta: per-run deltas. Note yield is separate.
    """
    r = await session.execute(
        select(ScrappySourceHealth).where(ScrappySourceHealth.source_name == source_name).limit(1)
    )
    row = r.scalars().first()
    now = _now_utc()
    if fetch_success is None and fetch_failure is None and success is not None:
        fetch_success = success
        fetch_failure = not success
    if fetch_success_count_delta == 0 and fetch_failure_count_delta == 0 and fetch_success is not None:
        if fetch_success:
            fetch_success_count_delta = 1
        if fetch_failure:
            fetch_failure_count_delta = 1
    has_activity = candidate_count_delta or post_dedup_count_delta or fetch_success_count_delta or fetch_failure_count_delta
    if row:
        row.last_attempt_at = now
        if has_activity:
            row.attempt_count = (row.attempt_count or 0) + 1
        if fetch_success_count_delta:
            row.last_success_at = now
            row.success_count = (row.success_count or 0) + fetch_success_count_delta
            row.fetch_success_count = (row.fetch_success_count or 0) + fetch_success_count_delta
        if fetch_failure_count_delta:
            row.failure_count = (row.failure_count or 0) + fetch_failure_count_delta
            row.fetch_failure_count = (row.fetch_failure_count or 0) + fetch_failure_count_delta
        if candidate_count_delta:
            row.candidate_count = (row.candidate_count or 0) + candidate_count_delta
        if post_dedup_count_delta:
            row.post_dedup_count = (row.post_dedup_count or 0) + post_dedup_count_delta
        if notes_inserted_delta:
            row.notes_inserted_count = (row.notes_inserted_count or 0) + notes_inserted_delta
        if last_error_code is not None:
            row.last_error_code = last_error_code[:64] if last_error_code else None
        if last_error_message is not None:
            row.last_error_message = (last_error_message or "")[:512]
    else:
        session.add(ScrappySourceHealth(
            source_name=source_name,
            last_attempt_at=now,
            last_success_at=now if fetch_success_count_delta else None,
            attempt_count=1 if has_activity else 0,
            success_count=fetch_success_count_delta,
            failure_count=fetch_failure_count_delta,
            fetch_success_count=fetch_success_count_delta,
            fetch_failure_count=fetch_failure_count_delta,
            candidate_count=candidate_count_delta,
            post_dedup_count=post_dedup_count_delta,
            notes_inserted_count=notes_inserted_delta,
            last_error_code=last_error_code[:64] if last_error_code else None,
            last_error_message=(last_error_message or "")[:512],
        ))
    await session.commit()


# ----- Symbol intelligence snapshots -----


async def insert_intelligence_snapshot(
    session: AsyncSession,
    symbol: str,
    snapshot_ts: datetime,
    freshness_minutes: int,
    catalyst_direction: str,
    catalyst_strength: int,
    *,
    sentiment_label: str | None = None,
    evidence_count: int = 0,
    source_count: int = 0,
    source_domains_json: list[str] | None = None,
    thesis_tags_json: list[str] | None = None,
    headline_set_json: list[str] | None = None,
    stale_flag: bool = False,
    conflict_flag: bool = False,
    raw_evidence_refs_json: list[dict] | None = None,
    scrappy_run_id: str | None = None,
    scrappy_version: str = "0.1.0",
) -> int:
    """Insert symbol_intelligence_snapshots row; return id."""
    row = SymbolIntelligenceSnapshotRow(
        symbol=symbol,
        snapshot_ts=snapshot_ts,
        freshness_minutes=freshness_minutes,
        catalyst_direction=catalyst_direction,
        catalyst_strength=catalyst_strength,
        sentiment_label=sentiment_label,
        evidence_count=evidence_count,
        source_count=source_count,
        source_domains_json=source_domains_json,
        thesis_tags_json=thesis_tags_json,
        headline_set_json=headline_set_json,
        stale_flag=stale_flag,
        conflict_flag=conflict_flag,
        raw_evidence_refs_json=raw_evidence_refs_json,
        scrappy_run_id=scrappy_run_id,
        scrappy_version=scrappy_version,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row.id


async def insert_intelligence_snapshot_from_snapshot(
    session: AsyncSession,
    snapshot: SymbolIntelligenceSnapshot,
) -> int:
    """Insert from SymbolIntelligenceSnapshot dataclass; return id."""
    return await insert_intelligence_snapshot(
        session,
        symbol=snapshot.symbol,
        snapshot_ts=snapshot.snapshot_ts,
        freshness_minutes=snapshot.freshness_minutes,
        catalyst_direction=snapshot.catalyst_direction,
        catalyst_strength=snapshot.catalyst_strength,
        sentiment_label=snapshot.sentiment_label,
        evidence_count=snapshot.evidence_count,
        source_count=snapshot.source_count,
        source_domains_json=snapshot.source_domains or None,
        thesis_tags_json=snapshot.thesis_tags or None,
        headline_set_json=snapshot.headline_set or None,
        stale_flag=snapshot.stale_flag,
        conflict_flag=snapshot.conflict_flag,
        raw_evidence_refs_json=snapshot.raw_evidence_refs or None,
        scrappy_run_id=snapshot.scrappy_run_id,
        scrappy_version=snapshot.scrappy_version,
    )


async def get_latest_snapshot_by_symbol(
    session: AsyncSession,
    symbol: str,
) -> SymbolIntelligenceSnapshotRow | None:
    """Return latest snapshot for symbol by snapshot_ts desc."""
    r = await session.execute(
        select(SymbolIntelligenceSnapshotRow)
        .where(SymbolIntelligenceSnapshotRow.symbol == symbol)
        .order_by(SymbolIntelligenceSnapshotRow.snapshot_ts.desc())
        .limit(1)
    )
    return r.scalars().first()


async def get_latest_non_stale_snapshot_by_symbol(
    session: AsyncSession,
    symbol: str,
) -> SymbolIntelligenceSnapshotRow | None:
    """Return latest non-stale snapshot for symbol."""
    r = await session.execute(
        select(SymbolIntelligenceSnapshotRow)
        .where(
            SymbolIntelligenceSnapshotRow.symbol == symbol,
            SymbolIntelligenceSnapshotRow.stale_flag.is_(False),
        )
        .order_by(SymbolIntelligenceSnapshotRow.snapshot_ts.desc())
        .limit(1)
    )
    return r.scalars().first()


async def get_recent_snapshots(
    session: AsyncSession,
    limit: int = 50,
    symbol: str | None = None,
) -> list[SymbolIntelligenceSnapshotRow]:
    """Return recent snapshots, optionally filtered by symbol."""
    q = (
        select(SymbolIntelligenceSnapshotRow)
        .order_by(SymbolIntelligenceSnapshotRow.snapshot_ts.desc())
        .limit(limit)
    )
    if symbol:
        q = q.where(SymbolIntelligenceSnapshotRow.symbol == symbol)
    r = await session.execute(q)
    return list(r.scalars().all())


async def insert_gate_rejection(
    session: AsyncSession,
    symbol: str,
    reason_code: str,
    scrappy_mode: str | None = None,
) -> None:
    """Record a Scrappy gate rejection for attribution."""
    session.add(ScrappyGateRejection(
        symbol=symbol.strip().upper()[:32],
        reason_code=reason_code.strip()[:64],
        scrappy_mode=scrappy_mode.strip().lower()[:16] if scrappy_mode else None,
    ))
    await session.commit()


async def get_gate_rejection_counts(
    session: AsyncSession, scrappy_mode: str | None = None
) -> dict[str, int]:
    """Return counts per reason_code for attribution, optionally filtered by scrappy_mode."""
    from sqlalchemy import func
    q = (
        select(ScrappyGateRejection.reason_code, func.count(ScrappyGateRejection.id))
        .group_by(ScrappyGateRejection.reason_code)
    )
    if scrappy_mode is not None:
        q = q.where(ScrappyGateRejection.scrappy_mode == scrappy_mode)
    r = await session.execute(q)
    return {row[0]: row[1] for row in r.all()}


async def get_gate_rejection_counts_by_mode(session: AsyncSession) -> dict[str, dict[str, int]]:
    """Return rejection counts per reason_code grouped by scrappy_mode for comparison."""
    from sqlalchemy import func
    r = await session.execute(
        select(
            ScrappyGateRejection.scrappy_mode,
            ScrappyGateRejection.reason_code,
            func.count(ScrappyGateRejection.id),
        )
        .group_by(ScrappyGateRejection.scrappy_mode, ScrappyGateRejection.reason_code)
    )
    out: dict[str, dict[str, int]] = {}
    for mode, reason, count in r.all():
        mode_key = mode or "unknown"
        if mode_key not in out:
            out[mode_key] = {}
        out[mode_key][reason] = count
    return out


async def get_source_health_all(session: AsyncSession) -> list[dict]:
    """Return per-source health for API."""
    r = await session.execute(
        select(ScrappySourceHealth).order_by(ScrappySourceHealth.source_name.asc())
    )
    rows = list(r.scalars().all())
    return [
        {
            "source_name": h.source_name,
            "last_attempt_at": h.last_attempt_at.isoformat() if h.last_attempt_at else None,
            "last_success_at": h.last_success_at.isoformat() if h.last_success_at else None,
            "attempt_count": h.attempt_count or 0,
            "success_count": h.success_count or 0,
            "failure_count": h.failure_count or 0,
            "fetch_success_count": getattr(h, "fetch_success_count", None) or 0,
            "fetch_failure_count": getattr(h, "fetch_failure_count", None) or 0,
            "candidate_count": getattr(h, "candidate_count", None) or 0,
            "post_dedup_count": getattr(h, "post_dedup_count", None) or 0,
            "notes_inserted_count": getattr(h, "notes_inserted_count", None) or 0,
            "last_error_code": getattr(h, "last_error_code", None),
            "last_error_message": getattr(h, "last_error_message", None),
        }
        for h in rows
    ]
