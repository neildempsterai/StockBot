#!/usr/bin/env python3
"""Write release gate report JSON and Markdown to artifacts/release_gate/."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--git-commit", default="n/a")
    p.add_argument("--migration-status", default="")
    p.add_argument("--db-test-passed", default="false")
    p.add_argument("--db-test-count", default="")
    p.add_argument("--replay-passed", default="false")
    p.add_argument("--replay-diff-status", default="")
    p.add_argument("--smoke-status", default="skipped")
    p.add_argument("--timestamp", default="")
    p.add_argument("--out-json", required=True)
    p.add_argument("--out-md", required=True)
    p.add_argument("--metrics-summary-json", default="", help="Optional path to metrics summary JSON")
    args = p.parse_args()

    db_passed = args.db_test_passed.lower() in ("true", "1", "yes")
    replay_passed = args.replay_passed.lower() in ("true", "1", "yes")

    data = {
        "git_commit": args.git_commit,
        "migration_status": args.migration_status,
        "db_test_passed": db_passed,
        "db_test_count": args.db_test_count or None,
        "replay_passed": replay_passed,
        "replay_diff_status": args.replay_diff_status or None,
        "smoke_status": args.smoke_status,
        "timestamp": args.timestamp,
        "release_gate_pass": (
            args.migration_status == "ok" and db_passed and replay_passed
            and args.smoke_status in ("ok", "skipped")
        ),
    }
    if args.metrics_summary_json and Path(args.metrics_summary_json).exists():
        with open(args.metrics_summary_json) as f:
            data["metrics_summary_snapshot"] = json.load(f)

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with out_json.open("w") as f:
        json.dump(data, f, indent=2)

    md_lines = [
        "# Release gate report",
        "",
        f"- **Git commit**: `{args.git_commit}`",
        f"- **Timestamp**: {args.timestamp}",
        "",
        "## Results",
        "",
        "| Step | Status |",
        "|------|--------|",
        f"| Migrations | {args.migration_status} |",
        f"| DB-backed tests | {'PASS' if db_passed else 'FAIL'} |",
        f"| Replay session_001 | {'PASS' if replay_passed else 'FAIL'} |",
        f"| Smoke UM790 | {args.smoke_status} |",
        "",
        f"**Release gate**: {'PASS' if data['release_gate_pass'] else 'FAIL'}",
        "",
        f"Report JSON: `{out_json.name}`",
    ]
    out_md = Path(args.out_md)
    with out_md.open("w") as f:
        f.write("\n".join(md_lines))


if __name__ == "__main__":
    main()
