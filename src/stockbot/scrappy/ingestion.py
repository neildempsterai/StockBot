"""RSS ingestion: fetch feeds, normalize entries to candidates."""
from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

import feedparser

from stockbot.scrappy.dedup import normalize_url
from stockbot.scrappy.sources import load_scrappy_sources

logger = logging.getLogger(__name__)


def _parse_date(entry: Any) -> datetime | None:
    """Parse published/updated date from feed entry."""
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        val = getattr(entry, key, None)
        if val and isinstance(val, time.struct_time):
            try:
                return datetime(*val[:6], tzinfo=UTC)
            except Exception:
                pass
    return None


def _get_link(entry: Any) -> str:
    """Get canonical link from entry."""
    link = getattr(entry, "link", None) or ""
    if isinstance(link, str):
        return link.strip()
    return ""


def _get_title(entry: Any) -> str:
    title = getattr(entry, "title", None) or ""
    return (title.strip() if isinstance(title, str) else "")[:512]


def _get_summary(entry: Any) -> str:
    summary = getattr(entry, "summary", None) or getattr(entry, "description", None) or ""
    if isinstance(summary, str):
        return summary.strip()[:2000]
    return ""


def fetch_feed(url: str, source_name: str, timeout_sec: int = 15) -> list[dict[str, Any]]:
    """Fetch one RSS/Atom feed; return list of candidate dicts."""
    candidates: list[dict[str, Any]] = []
    try:
        # feedparser.parse() doesn't support timeout parameter - timeout is handled by underlying urllib
        # We can set it via request_headers or use a custom opener, but for now just remove timeout
        parsed = feedparser.parse(url, request_headers={"User-Agent": "StockBot-Scrappy/1.0"})
    except Exception as e:
        logger.warning("feed fetch failed url=%s error=%s", url[:80], e)
        return candidates
    if getattr(parsed, "bozo", False) and not getattr(parsed, "entries", None):
        logger.warning("feed parse error url=%s bozo=%s", url[:80], getattr(parsed, "bozo_exception", None))
        return candidates
    for entry in getattr(parsed, "entries", []) or []:
        link = _get_link(entry)
        if not link:
            continue
        published = _parse_date(entry)
        candidates.append({
            "url": link,
            "source_name": source_name,
            "source_type": "rss",
            "source_url": url,
            "published_at": published.isoformat() if published else None,
            "title": _get_title(entry),
            "summary": _get_summary(entry),
            "raw_metadata": {
                "feed_url": url,
                "entry_id": getattr(entry, "id", None),
                "author": getattr(entry, "author", None),
            },
        })
    return candidates


def collect_candidates_from_sources(
    symbols: list[str] | None = None,
    themes: list[str] | None = None,
    max_per_feed: int = 50,
) -> list[dict[str, Any]]:
    """
    Load enabled RSS sources, fetch each feed, return normalized candidates.
    Each candidate has: url, source_name, source_type, source_url, published_at, title, summary, raw_metadata.
    """
    cfg = load_scrappy_sources()
    sources = cfg.get("sources") or []
    # Filter sources by theme only (focus_tags describe source type e.g. filings, macro; not symbols)
    focus_tags = list(themes or [])
    all_candidates: list[dict[str, Any]] = []
    for s in sources:
        if not isinstance(s, dict) or not s.get("enabled", True):
            continue
        transport = (s.get("transport") or "").lower()
        if transport not in ("rss", "rss_or_api"):
            continue
        url = (s.get("url") or "").strip()
        if not url:
            continue
        stags = s.get("focus_tags") or []
        if stags and focus_tags:
            if not any(t in focus_tags for t in stags):
                continue
        name = (s.get("name") or "unknown").strip()
        candidates = fetch_feed(url, name)[:max_per_feed]
        for c in candidates:
            c["url"] = normalize_url(c.get("url") or "")
            if c["url"]:
                all_candidates.append(c)
    return all_candidates
