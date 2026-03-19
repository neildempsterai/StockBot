"""Optional full-article fetch for open_text domains. Disabled by default."""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Max chars to store from fetched body
MAX_FETCH_CHARS = 30000

# Error codes for audit
FETCH_OK = "ok"
FETCH_ERROR_TIMEOUT = "timeout"
FETCH_ERROR_NON_200 = "non_200"
FETCH_ERROR_PARSE = "parse_failure"
FETCH_ERROR_EMPTY = "empty"
FETCH_ERROR_OVERSIZED = "oversized"
FETCH_ERROR_POLICY_BLOCKED = "policy_blocked"
FETCH_ERROR_NETWORK = "network"


def _strip_html(html: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    if not html:
        return ""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_FETCH_CHARS]


def fetch_full_text(url: str, timeout_sec: int = 15) -> str | None:
    """
    Fetch URL and return plain text (HTML stripped). None on failure.
    Only call for open_text domains when SCRAPPY_OPEN_TEXT_FETCH_ENABLED is true.
    """
    result = fetch_full_text_result(url, timeout_sec=timeout_sec)
    if result.get("ok") and result.get("text"):
        return result["text"]
    return None


def fetch_full_text_result(url: str, timeout_sec: int = 15) -> dict[str, Any]:
    """
    Fetch URL and return structured result for audit:
    - ok: bool
    - text: str | None (when ok)
    - error_code: str (when not ok): timeout, non_200, parse_failure, empty, oversized, network
    - error_message: str | None (truncated)
    """
    try:
        import httpx
    except ImportError:
        return {"ok": False, "error_code": FETCH_ERROR_NETWORK, "error_message": "httpx not installed"}
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout_sec) as client:
            r = client.get(
                url,
                headers={"User-Agent": "StockBot-Scrappy/1.0"},
            )
            if r.status_code != 200:
                return {
                    "ok": False,
                    "error_code": FETCH_ERROR_NON_200,
                    "error_message": f"status {r.status_code}",
                }
            ct = (r.headers.get("content-type") or "").lower()
            if "html" in ct or "text" in ct:
                raw = r.text or ""
            else:
                raw = (r.text or "")[:MAX_FETCH_CHARS]
            text = _strip_html(raw) if ("html" in ct or "text" in ct) else raw
            if not (text or "").strip():
                return {"ok": False, "error_code": FETCH_ERROR_EMPTY, "error_message": "empty content"}
            if len(text) >= MAX_FETCH_CHARS and len(raw) > MAX_FETCH_CHARS:
                return {
                    "ok": True,
                    "text": text,
                    "trimmed": True,
                    "error_code": None,
                    "error_message": f"trimmed to {MAX_FETCH_CHARS}",
                }
            return {"ok": True, "text": text, "trimmed": False}
    except Exception as e:
        err = str(e)
        if "timeout" in err.lower() or "timed out" in err.lower():
            code = FETCH_ERROR_TIMEOUT
        else:
            code = FETCH_ERROR_NETWORK
        logger.debug("fetch_full_text_result failed url=%s error=%s", url[:80], e)
        return {"ok": False, "error_code": code, "error_message": err[:500]}
