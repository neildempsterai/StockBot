"""Opportunity engine service: merge market + semantic candidates and publish to Redis."""
from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as redis

from stockbot.config import get_settings
from stockbot.market_sessions import current_session
from stockbot.opportunities.blend import blend_candidates
from stockbot.opportunities.types import OpportunityCandidate
from stockbot.scanner.types import ScannerCandidate

logger = logging.getLogger(__name__)

REDIS_KEY_SCANNER_TOP = "stockbot:scanner:top_symbols"
REDIS_KEY_SCANNER_TOP_TS = "stockbot:scanner:top_updated_at"
REDIS_KEY_SCANNER_RUN_ID = "stockbot:scanner:latest_run_id"
REDIS_TTL_TOP_SEC = 86400 * 2


async def get_latest_opportunity_run_and_candidates() -> tuple[str | None, str | None, list[dict]]:
    """Return (run_id, updated_at_iso, list of candidate dicts) for latest live opportunity run only. Excludes hist_* runs."""
    try:
        from sqlalchemy import select
        from stockbot.db.session import get_session_factory
        from stockbot.db.models import OpportunityRun, OpportunityCandidateRow
        factory = get_session_factory()
        async with factory() as session:
            r = await session.execute(
                select(OpportunityRun)
                .where(~OpportunityRun.run_id.like("hist_%"))
                .order_by(OpportunityRun.run_ts.desc())
                .limit(1)
            )
            run_row = r.scalars().first()
            if not run_row:
                return None, None, []
            cq = await session.execute(
                select(OpportunityCandidateRow)
                .where(OpportunityCandidateRow.run_id == run_row.run_id)
                .order_by(OpportunityCandidateRow.rank.asc())
                .limit(100)
            )
            rows = list(cq.scalars().all())
        candidates = [
            {
                "symbol": c.symbol,
                "rank": c.rank,
                "total_score": c.total_score,
                "market_score": c.market_score,
                "semantic_score": c.semantic_score,
                "candidate_source": c.candidate_source,
                "inclusion_reasons": c.inclusion_reasons_json or [],
                "filter_reasons": c.filter_reasons_json or [],
                "session": c.session,
                "news_count": c.news_count,
                "scrappy_present": c.scrappy_present,
            }
            for c in rows
        ]
        updated_at = run_row.run_ts.isoformat() if run_row.run_ts else None
        return run_row.run_id, updated_at, candidates
    except Exception as e:
        logger.debug("get_latest_opportunity_run_and_candidates: %s", e)
        return None, None, []


def _scanner_candidates_to_opportunity(candidates: list[ScannerCandidate]) -> list[OpportunityCandidate]:
    """Convert scanner candidates to opportunity candidates (market source)."""
    out: list[OpportunityCandidate] = []
    for c in candidates:
        comp = c.component_scores.to_dict() if hasattr(c.component_scores, "to_dict") else {}
        out.append(OpportunityCandidate(
            symbol=c.symbol,
            total_score=c.total_score,
            market_score=c.total_score,
            semantic_score=0.0,
            candidate_source="market",
            inclusion_reasons=list(c.reason_codes) if c.reason_codes else [],
            filter_reasons=list(c.filter_reasons) if c.filter_reasons else [],
            component_scores=comp,
            current_session=current_session(),
            scrappy_present=c.scrappy_present,
            news_count=c.news_count or 0,
        ))
    return out


def _semantic_score_from_news(mention_count: int, freshness_minutes: float) -> float:
    """Deterministic semantic score from news: mention density + freshness. Explainable."""
    # density: cap at 5 mentions for score contribution
    density_part = min(mention_count / 10.0, 0.35)
    # freshness: 0–1440 min (24h); newer = higher (max 0.35)
    freshness_part = max(0.0, 0.35 * (1.0 - freshness_minutes / 1440.0))
    return round(0.5 + density_part + freshness_part, 4)


async def _get_semantic_candidates() -> list[OpportunityCandidate]:
    """Symbols from recent Alpaca news, Scrappy notes, and intelligence snapshots. Deterministic scores."""
    import asyncio
    from datetime import UTC, datetime, timedelta

    out: list[OpportunityCandidate] = []
    seen: set[str] = set()
    now = datetime.now(UTC)
    since_dt = now - timedelta(hours=24)
    since_iso = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1) Alpaca news: group by symbol, freshness + mention density
    try:
        from stockbot.alpaca.client import AlpacaClient
        client = AlpacaClient()
        articles, _ = await asyncio.to_thread(
            client.get_news,
            symbols=None,
            start=since_iso,
            limit=100,
        )
        # symbol -> list of created_at (epoch or parse)
        by_symbol: dict[str, list[float]] = {}
        for a in articles or []:
            if not isinstance(a, dict):
                continue
            syms = a.get("symbols") or []
            created = a.get("created_at") or a.get("updated_at")
            ts = now.timestamp()
            if created:
                try:
                    s = str(created).replace("Z", "+00:00")
                    dt = datetime.fromisoformat(s)
                    ts = dt.timestamp()
                except Exception:
                    pass
            for sym in syms:
                if isinstance(sym, str) and sym.strip():
                    by_symbol.setdefault(sym.strip(), []).append(ts)
        for sym, timestamps in by_symbol.items():
            if sym in seen:
                continue
            seen.add(sym)
            mention_count = len(timestamps)
            newest = max(timestamps)
            freshness_minutes = (now.timestamp() - newest) / 60.0
            score = _semantic_score_from_news(mention_count, freshness_minutes)
            reasons = ["recent_alpaca_news", f"mention_density_{mention_count}"]
            out.append(OpportunityCandidate(
                symbol=sym,
                total_score=score,
                market_score=0.0,
                semantic_score=score,
                candidate_source="semantic",
                inclusion_reasons=reasons,
                current_session=current_session(),
                scrappy_present=False,
                news_count=mention_count,
                freshness_minutes=int(freshness_minutes),
            ))
    except Exception as e:
        logger.debug("opportunity semantic from Alpaca news failed: %s", e)

    # 2) Scrappy notes
    try:
        from stockbot.db.session import get_session_factory
        from stockbot.scrappy.store import get_recent_notes, get_recent_snapshots
        factory = get_session_factory()
        async with factory() as session:
            notes = await get_recent_notes(session, limit=100, since=since_dt)
            for n in notes or []:
                sym = getattr(n, "primary_symbol", None) or (getattr(n, "symbol", None) if hasattr(n, "symbol") else None)
                if not sym or sym in seen:
                    continue
                seen.add(sym)
                reasons = ["recent_scrappy_note"]
                if getattr(n, "catalyst_type", None):
                    reasons.append(f"catalyst_type_{n.catalyst_type}")
                out.append(OpportunityCandidate(
                    symbol=sym,
                    total_score=0.7,
                    market_score=0.0,
                    semantic_score=0.7,
                    candidate_source="semantic",
                    inclusion_reasons=reasons,
                    current_session=current_session(),
                    scrappy_present=True,
                    news_count=1,
                ))
            # 3) Intelligence snapshots: catalyst direction/strength, stale/conflict
            snapshots = await get_recent_snapshots(session, limit=50)
            for s in snapshots or []:
                sym = getattr(s, "symbol", None) if hasattr(s, "symbol") else (s.get("symbol") if isinstance(s, dict) else None)
                if not sym or sym in seen:
                    continue
                seen.add(sym)
                reasons = ["recent_intelligence_snapshot"]
                if getattr(s, "catalyst_direction", None):
                    reasons.append(f"catalyst_direction_{s.catalyst_direction}")
                if getattr(s, "catalyst_strength", None) is not None:
                    reasons.append(f"catalyst_strength_{s.catalyst_strength}")
                if getattr(s, "stale_flag", False):
                    reasons.append("stale_flag")
                if getattr(s, "conflict_flag", False):
                    reasons.append("conflict_flag")
                score = 0.6
                if getattr(s, "catalyst_strength", 0) and not getattr(s, "stale_flag", True):
                    score = 0.65 + min(getattr(s, "catalyst_strength", 0) / 500.0, 0.15)
                out.append(OpportunityCandidate(
                    symbol=sym,
                    total_score=round(score, 4),
                    market_score=0.0,
                    semantic_score=round(score, 4),
                    candidate_source="semantic",
                    inclusion_reasons=reasons,
                    current_session=current_session(),
                    scrappy_present=True,
                    news_count=0,
                ))
    except Exception as e:
        logger.debug("opportunity semantic notes/snapshots failed: %s", e)

    return out


async def run_opportunity_merge_from_latest_scanner() -> list[str] | None:
    """Re-run opportunity blend from latest live scanner run in DB (no new market scan). For manual/debug trigger. Ignores historical runs."""
    from stockbot.db.session import get_session_factory
    from stockbot.scanner.store import get_latest_live_scanner_result
    factory = get_session_factory()
    async with factory() as session:
        result = await get_latest_live_scanner_result(session)
    if not result or not result.candidates:
        return None
    return await merge_and_publish(result, result.run_id)


async def merge_and_publish(
    scanner_result: Any,
    run_id: str,
) -> list[str]:
    """
    Blend market (scanner) + semantic candidates and publish top symbols to Redis.
    Returns final list of symbols written to Redis. Worker/gateway read same key.
    """
    settings = get_settings()
    if not getattr(settings, "opportunity_engine_enabled", True):
        symbols = [c.symbol for c in scanner_result.candidates]
        await _publish_to_redis(symbols, run_id)
        return symbols
    mode = getattr(settings, "opportunity_engine_mode", "market_only")
    if mode == "market_only":
        symbols = [c.symbol for c in scanner_result.candidates]
        await _publish_to_redis(symbols, run_id)
        return symbols
    market_list = _scanner_candidates_to_opportunity(scanner_result.candidates)
    semantic_list = await _get_semantic_candidates()
    market_weight = getattr(settings, "opportunity_blend_market_weight", 0.6)
    semantic_weight = getattr(settings, "opportunity_blend_semantic_weight", 0.4)
    top_n = getattr(settings, "scanner_top_candidates", 25)
    if mode == "semantic_only":
        blended = blend_candidates([], semantic_list, market_weight=0.0, semantic_weight=1.0, top_n=top_n)
    else:
        blended = blend_candidates(market_list, semantic_list, market_weight, semantic_weight, top_n)
    symbols = [c.symbol for c in blended]
    await _publish_to_redis(symbols, run_id)
    # Persist opportunity run and candidates when blended/semantic
    await _persist_opportunity_run(
        run_id=run_id,
        mode=mode,
        market_count=len(market_list),
        semantic_count=len(semantic_list),
        blended_list=blended,
    )
    return symbols


async def _persist_opportunity_run(
    run_id: str,
    mode: str,
    market_count: int,
    semantic_count: int,
    blended_list: list[OpportunityCandidate],
) -> None:
    """Write opportunity run and candidates to DB."""
    from datetime import UTC, datetime
    try:
        from stockbot.db.session import get_session_factory
        from stockbot.db.models import OpportunityRun, OpportunityCandidateRow
        factory = get_session_factory()
        session_name = current_session()
        async with factory() as session:
            run_row = OpportunityRun(
                run_id=run_id,
                run_ts=datetime.now(UTC),
                mode=mode,
                session=session_name,
                market_candidates_count=market_count,
                semantic_candidates_count=semantic_count,
                blended_candidates_count=len(blended_list),
                top_candidates_count=len(blended_list),
                status="completed",
                notes=None,
            )
            session.add(run_row)
            await session.flush()
            for i, c in enumerate(blended_list):
                session.add(OpportunityCandidateRow(
                    run_id=run_id,
                    symbol=c.symbol,
                    rank=i + 1,
                    total_score=c.total_score,
                    market_score=c.market_score,
                    semantic_score=c.semantic_score,
                    candidate_source=c.candidate_source,
                    inclusion_reasons_json=c.inclusion_reasons,
                    filter_reasons_json=c.filter_reasons,
                    session=c.current_session,
                    news_count=c.news_count,
                    scrappy_present=c.scrappy_present,
                    freshness_minutes=c.freshness_minutes,
                    raw_json=c.raw_json,
                ))
            await session.commit()
    except Exception as e:
        logger.warning("opportunity persist failed: %s", e)


async def _publish_to_redis(symbols: list[str], run_id: str) -> None:
    try:
        settings = get_settings()
        r = redis.from_url(settings.redis_url, decode_responses=True)
        await r.set(REDIS_KEY_SCANNER_TOP, json.dumps(symbols), ex=REDIS_TTL_TOP_SEC)
        from datetime import UTC, datetime
        await r.set(REDIS_KEY_SCANNER_TOP_TS, datetime.now(UTC).isoformat(), ex=REDIS_TTL_TOP_SEC)
        await r.set(REDIS_KEY_SCANNER_RUN_ID, run_id, ex=REDIS_TTL_TOP_SEC)
        await r.aclose()
    except Exception as e:
        logger.warning("opportunity publish to Redis failed: %s", e)
