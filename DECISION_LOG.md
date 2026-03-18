# Decision Log

## 2026-03-17 — Freeze v0.1 integrations to Alpaca + Tailscale SSH
Status: Accepted

Decision:
- Alpaca is the sole v0.1 provider for US equities market data and paper trading.
- Runtime uses Alpaca direct APIs only; no Alpaca MCP runtime integration.
- One internal market-data gateway owns the Alpaca stock stream and fans out internally.
- One separate trade gateway owns Alpaca paper `trade_updates`.
- REST latest/snapshot/historical endpoints are recovery/reconciliation tools, not the primary live data path.
- `client_order_id` must equal the bot signal UUID for idempotency and auditability.
- Internal fills/positions ledger is canonical; Alpaca-reported average entry price is informational only.
- Deployment to the UM790 is SSH-only over Tailscale using Docker contexts; no public Docker daemon exposure.
- v0.1 trading scope is regular-hours only; extended-hours and 24/5 are disabled.

## 2026-03-17 — Scrappy as market-intel sidecar (v1)
Status: Accepted

Decision:
- Scrappy in StockBot is a **market-intel sidecar** only: filings, macro, earnings/guidance signals, IR/news context, catalyst detection, “why is this moving?” context. It does **not** replace live market data or execution logic.
- Source policy: unknown domains default to **metadata_only**; never open_text by default. Blocked domains are not fetched; every drop/downgrade has a reason code.
- Structured **market_intel_note** contract is enforced: required fields (source_url, source_name, dedup_hash, content_mode, catalyst_type, sentiment_label, etc.); validation before persist; metadata_only notes must not be presented as full-article reads.
- Telemetry and audit must be **truthful**: read from DB (scrappy_runs, note counts); report actual run counts, outcome_code, zero-yield streak; audit shows candidate_url_count, post_dedup_count, notes_created, mismatch, errors.
- Current tranche accepted only when end-to-end path is proven: real run creates run row, inserts notes idempotently, repeated run does not duplicate notes.

## 2026-03-17 — Scrappy hardening (backend beta)
Status: Accepted

Decision:
- Source policy: every candidate gets policy_decision and policy_reason_code; unknown domains remain metadata_only (never open_text); metadata_only and blocked never trigger full-text fetch.
- LLM drafted note enrichment must use strict JSON validation (summary, why_this_matters); malformed output is rejected and payload remains deterministic.
- Source fetch success is tracked separately from note yield (fetch_success_count, fetch_failure_count, notes_inserted_count).
- Scrappy remains a market-intel sidecar and does not replace live market data or execution logic.
- Run outcome codes are computed from actual counters; audit and telemetry reflect real run data from DB.

## 2026-03-17 — Next milestone is first working shadow strategy
Status: Accepted

Decision:
- Stop adding scaffolding.
- Implement `INTRA_EVENT_MOMO / 0.1.0` as the first end-to-end vertical slice.
- Scheduled strategy runs remain shadow-only.
- Manual paper-order endpoints may remain for testing, but strategy automation must not place paper orders in v0.1.

## 2026-03-18 — Scrappy hardening accepted; next milestone is strategy bridge
Status: Accepted

Context:
- Scrappy migration path is verified through current head.
- Scrappy live symbol runs complete successfully.
- Duplicate-run behavior and no-duplicate-note behavior are verified.
- Telemetry, audit, source health, and recent notes endpoints return stable shapes.

Decision:
- Freeze Scrappy as the market-intelligence subsystem for StockBot.
- Stop spending the next cycle on Scrappy hardening except for defects.
- Build a bounded bridge from Scrappy outputs to deterministic strategy evaluation.
- Scrappy remains advisory only and cannot create executable trade signals.
- Every strategy signal that uses Scrappy must persist the exact Scrappy snapshot used at signal time.

Consequences:
- Next implementation focus is intelligence snapshot persistence, worker lookup, gating rules, and attribution metrics.
- DB-backed Scrappy e2e tests remain important but are not the next product milestone unless they block deployment.

## 2026-03-18 — Freeze feature expansion; next milestone is end-to-end validation
Status: Accepted

Context:
- Scrappy intelligence snapshots, worker gating, attribution, API, UI, and migrations are now implemented.
- Remaining gaps are integration proof, not capability gaps.

Decision:
- Stop adding new strategy features in the next cycle.
- Build DB/Redis-backed end-to-end tests for Scrappy-gated signals and shadow trades.
- Add a repeatable staging smoke run on the UM790 using Docker over Tailscale SSH.
- Treat this as the validation gate before any further strategy expansion.

Consequences:
- Next work is test harness, e2e fixtures, smoke-run scripts, and operational verification.
- New features are deferred unless a defect is found during validation.

## 2026-03-18 — Next milestone is deterministic replay validation
Status: Accepted

Context:
- Scrappy bridge, worker gating, attribution, DB-backed tests, and smoke path are implemented.
- Remaining uncertainty is reproducibility across a fixed event sequence and release-to-release drift.

Decision:
- Freeze new feature work for the next cycle.
- Add a deterministic replay pack for one fixed market session.
- Use replay results as the main regression gate before expanding strategy scope or enabling stricter Scrappy modes.
- A build is not accepted unless replay outputs are stable for signals, rejections, shadow trades, and attribution metrics.

Consequences:
- Next work is fixture capture, replay runner, golden outputs, and a release acceptance checklist.
- Strategy expansion is deferred until replay stability is proven.

## 2026-03-18 — Next milestone is Docker-native release validation
Status: Accepted

Context:
- The release gate, replay pack, and smoke path are implemented.
- Remaining friction is environment inconsistency and residual runtime-path test failures.
- The target deployment model is Docker on the UM790 over Tailscale SSH.

Decision:
- Make the release gate fully Docker-native.
- Standardize validation on async Postgres + Redis only.
- Remove SQLite assumptions from runtime-adjacent tests.
- Clean the lint/type/test surface for files in the release path.

Consequences:
- Next work is validation containerization, test-environment unification, and core-path cleanup.
- New feature work remains frozen until the release gate runs in one command without host Python setup.

## 2026-03-18 — Release gate must run against isolated state
Status: Accepted

Context:
- Docker-native release gate now runs.
- Remaining failure is caused by replay/test assumptions running against shared Postgres state from earlier runs.

Decision:
- Release-gate and replay validation must use isolated DB state per run.
- Tests must not depend on pre-existing signals, trades, or intelligence rows.
- Do not weaken deterministic replay assertions to tolerate shared-state contamination.

Consequences:
- Next implementation is per-run DB isolation or reset for validation.
- Replay outputs become trustworthy release artifacts.
