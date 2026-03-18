# Scrappy in StockBot — Implementation Summary

Scrappy is a **market-intel sidecar** for StockBot: it ingests from configured sources (RSS, optional APIs), applies source policy and deduplication, produces structured market-intel notes, persists them idempotently, and exposes truthful telemetry and audit. It **does not** replace live market data, quote engine, or order routing.

## What Was Built (v1 + hardening)

- **Source registry and policy**: `source_registry.yml` (domain → content_mode, source_name, source_class, fetch_policy). `get_policy_decision(url)` returns (content_mode, reason_code). Unknown domains default to **metadata_only** (never open_text). Every candidate gets policy_decision and policy_reason_code; metadata_only/blocked never trigger full-text fetch.
- **RSS ingestion**: `ingestion.py` — load enabled sources from `scrappy_sources.yml`, fetch feeds via feedparser, normalize entries to candidates (source_name, source_url, published_at, title, summary, url, raw_metadata). Real feed URLs for SEC EDGAR, Federal Reserve, BLS, Yahoo Finance, Benzinga.
- **Dedup and idempotency**: Canonical URL normalization and `url_hash`; `dedup_hash` (sha256(normalized_url|published_at)) for notes; idempotent note insert by `dedup_hash`; URL-seen check via `scrappy_urls` so repeated runs do not create duplicate notes.
- **Structured note generation**: `notes.py` — build note from candidate, content_mode from candidate policy_decision, validate catalyst_type / sentiment_label / impact_horizon; symbol extraction conservative; schema validation before persist; LLM draft uses strict JSON only.
- **Run path**: create run → collect candidates → apply policy to every candidate (policy_decision, policy_reason_code) → drop blocked → URL dedup → open_text fetch only when policy=open_text and env enabled → build & validate note → optional LLM draft (strict JSON) → idempotent insert → finish run with counters and computed outcome_code.
- **Outcome codes** (computed from actual counters): success_useful_output, success_candidates_but_no_notes, success_all_deduped, success_all_blocked_or_metadata_only_no_output, no_new_candidate_urls, partial_output_note_rejections, failed_source_fetch, failed_note_validation, failed_persistence, failed_internal_error.
- **Truthful API**: GET /scrappy/health, /scrappy/telemetry, /scrappy/sources/health (with per-source last_attempt_at, last_success_at, attempt_count, success_count, failure_count), /scrappy/audit, GET /scrappy/notes/recent, GET/POST /scrappy/watchlist, POST /scrappy/run, POST /scrappy/run/watchlist (uses watchlist_symbols table), POST /scrappy/run/symbol/{symbol}.
- **Watchlist**: Table `watchlist_symbols` (symbol, added_at, source); GET /scrappy/watchlist returns symbols; POST /scrappy/watchlist?symbol=X adds symbol; POST /scrappy/run/watchlist runs with those symbols.
- **Optional open_text fetch**: Default off. When `SCRAPPY_OPEN_TEXT_FETCH_ENABLED=true` and policy=open_text only, fetch via `fetch_content.fetch_full_text_result()`; metadata_only/blocked never fetch.
- **LLM note drafting**: Default off. When `SCRAPPY_LLM_NOTE_DRAFT_ENABLED=true`, router returns JSON only (summary, why_this_matters); malformed output is rejected and payload stays deterministic.
- **Per-source health**: fetch_success_count, fetch_failure_count, notes_inserted_count (fetch success tracked separately from note yield); last_error_code, last_error_message. GET /scrappy/sources/health returns all fields.
- **DB**: Migration 003, 005. **Migration 006**: run counters (policy_blocked_count, metadata_only_count, open_text_count, notes_attempted_count, notes_rejected_count) and source health (fetch_success_count, fetch_failure_count, candidate_count, post_dedup_count, notes_inserted_count, last_error_code, last_error_message).

## Source Policy Behaviour

- **open_text**: may fetch full article (not used by default in registry; all listed domains are metadata_only or blocked).
- **metadata_only**: only feed/summary and metadata; note records content_mode=metadata_only; never triggers full-text fetch.
- **blocked**: do not fetch; drop from run; reason code (e.g. blocked_domain) recorded.
- Unknown domains → **metadata_only** (never open_text by default).

## Data Model Additions

- **market_intel_notes**: content_mode, dedup_hash (unique), why_this_matters, impact_horizon.
- **scrappy_runs**: run_scope (JSONB), errors (text), policy_blocked_count, metadata_only_count, open_text_count, notes_attempted_count, notes_rejected_count (migration 006).

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /scrappy/health | Service health |
| GET | /scrappy/telemetry | Runs, notes_total, zero_yield_streak (from DB) |
| GET | /scrappy/sources/health | Configured/enabled sources |
| GET | /scrappy/audit | Last N runs with full audit fields |
| GET | /scrappy/notes/recent | Recent notes; params: limit, symbol, catalyst_type, sentiment_label, content_mode, since_hours |
| GET | /scrappy/watchlist | List watchlist symbols |
| POST | /scrappy/watchlist | Add symbol (validated: non-empty, alphanumeric; query param symbol=) |
| POST | /scrappy/run | Trigger run (run_type, symbols, themes) |
| POST | /scrappy/run/watchlist | Run with symbols from watchlist_symbols table |
| POST | /scrappy/run/symbol/{symbol} | Run for one symbol |

## Env / Config

- **Database**: Same as StockBot; `DATABASE_URL` (Postgres async).
- **Source config**: `src/stockbot/scrappy/config/scrappy_sources.yml` (sources with url, name, transport, focus_tags).
- **Registry**: `src/stockbot/scrappy/config/source_registry.yml` (domains → content_mode, trust_tier).
- **Model/LLM**: Router in `scrappy_router.yml`; env `SCRAPPY_ROUTER_*`, `SCRAPPY_LLM_NOTE_DRAFT_ENABLED` (optional). When enabled, `structured_note_draft` refines summary and why_this_matters.
- **Open-text fetch**: `SCRAPPY_OPEN_TEXT_FETCH_ENABLED` (default off). When true and policy=open_text only, full-article fetch via `fetch_content.fetch_full_text_result()`. metadata_only/blocked never fetch.

## Run Commands

```bash
# Migrations (from repo root, DATABASE_URL set)
alembic upgrade head

# API (includes /scrappy)
uvicorn api.main:app --reload

# Unit tests (PYTHONPATH=src or install -e .)
pytest tests/test_scrappy_dedup.py tests/test_scrappy_schema.py tests/test_scrappy_sources.py tests/test_scrappy_registry_policy.py tests/test_scrappy_notes.py tests/test_scrappy_run_outcome.py -v

# API tests (require DATABASE_URL for async DB)
pytest tests/test_scrappy_api.py -v
```

## Test Commands

```bash
pytest tests/test_scrappy_*.py -v
# E2E (DATABASE_URL Postgres): run → notes → repeat run → no duplicate notes
pytest tests/test_scrappy_e2e.py -v
```

## Known Limitations

- **Premarket**: No premarket/session concept wired; not added.
- **Open-text fetch**: Disabled by default; enable with `SCRAPPY_OPEN_TEXT_FETCH_ENABLED`. Only domains explicitly set to open_text in source_registry.yml are fetched.
- **LLM**: Disabled by default; set `SCRAPPY_LLM_NOTE_DRAFT_ENABLED=true` and configure OLLAMA_CHAT_URL or OPENROUTER_API_KEY for structured_note_draft.

## What Scrappy Does Not Do

- Does **not** replace live market data or quote engine.
- Does **not** scrape prices or use scraped prices as buy/sell triggers.
- Does **not** place or cancel orders.
- Does **not** become the sole basis of entry/exit; manual execution only; Scrappy enriches context and explainability only.
