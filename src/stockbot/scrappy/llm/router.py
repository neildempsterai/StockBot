"""Scrappy task-based model router. Config-driven; task map for market-intel only."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from stockbot.scrappy.llm import adapters

SCRAPPY_TASKS = (
    "triage",
    "structured_note_draft",
    "whole_doc_read",
    "semantic_validation",
    "arbitration",
)

_route_config: dict[str, dict[str, Any]] | None = None
_OLLAMA_ENABLED = os.getenv("SCRAPPY_ROUTER_OLLAMA_ENABLED", "1").strip().lower() in ("1", "true", "yes")
_OPENROUTER_ENABLED = os.getenv("SCRAPPY_ROUTER_OPENROUTER_ENABLED", "1").strip().lower() in ("1", "true", "yes")
_OLLAMA_FAST = os.getenv("OLLAMA_FAST_MODEL", os.getenv("OLLAMA_CHAT_MODEL", "qwen3:8b")).strip() or "qwen3:8b"
_OLLAMA_REASONING = os.getenv("OLLAMA_REASONING_MODEL", "qwen3:8b").strip() or "qwen3:8b"
_OPENROUTER_LONG = os.getenv("SCRAPPY_ROUTER_LONG_CONTEXT_MODEL", "openrouter/free").strip() or "openrouter/free"


def _load_route_config() -> dict[str, dict[str, Any]]:
    global _route_config
    if _route_config is not None:
        return _route_config
    config_dir = Path(__file__).resolve().parent.parent / "config"
    path = config_dir / "scrappy_router.yml"
    defaults: dict[str, dict[str, Any]] = {
        "triage": {"provider": "ollama", "model": "fast", "timeout_s": 30, "allow_cloud_long_context": False},
        "structured_note_draft": {"provider": "ollama", "model": "reasoning", "timeout_s": 90, "allow_cloud_long_context": False},
        "whole_doc_read": {"provider": "openrouter", "model": "long_context", "timeout_s": 90, "allow_cloud_long_context": True},
        "semantic_validation": {"provider": "ollama", "model": "fast", "timeout_s": 45, "allow_cloud_long_context": False},
        "arbitration": {"provider": "openrouter", "model": "long_context", "timeout_s": 90, "allow_cloud_long_context": True},
    }
    if path.is_file():
        try:
            import yaml
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for task, cfg in (data.get("tasks") or {}).items():
                if task in SCRAPPY_TASKS:
                    defaults[task] = {**defaults.get(task, {}), **cfg}
        except Exception:
            pass
    for task in SCRAPPY_TASKS:
        p = os.getenv(f"SCRAPPY_ROUTER_{task.upper()}_PROVIDER", "").strip().lower()
        if p:
            defaults.setdefault(task, {})["provider"] = p
        m = os.getenv(f"SCRAPPY_ROUTER_{task.upper()}_MODEL", "").strip()
        if m:
            defaults.setdefault(task, {})["model"] = m
        t = os.getenv(f"SCRAPPY_ROUTER_{task.upper()}_TIMEOUT", "")
        if t.isdigit():
            defaults.setdefault(task, {})["timeout_s"] = int(t)
    _route_config = defaults
    return _route_config


def _resolve_model(provider: str, model_key: str) -> str:
    if provider == "ollama":
        if model_key == "fast":
            return _OLLAMA_FAST
        if model_key == "reasoning":
            return _OLLAMA_REASONING
        return _OLLAMA_FAST
    if provider == "openrouter":
        if model_key == "long_context":
            return _OPENROUTER_LONG
        return _OPENROUTER_LONG
    return model_key


def get_route(task: str) -> dict[str, Any] | None:
    """Return route for task: provider, model, timeout_s, allow_cloud_long_context. None if disabled."""
    if task not in SCRAPPY_TASKS:
        return None
    cfg = _load_route_config().get(task)
    if not cfg:
        return None
    provider = (cfg.get("provider") or "ollama").strip().lower()
    model_key = (cfg.get("model") or "fast").strip()
    if provider == "ollama" and not (_OLLAMA_ENABLED and adapters.ollama_enabled()):
        return None
    if provider == "openrouter" and not (_OPENROUTER_ENABLED and adapters.openrouter_enabled()):
        return None
    model = _resolve_model(provider, model_key)
    return {
        "provider": provider,
        "model": model,
        "model_key": model_key,
        "timeout_s": int(cfg.get("timeout_s") or 60),
        "allow_cloud_long_context": bool(cfg.get("allow_cloud_long_context", False)),
    }


def call(
    task: str,
    prompt: str,
    system: str = "",
    timeout_s: int | None = None,
) -> tuple[str, dict[str, Any]]:
    """Run one Scrappy LLM task. Returns (text, meta). meta: provider, model, success, error."""
    route = get_route(task)
    if not route:
        return "", {"provider": "", "model": "", "success": False, "error": "no route"}
    provider = route["provider"]
    model = route["model"]
    timeout_s = timeout_s or route["timeout_s"]
    meta: dict[str, Any] = {"provider": provider, "model": model, "success": False, "error": ""}
    if provider == "ollama":
        text, adapter_meta = adapters.ollama_call(model=model, prompt=prompt, system=system, timeout_s=timeout_s)
        meta["success"] = adapter_meta.get("success", False)
        meta["error"] = adapter_meta.get("error", "")
        if adapter_meta.get("actual_model"):
            meta["actual_model"] = adapter_meta["actual_model"]
        return text, meta
    if provider == "openrouter":
        text, adapter_meta = adapters.openrouter_call(
            model=model, prompt=prompt, system=system, timeout_s=timeout_s
        )
        meta["success"] = adapter_meta.get("success", False)
        meta["error"] = adapter_meta.get("error", "")
        if adapter_meta.get("actual_model"):
            meta["actual_model"] = adapter_meta["actual_model"]
        return text, meta
    meta["error"] = "unknown provider"
    return "", meta
