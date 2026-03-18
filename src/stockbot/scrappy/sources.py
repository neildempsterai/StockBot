"""
Scrappy source config: load market-intel sources (official + media) and search/dedup rules.
Retargeted from FM focus_tags to symbol/theme/sector.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

_CACHE: dict[str, Any] | None = None


def _config_dir() -> Path:
    return Path(__file__).resolve().parent / "config"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    if yaml is None:
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_scrappy_sources(config_dir: Path | None = None) -> dict[str, Any]:
    """Load scrappy_sources.yml; return { sources, search, watchlist_rules, dedup, extraction }. Cached."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    base = config_dir or _config_dir()
    data = _load_yaml(base / "scrappy_sources.yml")
    _CACHE = {
        "sources": list(data.get("sources") or []),
        "search": dict(data.get("search") or {}),
        "watchlist_rules": dict(data.get("watchlist_rules") or {}),
        "dedup": dict(data.get("dedup") or {}),
        "extraction": dict(data.get("extraction") or {}),
    }
    return _CACHE


def get_enabled_rss_feeds(config_dir: Path | None = None) -> list[str]:
    """Return list of enabled RSS feed URLs from config (transport rss or rss_or_api)."""
    cfg = load_scrappy_sources(config_dir)
    out: list[str] = []
    for s in cfg.get("sources") or []:
        if not isinstance(s, dict):
            continue
        if not s.get("enabled", True):
            continue
        transport = (s.get("transport") or "").lower()
        if transport not in ("rss", "rss_or_api"):
            continue
        url = (s.get("url") or "").strip()
        if url:
            out.append(url)
    return out


def get_search_config(config_dir: Path | None = None) -> dict[str, Any]:
    """Return search config: enabled_for_low_confidence, threshold, max_queries, max_results, preferred_domains, query_templates."""
    cfg = load_scrappy_sources(config_dir)
    search = cfg.get("search") or {}
    return {
        "enabled_for_low_confidence": bool(search.get("enabled_for_low_confidence", True)),
        "confidence_threshold": float(search.get("confidence_threshold", 0.65)),
        "max_queries_per_sprint": int(search.get("max_queries_per_sprint", 6)),
        "max_results_per_query": int(search.get("max_results_per_query", 8)),
        "preferred_domains": list(search.get("preferred_domains") or []),
        "query_templates": list(search.get("query_templates") or []),
    }


def get_sources_for_symbols_or_themes(
    symbol_tags: list[str] | None = None,
    theme_tags: list[str] | None = None,
    config_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Return enabled sources that apply to these symbol/theme tags (focus_tags in config)."""
    cfg = load_scrappy_sources(config_dir)
    focus_tags = list(symbol_tags or []) + list(theme_tags or [])
    out: list[dict[str, Any]] = []
    for s in cfg.get("sources") or []:
        if not isinstance(s, dict) or not s.get("enabled", True):
            continue
        stags = s.get("focus_tags") or []
        if stags and focus_tags:
            if not any(t in focus_tags for t in stags):
                continue
        out.append(dict(s))
    return out


def invalidate_cache() -> None:
    """Clear cache (e.g. for tests)."""
    global _CACHE
    _CACHE = None
