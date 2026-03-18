"""
Scrappy dedup: canonical URL handling, time-bound re-crawl eligibility, and reason codes.
Port from Agent_Smith; same logic, market-intel context.
"""
from __future__ import annotations

import hashlib
import os
import re
from typing import Any

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

# Reason codes for every dropped candidate
DEDUP_ALREADY_SEEN_RECENT = "already_seen_recent"
DEDUP_ALREADY_SEEN_PERMANENT = "already_seen_permanent"
DEDUP_BLOCKED_POLICY = "blocked_policy"
DEDUP_JUNK_DOMAIN = "junk_domain"
DEDUP_OUT_OF_FOCUS = "out_of_focus"
DEDUP_DUPLICATE_IN_BATCH = "duplicate_in_batch"
DEDUP_MISSING_REQUIRED_METADATA = "missing_required_metadata"
DEDUP_SAME_CONTENT_HASH = "same_content_hash"

RECRAWL_DAYS_DEFAULT = 14
RECRAWL_DAYS_ENV = "SCRAPPY_DEDUP_RECRAWL_DAYS"
MIN_CANDIDATES_TO_PROCEED_DEFAULT = 1
MIN_CANDIDATES_ENV = "SCRAPPY_DEDUP_MIN_CANDIDATES"


def normalize_url(url: str) -> str:
    """
    Canonical URL for dedup: scheme+netloc+path normalized; optional query; no fragment.
    """
    if not url or not isinstance(url, str):
        return ""
    url = url.strip()
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        scheme = (parsed.scheme or "https").lower()
        netloc = (parsed.hostname or "").lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        path = (parsed.path or "/").rstrip("/") or "/"
        path = re.sub(r"/+", "/", path)
        query = parsed.query
        if query:
            qs = parse_qs(query, keep_blank_values=False)
            query = urlencode(sorted((k, v[0] if isinstance(v, list) and len(v) == 1 else v) for k, v in qs.items()))
        return urlunparse((scheme, netloc, path, parsed.params, query, ""))
    except Exception:
        return ""


def url_hash(url: str) -> str:
    """Stable 32-char hash for scrappy_urls key."""
    canonical = normalize_url(url)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


_JUNK_PATTERNS = [
    r"facebook\.com",
    r"twitter\.com",
    r"linkedin\.com",
    r"youtube\.com",
    r"instagram\.com",
    r"t\.co",
    r"bit\.ly",
    r"goo\.gl",
    r"amazon\.(com|co\.uk)",
    r"ebay\.com",
    r"wikipedia\.org",
    r"reddit\.com",
    r"login\.",
    r"accounts\.google",
    r"marktechpost\.com",
    r"notion\.so",
]


def is_junk_domain(url: str) -> bool:
    """True if URL host matches known junk/off-topic patterns."""
    try:
        host = (urlparse(url).hostname or "").lower()
        for pat in _JUNK_PATTERNS:
            if re.search(pat, host):
                return True
        return False
    except Exception:
        return True


def get_dedup_recrawl_days() -> int:
    """Days after which a URL may be re-eligible for fetch."""
    try:
        return max(1, int(os.getenv(RECRAWL_DAYS_ENV, str(RECRAWL_DAYS_DEFAULT))))
    except ValueError:
        return RECRAWL_DAYS_DEFAULT


def get_min_candidates_to_proceed() -> int:
    """Minimum post-dedup candidate count to run fetch loop."""
    try:
        return max(0, int(os.getenv(MIN_CANDIDATES_ENV, str(MIN_CANDIDATES_TO_PROCEED_DEFAULT))))
    except ValueError:
        return MIN_CANDIDATES_TO_PROCEED_DEFAULT


def filter_candidates_with_reasons(
    candidates: list[dict[str, Any]],
    url_seen_fn: Any,
    url_seen_recent_fn: Any,
    policy_blocked_fn: Any,
    junk_fn: Any,
    recrawl_eligible_fn: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Apply policy + dedup; return (eligible_candidates, drop_reasons).
    Each drop has {"url", "reason"}.
    """
    seen_in_batch: set[str] = set()
    eligible: list[dict[str, Any]] = []
    drop_reasons: list[dict[str, Any]] = []
    for r in candidates:
        url = (r.get("url") or "").strip()
        if not url:
            drop_reasons.append({"url": url, "reason": DEDUP_MISSING_REQUIRED_METADATA})
            continue
        canonical = normalize_url(url)
        if canonical in seen_in_batch:
            drop_reasons.append({"url": url, "reason": DEDUP_DUPLICATE_IN_BATCH})
            continue
        seen_in_batch.add(canonical)
        if junk_fn(url):
            drop_reasons.append({"url": url, "reason": DEDUP_JUNK_DOMAIN})
            continue
        if policy_blocked_fn(url, r):
            drop_reasons.append({"url": url, "reason": DEDUP_BLOCKED_POLICY})
            continue
        seen = url_seen_fn(url)
        if seen:
            if recrawl_eligible_fn(url):
                eligible.append(r)
            else:
                drop_reasons.append({"url": url, "reason": DEDUP_ALREADY_SEEN_PERMANENT})
            continue
        eligible.append(r)
    return eligible, drop_reasons
