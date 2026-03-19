"""OpenAI-backed referee service. Structured output only; fail-safe by mode."""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any, AsyncIterator
from uuid import uuid4

import httpx

from stockbot.ai_referee.prompting import (
    REFEREE_RESPONSE_SCHEMA,
    SYSTEM_PROMPT,
    build_user_message,
)
from stockbot.ai_referee.types import RefereeAssessment, RefereeInput

logger = logging.getLogger(__name__)

REFEREE_VERSION = "0.1.0"
CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"


def _parse_response(
    raw: dict,
    symbol: str,
    strategy_id: str,
    strategy_version: str,
    scrappy_snapshot_id: int | None,
    scrappy_run_id: str | None,
    model_name: str,
) -> RefereeAssessment:
    """Build RefereeAssessment from parsed JSON. Validates enums."""
    score = int(raw.get("setup_quality_score", 0))
    if score < 0 or score > 100:
        score = max(0, min(100, score))
    catalyst = str(raw.get("catalyst_strength", "weak")).lower()
    if catalyst not in ("weak", "moderate", "strong"):
        catalyst = "weak"
    regime = str(raw.get("regime_label", "unknown")).lower()
    if regime not in ("bull", "bear", "chop", "unknown"):
        regime = "unknown"
    evidence = str(raw.get("evidence_sufficiency", "low")).lower()
    if evidence not in ("low", "medium", "high"):
        evidence = "low"
    decision = str(raw.get("decision_class", "review")).lower()
    if decision not in ("allow", "downgrade", "block", "review"):
        decision = "review"
    reason_codes = raw.get("reason_codes")
    if not isinstance(reason_codes, list):
        reason_codes = []
    reason_codes = [str(c) for c in reason_codes]
    return RefereeAssessment(
        assessment_id=str(uuid4()),
        assessment_ts=datetime.now(UTC),
        symbol=symbol,
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        scrappy_snapshot_id=scrappy_snapshot_id,
        scrappy_run_id=scrappy_run_id,
        model_name=model_name,
        referee_version=REFEREE_VERSION,
        setup_quality_score=score,
        catalyst_strength=catalyst,
        regime_label=regime,
        evidence_sufficiency=evidence,
        contradiction_flag=bool(raw.get("contradiction_flag", False)),
        stale_flag=bool(raw.get("stale_flag", False)),
        decision_class=decision,
        reason_codes=reason_codes,
        plain_english_rationale=str(raw.get("plain_english_rationale", ""))[:2000],
        raw_response_json=dict(raw),
    )


async def _assess_via_api_key(
    inp: RefereeInput,
    user_msg: str,
    model: str,
    timeout_seconds: int,
    require_json: bool,
    api_key: str,
    base_url: str | None,
) -> RefereeAssessment | None:
    """Use OpenAI API with API key."""
    try:
        from openai import AsyncOpenAI
    except ImportError:
        logger.warning("openai not installed; ai_referee disabled")
        return None
    client = AsyncOpenAI(api_key=api_key.strip(), base_url=base_url) if base_url else AsyncOpenAI(api_key=api_key.strip())
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    kwargs: dict = {
        "model": model,
        "messages": messages,
        "timeout": float(timeout_seconds),
    }
    if require_json:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "referee_response",
                "strict": True,
                "schema": REFEREE_RESPONSE_SCHEMA,
            },
        }
    try:
        resp = await client.chat.completions.create(**kwargs)
    except (TimeoutError, Exception) as e:
        logger.debug("ai_referee api_key call failed: %s", e)
        return None
    return _extract_assessment_from_response(resp, inp, model)


def _log_oauth_error(e: Exception) -> None:
    """Log oauth-codex API errors with response body when available (e.g. 400 detail)."""
    body = getattr(e, "body", None)
    response = getattr(e, "response", None)
    if body is not None:
        logger.warning("ai_referee oauth call failed: %s (body: %s)", e, body)
    elif response is not None and hasattr(response, "text"):
        logger.warning("ai_referee oauth call failed: %s (response: %s)", e, response.text)
    else:
        logger.warning("ai_referee oauth call failed: %s", e)


async def _iter_sse_events(response: httpx.Response) -> AsyncIterator[dict[str, Any]]:
    """Parse a text/event-stream response into JSON event objects (OpenClaw/Codex SSE format)."""
    buffer = ""
    async for chunk in response.aiter_text():
        buffer += chunk.replace("\r\n", "\n")
        while "\n\n" in buffer:
            frame, buffer = buffer.split("\n\n", 1)
            data_lines: list[str] = []
            for line in frame.split("\n"):
                if line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
            if not data_lines:
                continue
            payload = "\n".join(data_lines).strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj
    tail = buffer.strip()
    if tail:
        data_lines = [line[5:].lstrip() for line in tail.split("\n") if line.startswith("data:")]
        if data_lines:
            payload = "\n".join(data_lines).strip()
            if payload and payload != "[DONE]":
                try:
                    obj = json.loads(payload)
                    if isinstance(obj, dict):
                        yield obj
                except json.JSONDecodeError:
                    pass


def _extract_text_from_completed(event: dict[str, Any]) -> str:
    """Pull assistant text from response.completed output when deltas were not captured."""
    response_obj = event.get("response")
    if not isinstance(response_obj, dict):
        return ""
    pieces: list[str] = []
    output = response_obj.get("output")
    if not isinstance(output, list):
        return ""
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "output_text":
                continue
            text = part.get("text")
            if isinstance(text, str):
                pieces.append(text)
    return "".join(pieces)


async def _assess_via_oauth(
    inp: RefereeInput,
    user_msg: str,
    model: str,
    timeout_seconds: int,
    require_json: bool,
) -> RefereeAssessment | None:
    """Use oauth-codex SDK: authenticate then POST /responses with REFEREE_OAUTH_PAYLOAD_KEYS shape."""
    try:
        from oauth_codex import AsyncClient
    except ImportError:
        logger.warning("oauth-codex not installed; pip install oauth-codex for OAuth")
        return None

    user_content = user_msg
    if require_json:
        user_content = (
            user_msg
            + "\n\nReply with exactly one JSON object; no other text or markdown. Keys: "
            "setup_quality_score, catalyst_strength, regime_label, evidence_sufficiency, "
            "contradiction_flag, stale_flag, decision_class, reason_codes, plain_english_rationale."
        )

    timeout = float(timeout_seconds) if timeout_seconds else 60.0
    text_parts: list[str] = []
    try:
        async with AsyncClient(timeout=timeout) as client:
            await client.authenticate()
            # Codex /responses shape: input must be a list; include tools.web_search for live search;
            # do not send strict_output/validation_mode (backend 400).
            payload: dict[str, object] = {
                "model": model or "gpt-5.4",
                "instructions": SYSTEM_PROMPT,
                "input": [{"role": "user", "content": user_content}],
                "stream": True,
                "store": False,
                "tools": [{"type": "web_search"}],
            }
            response = await client.request("POST", "/responses", json_data=payload)
            raw_text = response.text
            # Backend may return SSE (data: {...}\n\n) or a JSON array; try both.
            try:
                events = response.json()
            except Exception:
                events = []
                for line in raw_text.split("\n"):
                    line = line.strip()
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        if data and data != "[DONE]":
                            try:
                                events.append(json.loads(data))
                            except json.JSONDecodeError:
                                pass
            if not isinstance(events, list):
                logger.warning("ai_referee oauth: unexpected stream response type %s", type(events))
                return None
            for event in events:
                if isinstance(event, dict) and event.get("error"):
                    logger.warning("ai_referee oauth stream error: %s", event.get("error"))
                    return None
                delta = event.get("delta") if isinstance(event, dict) else getattr(event, "delta", None)
                if isinstance(delta, str):
                    text_parts.append(delta)
                etype = (event.get("type") or "") if isinstance(event, dict) else (getattr(event, "type", "") or "")
                if etype in ("response.completed", "response.done", "response.output_text.done"):
                    break

        output_text = "".join(text_parts).strip()
    except Exception as e:
        _log_oauth_error(e)
        return None

    if not output_text:
        logger.warning("ai_referee oauth: empty stream output")
        return None
    try:
        raw = json.loads(output_text)
    except json.JSONDecodeError:
        logger.warning("ai_referee oauth: stream output not valid JSON: %.200s", output_text)
        return None
    if not isinstance(raw, dict):
        return None
    return _parse_response(
        raw,
        symbol=inp.symbol,
        strategy_id=inp.strategy_id,
        strategy_version=inp.strategy_version,
        scrappy_snapshot_id=inp.scrappy_snapshot_id,
        scrappy_run_id=inp.scrappy_run_id,
        model_name=model,
    )


def _extract_assessment_from_response(resp: object, inp: RefereeInput, model: str) -> RefereeAssessment | None:
    """Parse response object (OpenAI or oauth-codex) into RefereeAssessment."""
    choice = getattr(resp, "choices", None)
    choice = choice[0] if choice else None
    if not choice or not getattr(choice, "message", None):
        logger.warning("ai_referee: empty completion")
        return None
    content = getattr(choice.message, "content", None) or ""
    if not content.strip():
        return None
    try:
        raw = json.loads(content)
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict):
        return None
    return _parse_response(
        raw,
        symbol=inp.symbol,
        strategy_id=inp.strategy_id,
        strategy_version=inp.strategy_version,
        scrappy_snapshot_id=inp.scrappy_snapshot_id,
        scrappy_run_id=inp.scrappy_run_id,
        model_name=model,
    )


async def assess_setup(
    inp: RefereeInput,
    *,
    api_key: str,
    model: str,
    timeout_seconds: int,
    max_headlines: int,
    max_notes: int,
    base_url: str | None = None,
    require_json: bool = True,
    auth_mode: str = "api_key",
) -> RefereeAssessment | None:
    """
    Call OpenAI or Codex (OAuth) for structured referee assessment. Returns None on timeout/parse failure.
    No order/trading output; structured assessment only.
    - auth_mode=api_key: use OPENAI_API_KEY (default).
    - auth_mode=oauth: use oauth-codex (ChatGPT Pro); no key; run one-time browser login first.
    """
    use_oauth = (auth_mode or "api_key").strip().lower() == "oauth"
    if use_oauth:
        if not model or model.strip() == "":
            model = "gpt-5.4"
        user_msg = build_user_message(inp, max_headlines, max_notes)
        return await _assess_via_oauth(inp, user_msg, model, timeout_seconds, require_json)
    if not api_key or not api_key.strip():
        logger.debug("ai_referee: no API key, skipping")
        return None
    user_msg = build_user_message(inp, max_headlines, max_notes)
    return await _assess_via_api_key(
        inp, user_msg, model, timeout_seconds, require_json, api_key, base_url
    )
