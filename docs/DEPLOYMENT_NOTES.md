# Deployment notes

## v0.1.0-validated (2026-03-18)

**Tag:** `v0.1.0-validated`  
**Message:** Validated baseline: replay deterministic, Docker-native release gate pass

**Release-gate artifacts (archived with this tag):**

- `artifacts/release_gate/report_20260318_081607.json`
- `artifacts/release_gate/report_20260318_081607.md`

To reproduce: `git checkout v0.1.0-validated && make release-gate-docker`. Reports are written to `artifacts/release_gate/` (gitignored; copy into versioned storage if needed).

**Baseline state:**

- Migrations: ok
- DB-backed tests: pass (47 selected)
- Replay session_001: outputs match expected_outputs.json (1 signal AAPL, 0 shadow trades)
- Smoke: skipped (run separately via `make smoke-um790`)
