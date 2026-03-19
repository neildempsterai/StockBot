"""Persistence for AI referee assessments."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from stockbot.ai_referee.types import RefereeAssessment
from stockbot.db.models import AiRefereeAssessment, Signal, ShadowTrade


async def insert_assessment(session: AsyncSession, assessment: RefereeAssessment) -> int:
    """Persist RefereeAssessment; return ai_referee_assessments.id."""
    row = AiRefereeAssessment(
        assessment_id=assessment.assessment_id,
        assessment_ts=assessment.assessment_ts,
        symbol=assessment.symbol,
        strategy_id=assessment.strategy_id,
        strategy_version=assessment.strategy_version,
        scrappy_snapshot_id=assessment.scrappy_snapshot_id,
        scrappy_run_id=assessment.scrappy_run_id,
        model_name=assessment.model_name,
        referee_version=assessment.referee_version,
        setup_quality_score=assessment.setup_quality_score,
        catalyst_strength=assessment.catalyst_strength,
        regime_label=assessment.regime_label,
        evidence_sufficiency=assessment.evidence_sufficiency,
        contradiction_flag=assessment.contradiction_flag,
        stale_flag=assessment.stale_flag,
        decision_class=assessment.decision_class,
        reason_codes_json=assessment.reason_codes,
        plain_english_rationale=assessment.plain_english_rationale,
        input_snapshot_json=None,
        raw_response_json=assessment.raw_response_json,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row.id


async def get_assessment_by_id(session: AsyncSession, assessment_id: str) -> AiRefereeAssessment | None:
    """Get row by assessment_id (UUID string)."""
    r = await session.execute(
        select(AiRefereeAssessment).where(AiRefereeAssessment.assessment_id == assessment_id).limit(1)
    )
    return r.scalars().first()


async def get_assessment_row_by_pk(session: AsyncSession, pk: int) -> AiRefereeAssessment | None:
    """Get row by primary key id."""
    r = await session.execute(select(AiRefereeAssessment).where(AiRefereeAssessment.id == pk).limit(1))
    return r.scalars().first()


async def get_latest_assessment_for_symbol(
    session: AsyncSession,
    symbol: str,
    strategy_id: str | None = None,
) -> AiRefereeAssessment | None:
    """Latest assessment for symbol, optionally filtered by strategy_id."""
    q = (
        select(AiRefereeAssessment)
        .where(AiRefereeAssessment.symbol == symbol)
        .order_by(AiRefereeAssessment.assessment_ts.desc())
        .limit(1)
    )
    if strategy_id:
        q = q.where(AiRefereeAssessment.strategy_id == strategy_id)
    r = await session.execute(q)
    return r.scalars().first()


async def list_recent_assessments(
    session: AsyncSession,
    symbol: str | None = None,
    limit: int = 50,
) -> list[AiRefereeAssessment]:
    """Recent assessments, optionally by symbol."""
    q = select(AiRefereeAssessment).order_by(AiRefereeAssessment.assessment_ts.desc()).limit(limit)
    if symbol:
        q = q.where(AiRefereeAssessment.symbol == symbol)
    r = await session.execute(q)
    return list(r.scalars().all())


async def aggregate_decision_counts(session: AsyncSession) -> dict[str, int]:
    """Count assessments by decision_class."""
    r = await session.execute(
        select(AiRefereeAssessment.decision_class, func.count(AiRefereeAssessment.id)).group_by(
            AiRefereeAssessment.decision_class
        )
    )
    return {row[0]: row[1] for row in r.all()}


async def aggregate_assisted_vs_unassisted_metrics(
    session: AsyncSession,
) -> dict[str, Any]:
    """Signals/trades with vs without ai_referee_assessment_id."""
    q_sig_with = select(func.count(Signal.id)).where(Signal.ai_referee_assessment_id.isnot(None))
    q_sig_without = select(func.count(Signal.id)).where(Signal.ai_referee_assessment_id.is_(None))
    sig_with = (await session.execute(q_sig_with)).scalar() or 0
    sig_without = (await session.execute(q_sig_without)).scalar() or 0
    return {
        "signals_with_referee": sig_with,
        "signals_without_referee": sig_without,
        "signals_total": sig_with + sig_without,
    }
