"""Provider adapters for Scrappy router: Ollama, OpenRouter. Env-based; no gateway."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

_OLLAMA_URL = os.getenv("OLLAMA_CHAT_URL", "").strip().rstrip("/")
_OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
_OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", os.getenv("SCRAPPY_OPENROUTER_API_KEY", "")).strip()
_OPENROUTER_BASE = (
    os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip().rstrip("/")
    or "https://openrouter.ai/api/v1"
)
if _OPENROUTER_BASE.endswith("/api/v1"):
    _OPENROUTER_CHAT_URL = f"{_OPENROUTER_BASE}/chat/completions"
else:
    _OPENROUTER_CHAT_URL = f"{_OPENROUTER_BASE.rstrip('/')}/api/v1/chat/completions"


def ollama_enabled() -> bool:
    return bool(_OLLAMA_URL)


def openrouter_enabled() -> bool:
    return bool(_OPENROUTER_KEY)


def ollama_call(
    model: str,
    prompt: str,
    system: str = "",
    timeout_s: int | None = None,
) -> tuple[str, dict[str, Any]]:
    """Call Ollama chat. Returns (text, meta)."""
    timeout_s = timeout_s or _OLLAMA_TIMEOUT
    meta: dict[str, Any] = {"provider": "ollama", "model": model, "success": False, "error": ""}
    if not _OLLAMA_URL:
        meta["error"] = "OLLAMA_CHAT_URL not set"
        return "", meta
    ollama_model = model.split("/", 1)[1] if model.startswith("ollama/") else model
    body: dict[str, Any] = {"model": ollama_model, "messages": []}
    if system:
        body["messages"].append({"role": "system", "content": system})
    body["messages"].append({"role": "user", "content": prompt})
    try:
        req = urllib.request.Request(
            f"{_OLLAMA_URL}/api/chat",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as res:
            data = json.loads(res.read().decode("utf-8"))
        text = (data.get("message", {}).get("content", "") or "").strip()
        meta["success"] = True
        return text, meta
    except Exception as e:
        meta["error"] = str(e)[:200]
        return "", meta


def openrouter_call(
    model: str,
    prompt: str,
    system: str = "",
    timeout_s: int | None = None,
    response_format: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Call OpenRouter chat. Returns (text, meta). meta may include actual_model."""
    timeout_s = timeout_s or 120
    meta: dict[str, Any] = {"provider": "openrouter", "model": model, "success": False, "error": ""}
    if not _OPENROUTER_KEY:
        meta["error"] = "OPENROUTER_API_KEY not set"
        return "", meta
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system or "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 4096,
    }
    if response_format is not None:
        payload["response_format"] = response_format
    try:
        req = urllib.request.Request(
            _OPENROUTER_CHAT_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {_OPENROUTER_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost",
                "X-Title": "StockBot_Scrappy",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        body = json.loads(raw)
        text = (body.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
        meta["success"] = True
        if isinstance(body.get("model"), str):
            meta["actual_model"] = body["model"]
        return text, meta
    except urllib.error.HTTPError as e:
        code = getattr(e, "code", 0)
        try:
            snippet = (e.read().decode("utf-8", errors="replace") or "")[:500]
        except Exception:
            snippet = ""
        meta["error"] = f"HTTP {code}" + (f": {snippet}" if snippet else "")
        return "", meta
    except Exception as e:
        meta["error"] = str(e)[:200]
        return "", meta
