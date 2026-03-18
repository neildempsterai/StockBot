"""Source registry: load domain -> content_mode from YAML; central allowlist."""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

_CONTENT_MODES = ("open_text", "metadata_only", "blocked")
# Reason codes for policy decisions (auditable)
REASON_ALLOWED_OPEN_TEXT = "allowed_open_text"
REASON_ALLOWED_METADATA_ONLY = "allowed_metadata_only"
REASON_BLOCKED_DOMAIN = "blocked_domain"
REASON_UNKNOWN_DOMAIN_DEFAULT = "unknown_domain_default"
REASON_EMPTY_DOMAIN = "empty_domain"

_REGISTRY_CACHE: dict[str, Any] | None = None


def _config_dir() -> Path:
    return Path(__file__).resolve().parent / "config"


def load_source_registry(config_dir: Path | None = None) -> dict[str, Any]:
    """Load source_registry.yml; return { domains: { domain: { content_mode, trust_tier } }, default_content_mode }. Cached."""
    global _REGISTRY_CACHE
    if _REGISTRY_CACHE is not None:
        return _REGISTRY_CACHE
    base = config_dir or _config_dir()
    path = base / "source_registry.yml"
    data: dict[str, Any] = {"domains": {}, "default_content_mode": "metadata_only"}
    if path.exists() and yaml is not None:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        data["domains"] = dict(raw.get("domains") or {})
        data["default_content_mode"] = raw.get("default_content_mode") or "metadata_only"
    _REGISTRY_CACHE = data
    return _REGISTRY_CACHE


def _domain_from_url(url: str) -> str:
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def get_content_mode(url: str, config_dir: Path | None = None) -> str:
    """Return content_mode for URL's domain: open_text | metadata_only | blocked. Unknown -> default (metadata_only)."""
    mode, _ = get_policy_decision(url, config_dir)
    return mode


def get_policy_decision(url: str, config_dir: Path | None = None) -> tuple[str, str]:
    """
    Return (content_mode, reason_code). Unknown domains never get open_text.
    Reason codes: allowed_open_text, allowed_metadata_only, blocked_domain, unknown_domain_default, empty_domain.
    """
    reg = load_source_registry(config_dir)
    default = (reg.get("default_content_mode") or "metadata_only").strip().lower()
    if default not in _CONTENT_MODES:
        default = "metadata_only"
    domain = _domain_from_url(url)
    if not domain:
        return default, REASON_EMPTY_DOMAIN
    entry = reg["domains"].get(domain)
    if isinstance(entry, dict):
        mode = (entry.get("content_mode") or entry.get("fetch_policy") or "").strip().lower()
        if mode in _CONTENT_MODES:
            if mode == "open_text":
                return mode, REASON_ALLOWED_OPEN_TEXT
            if mode == "blocked":
                return mode, REASON_BLOCKED_DOMAIN
            return mode, REASON_ALLOWED_METADATA_ONLY
    if isinstance(entry, str):
        mode = entry.strip().lower()
        if mode in _CONTENT_MODES:
            if mode == "open_text":
                return mode, REASON_ALLOWED_OPEN_TEXT
            if mode == "blocked":
                return mode, REASON_BLOCKED_DOMAIN
            return mode, REASON_ALLOWED_METADATA_ONLY
    return default, REASON_UNKNOWN_DOMAIN_DEFAULT


def is_blocked(url: str, config_dir: Path | None = None) -> bool:
    """True if domain is blocked (do not fetch)."""
    return get_content_mode(url, config_dir) == "blocked"


def is_open_text(url: str, config_dir: Path | None = None) -> bool:
    """True if domain is allowed open_text fetch."""
    return get_content_mode(url, config_dir) == "open_text"


def invalidate_registry_cache() -> None:
    global _REGISTRY_CACHE
    _REGISTRY_CACHE = None
