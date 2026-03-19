"""Source policy: apply registry + allowlist; policy_blocked_fn for dedup filter."""
from __future__ import annotations

from typing import Any

from stockbot.scrappy.source_registry import (
    get_content_mode,
    get_policy_decision,
    is_blocked,
    load_source_registry,
)


def policy_blocked_fn(url: str, candidate: dict[str, Any]) -> bool:
    """
    True if URL/domain is blocked by registry (do not fetch).
    Does not block metadata_only; only blocked -> drop from fetch.
    """
    return is_blocked(url)


def get_content_mode_for_candidate(candidate: dict[str, Any]) -> str:
    """Return content_mode for this candidate's url."""
    url = (candidate.get("url") or candidate.get("source_url") or "").strip()
    return get_content_mode(url)


def apply_policy_for_candidate(candidate: dict[str, Any]) -> tuple[str, str]:
    """
    Return (content_mode, reason_code) for this candidate.
    Attach to candidate as policy_decision and policy_reason_code for audit.
    """
    url = (candidate.get("url") or candidate.get("source_url") or "").strip()
    return get_policy_decision(url)


def list_domains_by_content_mode(config_dir: Any = None) -> dict[str, list[str]]:
    """Return { open_text: [...], metadata_only: [...], blocked: [...] } for audit."""
    reg = load_source_registry(config_dir)
    out: dict[str, list[str]] = {"open_text": [], "metadata_only": [], "blocked": []}
    for domain, entry in (reg.get("domains") or {}).items():
        if isinstance(entry, dict):
            mode = (entry.get("content_mode") or reg.get("default_content_mode", "metadata_only")).lower()
        elif isinstance(entry, str):
            mode = entry.lower()
        else:
            mode = "metadata_only"
        if mode in out:
            out[mode].append(domain)
    return out
