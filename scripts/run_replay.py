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
) -> tuple[dict, dict]:
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
    bars = _load_jsonl(session_dir / "bars.jsonl")
    quotes = _load_jsonl(session_dir / "quotes.jsonl")
    trades = _load_jsonl(session_dir / "trades.jsonl")
    news = _load_jsonl(session_dir / "news.jsonl")
    snapshots = _load_jsonl(session_dir / "scrappy_snapshots.jsonl")

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

    # Insert Scrappy snapshots
    factory = get_session_factory()
    for row in snapshots:
        ts = datetime.fromisoformat(row["snapshot_ts"].replace("Z", "+00:00"))
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

    # Push market events in order
    for b in bars:
        ts = datetime.fromisoformat(b["timestamp"].replace("Z", "+00:00"))
        await push_bar(
            redis_client,
            b["symbol"],
            b["o"],
            b["h"],
            b["l"],
            b["c"],
            b["v"],
            timestamp=ts,
        )
    for q in quotes:
        ts = datetime.fromisoformat(q["timestamp"].replace("Z", "+00:00"))
        await push_quote(redis_client, q["symbol"], q["bp"], q["ap"], timestamp=ts)
    for t in trades:
        ts = datetime.fromisoformat(t["timestamp"].replace("Z", "+00:00"))
        await push_trade(redis_client, t["symbol"], t["p"], timestamp=ts)
    for n in news:
        created = n.get("created_at")
        ts = (
            datetime.fromisoformat(created.replace("Z", "+00:00"))
            if created
            else datetime.now(timezone.UTC)
        )
        await push_news(
            redis_client,
            n.get("headline", ""),
            n.get("summary", ""),
            symbols=n.get("symbols", []),
            published_at=ts,
        )

    await redis_client.aclose()

    if not skip_worker:
        # Run worker in subprocess so we can stop after N seconds and then collect from DB
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
        try:
            proc.wait(timeout=worker_run_seconds)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
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
    parser.add_argument("--seconds", type=float, default=25.0, help="Worker run seconds")
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
