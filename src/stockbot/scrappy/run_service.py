"""Scrappy run orchestration: policy-driven pipeline from sources -> candidates -> notes -> DB."""
from __future__ import annotations

import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from stockbot.db.session import get_session_factory
from stockbot.scrappy.dedup import normalize_url, url_hash
from stockbot.scrappy.fetch_content import fetch_full_text_result
from stockbot.scrappy.ingestion import collect_candidates_from_sources
from stockbot.scrappy.notes import (
    build_note_from_candidate,
    draft_note_with_llm,
    validate_note_payload,
)
from stockbot.scrappy.source_policy import apply_policy_for_candidate, policy_blocked_fn
from stockbot.scrappy.store import (
    count_notes,
    create_scrappy_run,
    finish_scrappy_run,
    get_recent_notes,
    get_recent_runs,
    get_seen_url_hashes,
    get_watchlist_symbols,
    insert_market_intel_note,
    upsert_scrappy_url,
    upsert_source_health,
)

logger = logging.getLogger(__name__)

OPEN_TEXT_FETCH_ENABLED = os.getenv("SCRAPPY_OPEN_TEXT_FETCH_ENABLED", "").strip().lower() in ("1", "true", "yes")
LLM_NOTE_DRAFT_ENABLED = os.getenv("SCRAPPY_LLM_NOTE_DRAFT_ENABLED", "").strip().lower() in ("1", "true", "yes")

# Outcome codes computed from actual counters
OUTCOME_SUCCESS_USEFUL = "success_useful_output"
OUTCOME_SUCCESS_NO_NOTES = "success_candidates_but_no_notes"
OUTCOME_SUCCESS_ALL_DEDUPED = "success_all_deduped"
OUTCOME_SUCCESS_ALL_BLOCKED_OR_METADATA = "success_all_blocked_or_metadata_only_no_output"
OUTCOME_NO_CANDIDATES = "no_new_candidate_urls"
OUTCOME_PARTIAL = "partial_output_note_rejections"
OUTCOME_FAILED_FETCH = "failed_source_fetch"
OUTCOME_FAILED_VALIDATION = "failed_note_validation"
OUTCOME_FAILED_PERSISTENCE = "failed_persistence"
OUTCOME_FAILED_INTERNAL = "failed_internal_error"


def _compute_outcome(
    candidate_count: int,
    policy_blocked_count: int,
    post_dedup_count: int,
    notes_created: int,
    notes_attempted_count: int,
    notes_rejected_count: int,
    errors_list: list[str],
) -> str:
    """Compute outcome code from actual counters; no hand-written guesses."""
    if candidate_count == 0:
        return OUTCOME_NO_CANDIDATES
    if any("failed" in e.lower() or "error" in e.lower() for e in errors_list[:5]):
        if any("validate" in e.lower() for e in errors_list):
            return OUTCOME_FAILED_VALIDATION
        if any("insert" in e.lower() or "persist" in e.lower() for e in errors_list):
            return OUTCOME_FAILED_PERSISTENCE
        if any("fetch" in e.lower() for e in errors_list):
            return OUTCOME_FAILED_FETCH
        return OUTCOME_FAILED_INTERNAL
    if notes_created > 0:
        if notes_rejected_count > 0:
            return OUTCOME_PARTIAL
        return OUTCOME_SUCCESS_USEFUL
    if post_dedup_count == 0:
        if policy_blocked_count == candidate_count:
            return OUTCOME_SUCCESS_ALL_BLOCKED_OR_METADATA
        return OUTCOME_SUCCESS_ALL_DEDUPED
    return OUTCOME_SUCCESS_NO_NOTES


async def get_watchlist_symbols_list() -> list[str]:
    """Load watchlist symbols from DB (for POST /scrappy/run/watchlist)."""
    factory = get_session_factory()
    async with factory() as session:
        return await get_watchlist_symbols(session)


async def run_scrappy(
    run_type: str = "sweep",
    symbols: list[str] | None = None,
    themes: list[str] | None = None,
    *,
    watchlist_symbols_fn: callable | None = None,
) -> dict:
    """
    Full pipeline: create run -> collect candidates -> apply policy to every candidate
    -> drop blocked -> URL dedup -> open_text fetch only when policy+env allow
    -> build & validate notes -> idempotent insert -> finish with counters and computed outcome.
    """
    symbols = list(symbols or [])
    themes = list(themes or [])
    if run_type == "watchlist" and watchlist_symbols_fn:
        try:
            watchlist = await watchlist_symbols_fn()
            if watchlist:
                symbols = list(watchlist)
        except Exception:
            pass
    run_scope = {"symbols": symbols, "themes": themes}
    factory = get_session_factory()
    async with factory() as session:
        run_id = await create_scrappy_run(
            session,
            run_type,
            candidate_url_count=0,
            post_dedup_count=0,
            notes_created=0,
            run_scope=run_scope,
        )
        try:
            candidates = collect_candidates_from_sources(symbols=symbols, themes=themes)
            candidate_count = len(candidates)
            if candidate_count == 0:
                await finish_scrappy_run(
                    session, run_id, OUTCOME_NO_CANDIDATES,
                    post_dedup_count=0, notes_created=0,
                    policy_blocked_count=0, metadata_only_count=0, open_text_count=0,
                    notes_attempted_count=0, notes_rejected_count=0,
                )
                return {
                    "run_id": run_id,
                    "run_type": run_type,
                    "candidate_url_count": 0,
                    "post_dedup_count": 0,
                    "notes_created": 0,
                    "outcome_code": OUTCOME_NO_CANDIDATES,
                }

            # 1) Apply policy to every candidate; attach policy_decision and policy_reason_code
            policy_blocked_count = 0
            eligible: list[dict] = []
            for c in candidates:
                url = (c.get("url") or "").strip()
                if not url:
                    continue
                content_mode, reason_code = apply_policy_for_candidate(c)
                c["policy_decision"] = content_mode
                c["policy_reason_code"] = reason_code
                if content_mode == "blocked":
                    policy_blocked_count += 1
                    continue
                eligible.append(c)

            # 2) URL dedup
            url_hashes_list = [url_hash(c.get("url") or "") for c in eligible]
            seen_hashes = await get_seen_url_hashes(session, url_hashes_list)
            after_dedup: list[dict] = []
            for c in eligible:
                h = url_hash(c.get("url") or "")
                if h in seen_hashes:
                    continue
                after_dedup.append(c)

            # 3) Count content modes among post-dedup
            metadata_only_count = sum(1 for c in after_dedup if c.get("policy_decision") == "metadata_only")
            open_text_count = sum(1 for c in after_dedup if c.get("policy_decision") == "open_text")

            # 4) Open-text fetch only when policy is open_text AND env enabled; metadata_only/blocked never fetch
            for c in after_dedup:
                if c.get("policy_decision") != "open_text":
                    continue
                if not OPEN_TEXT_FETCH_ENABLED:
                    continue
                url = (c.get("url") or "").strip()
                if not url:
                    continue
                result = fetch_full_text_result(url)
                if result.get("ok") and result.get("text"):
                    c["full_text"] = result["text"]
                    if not (c.get("summary") or "").strip():
                        c["summary"] = result["text"][:5000]
                    c["fetch_error_code"] = None
                else:
                    c["fetch_error_code"] = result.get("error_code") or "unknown"
                    c["fetch_error_message"] = result.get("error_message")
                    # Do not upgrade metadata or invent content; content_mode stays open_text but we have no full_text

            post_dedup_count = len(after_dedup)
            notes_created = 0
            note_ids: list[str] = []
            errors_list: list[str] = []
            # Per-source aggregates for source health (fetch success vs note yield)
            source_candidates: dict[str, int] = defaultdict(int)
            source_post_dedup: dict[str, int] = defaultdict(int)
            source_fetch_success: dict[str, int] = defaultdict(int)
            source_fetch_failure: dict[str, int] = defaultdict(int)
            source_notes_inserted: dict[str, int] = defaultdict(int)
            source_last_error: dict[str, tuple[str | None, str | None]] = {}

            for c in after_dedup:
                src = c.get("source_name") or "unknown"
                source_post_dedup[src] += 1
                mode = c.get("policy_decision") or "metadata_only"
                if mode == "open_text":
                    if c.get("fetch_error_code"):
                        source_fetch_failure[src] += 1
                        source_last_error[src] = (c.get("fetch_error_code"), c.get("fetch_error_message"))
                    else:
                        source_fetch_success[src] += 1
                else:
                    source_fetch_success[src] += 1  # metadata_only: we have metadata

            for c in eligible:
                source_candidates[c.get("source_name") or "unknown"] += 1

            for c in after_dedup:
                url = (c.get("url") or "").strip()
                norm = normalize_url(url)
                h = url_hash(url)
                try:
                    await upsert_scrappy_url(session, h, norm, c.get("source_name") or "unknown")
                except Exception as e:
                    errors_list.append(f"url_upsert {url[:80]}: {e}")
                    continue
                try:
                    payload = build_note_from_candidate(
                        c, run_id,
                        primary_symbol=symbols[0] if symbols else None,
                        symbol_context=symbols,
                    )
                except Exception as e:
                    errors_list.append(f"build_note {url[:80]}: {e}")
                    continue
                if LLM_NOTE_DRAFT_ENABLED:
                    try:
                        payload = draft_note_with_llm(payload)
                    except Exception:
                        pass
                try:
                    validate_note_payload(payload)
                except ValueError as e:
                    errors_list.append(f"validate {url[:80]}: {e}")
                    continue
                try:
                    nid = await insert_market_intel_note(
                        session,
                        note_id=None,
                        source_name=payload["source_name"],
                        source_url=payload["source_url"],
                        published_at=payload.get("published_at"),
                        title=payload.get("title"),
                        summary=payload.get("summary"),
                        evidence_snippets=payload.get("evidence_snippets"),
                        detected_symbols=payload.get("detected_symbols"),
                        primary_symbol=payload.get("primary_symbol"),
                        sector_tags=payload.get("sector_tags"),
                        theme_tags=payload.get("theme_tags"),
                        catalyst_type=payload.get("catalyst_type"),
                        sentiment_label=payload.get("sentiment_label"),
                        sentiment_score=payload.get("sentiment_score"),
                        confidence=payload.get("confidence"),
                        expires_at=payload.get("expires_at"),
                        raw_metadata=payload.get("raw_metadata"),
                        scrappy_run_id=run_id,
                        content_mode=payload.get("content_mode"),
                        dedup_hash=payload.get("dedup_hash"),
                        why_this_matters=payload.get("why_this_matters"),
                        impact_horizon=payload.get("impact_horizon"),
                    )
                    notes_created += 1
                    note_ids.append(nid)
                    source_notes_inserted[payload["source_name"]] += 1
                except Exception as e:
                    errors_list.append(f"insert {url[:80]}: {e}")

            notes_attempted_count = len(after_dedup)
            notes_rejected_count = notes_attempted_count - notes_created

            # Per-source health: fetch success vs note yield
            all_sources = set(source_candidates) | set(source_post_dedup)
            for src in all_sources:
                await upsert_source_health(
                    session,
                    src,
                    fetch_success_count_delta=source_fetch_success.get(src, 0),
                    fetch_failure_count_delta=source_fetch_failure.get(src, 0),
                    candidate_count_delta=source_candidates.get(src, 0),
                    post_dedup_count_delta=source_post_dedup.get(src, 0),
                    notes_inserted_delta=source_notes_inserted.get(src, 0),
                    last_error_code=source_last_error.get(src, (None, None))[0],
                    last_error_message=source_last_error.get(src, (None, None))[1],
                )

            outcome = _compute_outcome(
                candidate_count,
                policy_blocked_count,
                post_dedup_count,
                notes_created,
                notes_attempted_count,
                notes_rejected_count,
                errors_list,
            )
            errors_str = "\n".join(errors_list[:50]) if errors_list else None
            await finish_scrappy_run(
                session,
                run_id,
                outcome,
                post_dedup_count=post_dedup_count,
                notes_created=notes_created,
                policy_blocked_count=policy_blocked_count,
                metadata_only_count=metadata_only_count,
                open_text_count=open_text_count,
                notes_attempted_count=notes_attempted_count,
                notes_rejected_count=notes_rejected_count,
                errors=errors_str,
            )
            return {
                "run_id": run_id,
                "run_type": run_type,
                "candidate_url_count": candidate_count,
                "post_dedup_count": post_dedup_count,
                "policy_blocked_count": policy_blocked_count,
                "metadata_only_count": metadata_only_count,
                "open_text_count": open_text_count,
                "notes_created": notes_created,
                "notes_attempted_count": notes_attempted_count,
                "notes_rejected_count": notes_rejected_count,
                "outcome_code": outcome,
                "note_ids": note_ids,
            }
        except Exception as e:
            logger.exception("run_scrappy failed run_id=%s", run_id)
            await finish_scrappy_run(
                session,
                run_id,
                OUTCOME_FAILED_INTERNAL,
                errors=str(e),
            )
            raise


async def get_notes_recent(
    limit: int = 50,
    symbol: str | None = None,
    catalyst_type: str | None = None,
    sentiment_label: str | None = None,
    content_mode: str | None = None,
    since_hours: int | None = None,
) -> list[dict]:
    """Return recent market_intel_notes as dicts with optional filters."""
    factory = get_session_factory()
    since = None
    if since_hours is not None and since_hours > 0:
        since = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    async with factory() as session:
        notes = await get_recent_notes(
            session,
            limit=limit,
            symbol=symbol,
            catalyst_type=catalyst_type,
            sentiment_label=sentiment_label,
            content_mode=content_mode,
            since=since,
        )
    out: list[dict] = []
    for n in notes:
        out.append({
            "note_id": n.note_id,
            "created_at": n.created_at.isoformat() if n.created_at else None,
            "source_name": n.source_name,
            "source_url": n.source_url,
            "title": n.title,
            "summary": n.summary,
            "primary_symbol": n.primary_symbol,
            "catalyst_type": n.catalyst_type,
            "sentiment_label": n.sentiment_label,
            "confidence": float(n.confidence) if n.confidence is not None else None,
            "content_mode": n.content_mode,
        })
    return out[:limit]


async def get_telemetry(limit: int = 50, hours: int = 24) -> dict:
    """Truthful telemetry from DB: runs, counts, outcome codes, zero-yield streak."""
    factory = get_session_factory()
    async with factory() as session:
        runs = await get_recent_runs(session, limit=limit)
        notes_total = await count_notes(session)
    run_dicts = []
    for r in runs:
        run_dicts.append({
            "run_id": r.run_id,
            "run_type": r.run_type,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "candidate_url_count": r.candidate_url_count,
            "post_dedup_count": r.post_dedup_count,
            "policy_blocked_count": getattr(r, "policy_blocked_count", None) or 0,
            "metadata_only_count": getattr(r, "metadata_only_count", None) or 0,
            "open_text_count": getattr(r, "open_text_count", None) or 0,
            "notes_attempted_count": getattr(r, "notes_attempted_count", None) or 0,
            "notes_rejected_count": getattr(r, "notes_rejected_count", None) or 0,
            "notes_created": r.notes_created,
            "outcome_code": r.outcome_code,
        })
    zero_yield_streak = 0
    for r in runs:
        if (r.notes_created or 0) > 0:
            break
        zero_yield_streak += 1
    return {
        "total_runs": len(run_dicts),
        "runs": run_dicts,
        "notes_total": notes_total,
        "zero_yield_streak": zero_yield_streak,
        "limit": limit,
        "hours": hours,
    }


async def get_audit(limit: int = 10) -> dict:
    """Truthful audit: last N runs with full counters for reconciliation."""
    factory = get_session_factory()
    async with factory() as session:
        runs = await get_recent_runs(session, limit=limit)
        notes_total = await count_notes(session)
    run_list = []
    for r in runs:
        notes_inserted = r.notes_created or 0
        notes_attempted = getattr(r, "notes_attempted_count", None) or 0
        notes_rejected = getattr(r, "notes_rejected_count", None) or 0
        expected_notes = notes_attempted
        mismatch = notes_inserted != expected_notes and expected_notes > 0
        run_list.append({
            "run_id": r.run_id,
            "run_type": r.run_type,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "candidate_url_count": r.candidate_url_count,
            "post_dedup_count": r.post_dedup_count,
            "policy_blocked_count": getattr(r, "policy_blocked_count", None) or 0,
            "metadata_only_count": getattr(r, "metadata_only_count", None) or 0,
            "open_text_count": getattr(r, "open_text_count", None) or 0,
            "notes_attempted_count": notes_attempted,
            "notes_inserted_count": notes_inserted,
            "notes_rejected_count": notes_rejected,
            "outcome_code": r.outcome_code,
            "mismatch_flag": mismatch,
            "errors": r.errors,
            "run_scope": r.run_scope,
        })
    return {"runs": run_list, "notes_total": notes_total, "limit": limit}
