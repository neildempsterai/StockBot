"""
Premarket AI Referee runner: proactively assess focus symbols with fresh Scrappy research.
Only runs if Scrappy is producing fresh snapshots. Guards against assessing without research.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

import redis.asyncio as redis

from stockbot.config import get_settings
from stockbot.market_sessions import is_premarket
from stockbot.ai_referee.service import assess_setup
from stockbot.ai_referee.store import insert_assessment, get_latest_assessment_for_symbol
from stockbot.ai_referee.types import RefereeInput
from stockbot.scrappy.store import get_recent_notes, get_latest_snapshot_by_symbol
from stockbot.strategies.intra_event_momo import STRATEGY_ID, STRATEGY_VERSION

logger = logging.getLogger(__name__)

REDIS_KEY_AI_REFEREE_PREMARKET_LAST_RUN = "stockbot:ai_referee_premarket:last_run_ts"
REDIS_KEY_AI_REFEREE_PREMARKET_LAST_SYMBOLS = "stockbot:ai_referee_premarket:last_symbols"
REDIS_KEY_SCANNER_TOP = "stockbot:scanner:top_symbols"
REDIS_TTL_LAST_RUN_SEC = 86400

# Only assess symbols with fresh snapshots (not stale, not conflicted, < 4 hours old)
MAX_SNAPSHOT_AGE_HOURS = 4


async def _get_focus_symbols() -> list[str]:
    """Get current focus symbols from Redis (from scanner/opportunity)."""
    try:
        settings = get_settings()
        r = redis.from_url(settings.redis_url, decode_responses=True)
        raw = await r.get(REDIS_KEY_SCANNER_TOP)
        await r.aclose()
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, list) and data:
            return [str(s).strip().upper() for s in data if s][:20]  # Top 20 for premarket
    except Exception:
        pass
    return []


async def _should_assess_symbol(symbol: str, snapshot_id: int | None) -> tuple[bool, str]:
    """Check if symbol should be assessed: has fresh snapshot, not recently assessed."""
    if not snapshot_id:
        return False, "no_snapshot"
    
    from stockbot.db.session import get_session_factory
    from stockbot.db.models import SymbolIntelligenceSnapshot
    
        factory = get_session_factory()
        async with factory() as session:
            snapshot = await get_latest_snapshot_by_symbol(session, symbol)
            if not snapshot:
                return False, "snapshot_not_found"
        
        # Check freshness
        if snapshot.stale_flag:
            return False, "snapshot_stale"
        if snapshot.conflict_flag:
            return False, "snapshot_conflicted"
        
        # Check age
        if snapshot.snapshot_ts:
            age_hours = (datetime.now(UTC) - snapshot.snapshot_ts.replace(tzinfo=UTC)).total_seconds() / 3600
            if age_hours > MAX_SNAPSHOT_AGE_HOURS:
                return False, f"snapshot_too_old_{age_hours:.1f}h"
        
        # Check if recently assessed (skip if assessed < 2 hours ago)
        existing = await get_latest_assessment_for_symbol(session, symbol, STRATEGY_ID)
        if existing and existing.assessment_ts:
            age_hours = (datetime.now(UTC) - existing.assessment_ts.replace(tzinfo=UTC)).total_seconds() / 3600
            if age_hours < 2:
                return False, f"recently_assessed_{age_hours:.1f}h"
        
        return True, "ok"


async def _assess_symbol_premarket(symbol: str, snapshot_id: int) -> bool:
    """Assess a single symbol during premarket. Returns True if assessment was created."""
    try:
        from stockbot.db.session import get_session_factory
        from stockbot.scrappy.store import get_recent_notes
        from stockbot.db.models import SymbolIntelligenceSnapshot
        
        settings = get_settings()
        ai_referee_enabled = getattr(settings, "ai_referee_enabled", False)
        if not ai_referee_enabled:
            return False
        
        factory = get_session_factory()
        async with factory() as session:
            snapshot = await get_latest_snapshot_by_symbol(session, symbol)
            if not snapshot:
                return False
            
            # Build headlines from snapshot
            headlines: list[str] = []
            if snapshot.headline_set_json:
                headlines = list(snapshot.headline_set_json or [])[:20]
            
            # Build notes summary
            notes_summary: list[str] = []
            try:
                notes = await get_recent_notes(session, limit=30, symbol=symbol)
                notes_summary = [f"{n.title or ''}: {n.summary or ''}"[:200] for n in notes]
            except Exception as e:
                logger.debug("premarket_ai_referee notes fetch failed symbol=%s error=%s", symbol, e)
            
            # Build minimal RefereeInput (premarket: no live bars/quotes, use research only)
            inp = RefereeInput(
                symbol=symbol,
                strategy_id=STRATEGY_ID,
                strategy_version=STRATEGY_VERSION,
                scrappy_snapshot_id=snapshot.id,
                scrappy_run_id=snapshot.scrappy_run_id,
                scrappy_headlines=headlines,
                scrappy_notes_summary=notes_summary,
                feature_snapshot={},  # Premarket: no live features yet
                quote_snapshot=None,  # Premarket: may not have live quotes
                news_snapshot=None,  # Premarket: use Scrappy research instead
                candidate_side="buy",  # Default to buy for premarket assessment
            )
            
            assessment = await assess_setup(
                inp,
                api_key=getattr(settings, "openai_api_key", "") or "",
                model=getattr(settings, "ai_referee_model", "gpt-4o-mini"),
                timeout_seconds=getattr(settings, "ai_referee_timeout_seconds", 15),
                max_headlines=getattr(settings, "ai_referee_max_input_headlines", 20),
                max_notes=getattr(settings, "ai_referee_max_input_notes", 30),
                base_url=getattr(settings, "openai_base_url", None),
                require_json=getattr(settings, "ai_referee_require_json", True),
                auth_mode=getattr(settings, "ai_referee_auth", "api_key"),
            )
            
            if assessment:
                await insert_assessment(session, assessment)
                logger.info(
                    "premarket_ai_referee assessed symbol=%s assessment_id=%s decision=%s score=%s",
                    symbol, assessment.assessment_id[:8], assessment.decision_class, assessment.setup_quality_score
                )
                return True
            else:
                logger.debug("premarket_ai_referee assessment returned None for symbol=%s", symbol)
                return False
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.exception("premarket_ai_referee assess_symbol failed symbol=%s error=%s", symbol, e)
        return False


async def run_ai_referee_premarket_once() -> dict:
    """Run one premarket AI Referee pass on focus symbols with fresh research. Returns summary."""
    settings = get_settings()
    ai_referee_enabled = getattr(settings, "ai_referee_enabled", False)
    if not ai_referee_enabled:
        return {"status": "skipped", "reason": "ai_referee_disabled", "assessed": 0}
    
    if not is_premarket():
        return {"status": "skipped", "reason": "not_premarket", "assessed": 0}
    
    try:
        from stockbot.db.session import get_session_factory
        from stockbot.scrappy.store import get_latest_snapshot_for_symbol
        
        symbols = await _get_focus_symbols()
        if not symbols:
            return {"status": "skipped", "reason": "no_focus_symbols", "assessed": 0}
        
        factory = get_session_factory()
        assessed_count = 0
        skipped_count = 0
        skipped_reasons: dict[str, int] = {}
        
        async with factory() as session:
            for symbol in symbols:
                snapshot = await get_latest_snapshot_for_symbol(session, symbol)
                snapshot_id = snapshot.id if snapshot else None
                
                should_assess, reason = await _should_assess_symbol(symbol, snapshot_id)
                if not should_assess:
                    skipped_count += 1
                    skipped_reasons[reason] = skipped_reasons.get(reason, 0) + 1
                    continue
                
                if await _assess_symbol_premarket(symbol, snapshot_id):
                    assessed_count += 1
        
        # Persist run state
        try:
            r = redis.from_url(settings.redis_url, decode_responses=True)
            await r.set(REDIS_KEY_AI_REFEREE_PREMARKET_LAST_RUN, datetime.now(UTC).isoformat(), ex=REDIS_TTL_LAST_RUN_SEC)
            await r.set(REDIS_KEY_AI_REFEREE_PREMARKET_LAST_SYMBOLS, json.dumps(symbols), ex=REDIS_TTL_LAST_RUN_SEC)
            await r.aclose()
        except Exception:
            pass
        
        logger.info(
            "premarket_ai_referee run complete assessed=%d skipped=%d reasons=%s",
            assessed_count, skipped_count, skipped_reasons
        )
        
        return {
            "status": "completed",
            "assessed": assessed_count,
            "skipped": skipped_count,
            "skipped_reasons": skipped_reasons,
            "symbols_checked": len(symbols),
        }
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.exception("premarket_ai_referee run failed: %s", e)
        return {"status": "failed", "error": str(e)[:100], "assessed": 0}


async def run_ai_referee_premarket_loop() -> None:
    """Loop: run every hour during premarket, or when focus symbols change significantly."""
    settings = get_settings()
    ai_referee_enabled = getattr(settings, "ai_referee_enabled", False)
    if not ai_referee_enabled:
        logger.info("premarket_ai_referee disabled (AI_REFEREE_ENABLED=false)")
        return
    
    refresh_minutes = getattr(settings, "ai_referee_premarket_refresh_minutes", 60)
    await asyncio.sleep(60)  # Wait 1 minute after startup for Scrappy to run first
    
    while True:
        try:
            if is_premarket():
                await run_ai_referee_premarket_once()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception("premarket_ai_referee loop error: %s", e)
        await asyncio.sleep(refresh_minutes * 60)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_ai_referee_premarket_loop())


if __name__ == "__main__":
    main()
