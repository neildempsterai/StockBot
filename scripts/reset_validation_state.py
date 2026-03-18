#!/usr/bin/env python3
"""
Truncate validation/replay tables so release gate and replay run against isolated state.
Tables: signals, shadow_trades, scrappy_gate_rejections, symbol_intelligence_snapshots.
Uses DATABASE_URL from env (sync psycopg2 URL).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))


def _get_sync_url() -> str:
    """Return a DSN suitable for psycopg2.connect (postgresql://, no +driver)."""
    url = os.environ.get("DATABASE_URL", "postgresql://stockbot:stockbot@localhost:5432/stockbot")
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url.split("postgresql+asyncpg://", 1)[1]
    elif url.startswith("postgresql+psycopg2://"):
        url = "postgresql://" + url.split("postgresql+psycopg2://", 1)[1]
    return url


def main() -> int:
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 required: pip install psycopg2-binary", file=sys.stderr)
        return 1
    url = _get_sync_url()
    # Order: truncate tables that reference symbol_intelligence_snapshots first, then snapshots
    tables = ["signals", "shadow_trades", "scrappy_gate_rejections", "symbol_intelligence_snapshots"]
    try:
        conn = psycopg2.connect(url)
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                for t in tables:
                    cur.execute(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE")
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"reset_validation_state failed: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
