# Paper Trading Operator Runbook

Safe operation of paper trading during market hours. Repo as source of truth.

---

## 1. How to disarm paper immediately

**Without restart (recommended):**

```bash
curl -X POST "${BASE_URL:-http://localhost:8000}/v1/paper/disarm"
```

Response: `{"armed": false, "message": "Paper trading disarmed. No paper orders will be submitted until re-armed."}`

**With restart:** Set `PAPER_TRADING_ARMED=false` (or omit / set to 0) in `.env` and restart API and worker. Redis key `stockbot:paper:armed` will still be 0 until the next arm; if you only change env to false, effective armed is false (config and Redis both required to be armed).

---

## 2. How to identify if an order came from strategy_paper or operator_test

- **GET /v1/orders** — Each order has `order_source`: `strategy_paper` | `operator_test` | `legacy_unknown` (and `order_origin` / `order_intent`).
- **GET /v1/paper/exposure** — Each position has `source` with the same values and `operator_intent` when source is `operator_test`.
- **DB:** `PaperOrder.order_origin` is `"strategy"` (strategy_paper) or `"operator_test"`; `order_intent` is e.g. `buy_open`, `sell_close`, `short_open`, `buy_cover` for operator test.

---

## 3. How to inspect whether a position is managed or orphaned

- **GET /v1/paper/exposure** — Each position has:
  - `orphaned`: true if no known provenance (`source == "legacy_unknown"`) or no live exit plan (when Phase 3 exit plan is persisted, this will reflect missing plan).
  - `exit_plan_status`: `"not_persisted"` until exit plans are stored at entry; then e.g. `active` / `closed`.
  - `broker_protection`: `"unknown"` until broker-native or worker-mirrored protection is recorded.

Treat any position with `orphaned: true` or `exit_plan_status` indicating missing plan as unmanaged; use flatten or rescue flow (see section 7).

---

## 4. How to see the exact intelligence and rationale behind an order

- **GET /v1/paper/exposure** — Per position:
  - `scrappy_at_entry`, `scrappy_detail` (snapshot_id, freshness_minutes, catalyst_direction, evidence_count, headline_count, stale_flag, conflict_flag).
  - `ai_referee_at_entry` (`"ran"` | `"not_run"`), `ai_referee_detail` (model_name, referee_version, decision_class, setup_quality_score, contradiction_flag, stale_flag, evidence_sufficiency, plain_english_rationale).
- **Signal/order detail (API):** Use signal UUID from exposure or orders; query signal by ID to get `reason_codes`, `feature_snapshot_json`, `intelligence_snapshot_id`, `ai_referee_assessment_id`; join to `SymbolIntelligenceSnapshot` and `AiRefereeAssessment` for full rationale.

---

## 5. How to verify the exit plan for a live position

- **GET /v1/paper/exposure** — Fields `exit_plan_status`, `broker_protection`; when Phase 3 is complete, exit plan (stop, target, force-flat time) will be exposed per position.
- Until then, exit plan is not persisted at entry; treat all paper positions as needing manual verification of stop/target/force-flat (strategy logic exists in shadow; paper close happens on force-flat or manual flatten).

---

## 6. How to re-arm paper safely

1. **Prerequisites:** Ensure all arming checks pass:
   ```bash
   curl -s "${BASE_URL:-http://localhost:8000}/v1/paper/arming-prerequisites"
   ```
   Require `"satisfied": true` and `"blockers": []`. If not satisfied, resolve blockers (credentials, broker, DB, Redis, worker heartbeat, gateway heartbeat, dynamic universe not on static fallback).

2. **Config:** Set `PAPER_TRADING_ARMED=true` in `.env` (so the system allows arming via API). Restart not required if you only need to arm once prerequisites pass.

3. **Arm via API:**
   ```bash
   curl -X POST "${BASE_URL:-http://localhost:8000}/v1/paper/arm"
   ```
   On success: `{"armed": true, "message": "..."}`. On 400: prerequisites not satisfied; fix blockers and retry.

---

## 7. How to run safe live paper tests during market hours

- **Operator paper test routes** are blocked unless:
  - Paper is **armed** (config `PAPER_TRADING_ARMED=true` and Redis armed via POST /v1/paper/arm).
  - **Operator paper test** is enabled: `OPERATOR_PAPER_TEST_ENABLED=true`.
- **Caps:** Default `OPERATOR_PAPER_TEST_MAX_QTY=1`, `OPERATOR_PAPER_TEST_MAX_NOTIONAL=500.0`. Keep these safe for market-hours validation.
- **Flatten/rescue:** To close all paper positions: POST /v1/paper/test/flatten-all (requires armed + operator test enabled). For unmanaged/orphaned exposure, use flatten-all or close per symbol via sell-close / buy-cover as appropriate.

---

## 8. How to validate that scanner, Scrappy, AI Referee, and strategy are all participating

- **GET /v1/runtime/status** — Check:
  - `symbol_source.gateway.active_source`, `symbol_source.worker.active_source`: expect `dynamic` or `hybrid` (not `static` when scanner is live). If `static`, paper order submission is blocked.
  - `scrappy.mode`, `ai_referee.enabled` / `ai_referee.mode`: current config.
  - `paper_trading_armed`, `paper_armed_reason`: effective armed state.
- **GET /v1/health/detail** — `worker`, `alpaca_gateway`, `gateway_symbol_source`, `worker_universe_source`, `dynamic_symbols_available`.
- **GET /v1/scanner/summary** — Last run and toplist.
- **GET /v1/scrappy/status** — Scrappy runs and snapshot freshness.
- **Signals/exposure:** Use GET /v1/paper/exposure and signal/signal-detail endpoints to confirm `scrappy_at_entry` / `scrappy_detail` and `ai_referee_at_entry` / `ai_referee_detail` on strategy-driven paper positions.

---

## Endpoint quick reference

| Goal | Endpoint / action |
|------|-------------------|
| Disarm paper now | POST /v1/paper/disarm |
| Current paper exposure (source, orphaned, intelligence) | GET /v1/paper/exposure |
| Order source (strategy_paper vs operator_test) | GET /v1/orders (order_source), GET /v1/paper/exposure (source) |
| Arming prerequisites | GET /v1/paper/arming-prerequisites |
| Arm paper (after prerequisites pass) | POST /v1/paper/arm |
| Runtime truth (armed, universe, scrappy, referee) | GET /v1/runtime/status |
| Config (paper, operator test caps) | GET /v1/config |
