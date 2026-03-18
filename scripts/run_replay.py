#!/usr/bin/env python3
"""
Deterministic replay runner: load session_001, push to Redis/DB, run worker, compare to golden.
Exit 0 if outputs match expected_outputs.json; non-zero and diff on mismatch.
Requires: DATABASE_URL, REDIS_URL, ALPACA_API_KEY_ID, ALPACA_API_SECRET_KEY.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Repo root; src for app imports, repo root for tests.helpers.replay
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

# Scrappy mode for replay
os.environ.setdefault("SCRAPPY_MODE", "advisory")


def _load_jsonl(path: Path) -> list[dict]:
    out = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _load_json(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# Deterministic order when timestamps tie: news before quote before trade before bar
# so quotes/news are available before the bar that triggers evaluation.
EVENT_TYPE_PRIORITY = {"news": 0, "quote": 1, "trade": 2, "bar": 3}


def build_merged_timeline(session_dir: Path) -> list[tuple[datetime, int, str, dict]]:
    """Merge bars, quotes, trades, news from session dir into one list sorted by (ts, type_priority)."""
    bars = _load_jsonl(session_dir / "bars.jsonl")
    quotes = _load_jsonl(session_dir / "quotes.jsonl")
    trades = _load_jsonl(session_dir / "trades.jsonl")
    news = _load_jsonl(session_dir / "news.jsonl")
    events: list[tuple[datetime, int, str, dict]] = []
    for b in bars:
        ts = _parse_ts(b["timestamp"])
        events.append((ts, EVENT_TYPE_PRIORITY["bar"], "bar", b))
    for q in quotes:
        ts = _parse_ts(q["timestamp"])
        events.append((ts, EVENT_TYPE_PRIORITY["quote"], "quote", q))
    for t in trades:
        ts = _parse_ts(t["timestamp"])
        events.append((ts, EVENT_TYPE_PRIORITY["trade"], "trade", t))
    for n in news:
        created = n.get("created_at")
        ts = _parse_ts(created) if created else datetime.now(timezone.UTC)
        events.append((ts, EVENT_TYPE_PRIORITY["news"], "news", n))
    events.sort(key=lambda e: (e[0], e[1]))
    return events


async def _push_timeline_event(
    redis_client: Any,
    event: tuple[datetime, int, str, dict],
    push_bar_fn: Any,
    push_quote_fn: Any,
    push_trade_fn: Any,
    push_news_fn: Any,
) -> None:
    _ts, _pri, typ, payload = event
    if typ == "bar":
        await push_bar_fn(
            redis_client,
            payload["symbol"],
            payload["o"],
            payload["h"],
            payload["l"],
            payload["c"],
            payload["v"],
            timestamp=_ts,
        )
    elif typ == "quote":
        await push_quote_fn(
            redis_client,
            payload["symbol"],
            payload["bp"],
            payload["ap"],
            timestamp=_ts,
        )
    elif typ == "trade":
        await push_trade_fn(
            redis_client,
            payload["symbol"],
            payload["p"],
            timestamp=_ts,
        )
    elif typ == "news":
        await push_news_fn(
            redis_client,
            payload.get("headline", ""),
            payload.get("summary", ""),
            symbols=payload.get("symbols", []),
            published_at=_ts,
        )


async def _is_validation_db_dirty() -> tuple[bool, dict[str, int]]:
    """Return (is_dirty, counts) for signals, shadow_trades, scrappy_gate_rejections, symbol_intelligence_snapshots."""
    from sqlalchemy import text
    from stockbot.db.session import get_session_factory

    tables = ["signals", "shadow_trades", "scrappy_gate_rejections", "symbol_intelligence_snapshots"]
    counts = {}
    factory = get_session_factory()
    async with factory() as session:
        for t in tables:
            r = await session.execute(text(f"SELECT COUNT(*) FROM {t}"))
            counts[t] = r.scalar() or 0
    is_dirty = any(c > 0 for c in counts.values())
    return is_dirty, counts


async def _run(
    session_dir: Path,
    worker_run_seconds: float = 25.0,
    skip_worker: bool = False,
    allow_dirty: bool = False,
    debug_timeline: bool = False,
    debug_timeline_n: int = 30,
) -> tuple[dict, dict]:
    import time
    import redis.asyncio as redis
    from tests.helpers.replay import push_bar, push_news, push_quote, push_trade

    from stockbot.db.session import get_session_factory
    from stockbot.ledger.store import LedgerStore
    from stockbot.scrappy.store import get_gate_rejection_counts, insert_intelligence_snapshot

    if not allow_dirty:
        is_dirty, counts = await _is_validation_db_dirty()
        if is_dirty:
            print(
                "Replay requires clean validation state. Current row counts: "
                + ", ".join(f"{k}={v}" for k, v in counts.items()),
                file=sys.stderr,
            )
            print("Run scripts/reset_validation_state.py or pass --allow-dirty to override.", file=sys.stderr)
            sys.exit(1)

    metadata = _load_json(session_dir / "metadata.json")
    expected = _load_json(session_dir / "expected_outputs.json")
    snapshots = _load_jsonl(session_dir / "scrappy_snapshots.jsonl")
    timeline = build_merged_timeline(session_dir)

    if debug_timeline:
        n = min(debug_timeline_n, len(timeline))
        for i, (ts, _pri, typ, payload) in enumerate(timeline[:n]):
            sym = payload.get("symbol", payload.get("symbols", ["-"])[0] if payload.get("symbols") else "-")
            if isinstance(sym, list):
                sym = sym[0] if sym else "-"
            print(f"  {i+1}. {ts.isoformat()} {typ} {sym}", file=sys.stderr)
        print(f"  ... (showing first {n} of {len(timeline)} events)", file=sys.stderr)

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    redis_client = redis.from_url(redis_url, decode_responses=True)

    # Clear stream keys so worker reads from start (replay deterministic)
    for key in [
        "alpaca:market:bars",
        "alpaca:market:quotes",
        "alpaca:market:trades",
        "alpaca:market:news",
    ]:
        with contextlib.suppress(Exception):
            await redis_client.delete(key)
    with contextlib.suppress(Exception):
        await redis_client.delete("stockbot:worker:intra_event_momo:last_ids")
        await redis_client.delete("stockbot:strategies:intra_event_momo:traded_today")

    # Insert Scrappy snapshots (available before any stream events)
    factory = get_session_factory()
    for row in snapshots:
        ts = _parse_ts(row["snapshot_ts"])
        async with factory() as session:
            await insert_intelligence_snapshot(
                session,
                symbol=row["symbol"],
                snapshot_ts=ts,
                freshness_minutes=row.get("freshness_minutes", 30),
                catalyst_direction=row["catalyst_direction"],
                catalyst_strength=50,
                sentiment_label=row.get("catalyst_direction", "neutral"),
                evidence_count=1,
                source_count=1,
                source_domains_json=["replay"],
                thesis_tags_json=[],
                headline_set_json=[],
                stale_flag=row.get("stale_flag", False),
                conflict_flag=row.get("conflict_flag", False),
                raw_evidence_refs_json=[],
                scrappy_run_id="replay-session_001",
                scrappy_version="0.1.0",
            )

    proc = None
    if not skip_worker:
        # Start worker before feeding events so it sees them in order
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        env.setdefault("SCRAPPY_MODE", "advisory")
        proc = subprocess.Popen(
            [sys.executable, "-m", "worker.main"],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await asyncio.sleep(3)  # worker startup / first xread block

    # Feed events in strict timestamp+priority order. Use a delay between events so the worker's
    # xread (which reads all streams) sees at most one event type at a time and processes in order.
    feed_start = time.monotonic()
    inter_event_delay = 1.2 if not skip_worker else 0.0
    for ev in timeline:
        await _push_timeline_event(redis_client, ev, push_bar, push_quote, push_trade, push_news)
        if not skip_worker and inter_event_delay > 0:
            await asyncio.sleep(inter_event_delay)
    await redis_client.aclose()

    if not skip_worker and proc is not None:
        elapsed = time.monotonic() - feed_start
        remaining = worker_run_seconds - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        await asyncio.sleep(1)  # allow DB commits to settle

    # Collect outputs from DB
    async with factory() as session:
        store = LedgerStore(session)
        signals = await store.get_signals(limit=100)
        shadow_trades = await store.list_shadow_trades(limit=100)
        rejection_counts = await get_gate_rejection_counts(session)

    signal_symbols = sorted([s.symbol for s in signals])
    signal_sides = sorted([s.side for s in signals])
    shadow_symbols = sorted([t.symbol for t in shadow_trades])
    with_snapshot = sum(1 for s in signals if getattr(s, "intelligence_snapshot_id", None))
    without_snapshot = len(signals) - with_snapshot

    actual = {
        "replay_version": metadata.get("replay_version", "0.1.0"),
        "signal_count": len(signals),
        "signal_symbols": signal_symbols,
        "signal_sides": signal_sides,
        "rejection_counts_by_reason": dict(rejection_counts),
        "shadow_trade_count": len(shadow_trades),
        "shadow_trade_symbols": shadow_symbols,
        "accepted_with_snapshot_count": with_snapshot,
        "accepted_without_snapshot_count": without_snapshot,
        "attribution_summary": {
            "signals_total": len(signals),
            "signals_with_scrappy_snapshot": with_snapshot,
            "signals_without_scrappy_snapshot": without_snapshot,
        },
        "metrics_summary_subset": {
            "signals_total": len(signals),
            "shadow_trades_total": len(shadow_trades),
        },
    }
    return actual, expected


def _diff(actual: dict, expected: dict) -> list[str]:
    lines = []
    for k in expected:
        a = actual.get(k)
        e = expected[k]
        if k in ("signal_symbols", "signal_sides", "shadow_trade_symbols") and isinstance(e, list):
            if sorted(a or []) != sorted(e):
                lines.append(f"  {k}: expected {sorted(e)!r} got {sorted(a or [])!r}")
        elif isinstance(e, dict) and isinstance(a, dict):
            for subk, sube in e.items():
                suba = a.get(subk)
                if suba != sube:
                    lines.append(f"  {k}.{subk}: expected {sube!r} got {suba!r}")
        elif a != e:
            lines.append(f"  {k}: expected {e!r} got {a!r}")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Run replay and compare to golden outputs")
    parser.add_argument("--session", default="replay/session_001", help="Path to session dir")
    parser.add_argument("--seconds", type=float, default=35.0, help="Worker run seconds (after event feed)")
    parser.add_argument(
        "--skip-worker", action="store_true", help="Only load data, do not run worker"
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Run even if validation tables already have rows (not deterministic)",
    )
    parser.add_argument(
        "--reset-state",
        action="store_true",
        help="Run reset_validation_state.py before replay",
    )
    parser.add_argument(
        "--debug-timeline",
        action="store_true",
        help="Print first N replay events in order to stderr",
    )
    parser.add_argument(
        "--debug-timeline-n",
        type=int,
        default=30,
        help="Number of timeline events to print when --debug-timeline (default 30)",
    )
    parser.add_argument("--output", help="Write actual output JSON to file")
    args = parser.parse_args()
    session_dir = REPO_ROOT / args.session
    if not session_dir.is_dir():
        print(f"Session dir not found: {session_dir}", file=sys.stderr)
        return 1
    if args.reset_state:
        r = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "reset_validation_state.py")],
            cwd=str(REPO_ROOT),
            env=os.environ,
        )
        if r.returncode != 0:
            return r.returncode
    actual, expected = asyncio.run(
        _run(
            session_dir,
            worker_run_seconds=args.seconds,
            skip_worker=args.skip_worker,
            allow_dirty=args.allow_dirty,
            debug_timeline=args.debug_timeline,
            debug_timeline_n=args.debug_timeline_n,
        )
    )
    if args.output:
        with open(args.output, "w") as f:
            json.dump(actual, f, indent=2)
    if args.skip_worker:
        # Skip-worker run is for testing zero-signals; do not diff against full-run golden.
        print("Replay OK (--skip-worker): output written, no diff vs expected_outputs.json")
        return 0
    diffs = _diff(actual, expected)
    if diffs:
        print("Replay output mismatch:", file=sys.stderr)
        for line in diffs:
            print(line, file=sys.stderr)
        return 1
    print("Replay OK: outputs match expected_outputs.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
