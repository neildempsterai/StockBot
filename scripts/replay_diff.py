#!/usr/bin/env python3
"""
Compare two replay output JSON files and print human-readable diff.
Use after run_replay.py --output actual.json to compare actual vs expected or two runs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def diff(a: dict, b: dict, prefix: str = "") -> list[str]:
    lines = []
    all_keys = sorted(set(a.keys()) | set(b.keys()))
    for k in all_keys:
        va = a.get(k)
        vb = b.get(k)
        key_path = f"{prefix}.{k}" if prefix else k
        if isinstance(va, dict) and isinstance(vb, dict):
            lines.extend(diff(va, vb, key_path))
        elif va != vb:
            lines.append(f"  {key_path}:")
            lines.append(f"    a: {va!r}")
            lines.append(f"    b: {vb!r}")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Diff two replay output JSON files")
    parser.add_argument("a", help="First output JSON path")
    parser.add_argument("b", help="Second output JSON path")
    args = parser.parse_args()
    pa = Path(args.a)
    pb = Path(args.b)
    if not pa.exists():
        print(f"File not found: {pa}", file=sys.stderr)
        return 1
    if not pb.exists():
        print(f"File not found: {pb}", file=sys.stderr)
        return 1
    da = load(pa)
    db = load(pb)
    lines = diff(da, db)
    if not lines:
        print("No differences.")
        return 0
    print("Differences:")
    for line in lines:
        print(line)
    return 1


if __name__ == "__main__":
    sys.exit(main())
