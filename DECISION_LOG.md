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
