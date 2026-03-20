# Why Intelligence and AI Referee Aren’t Running or Producing Output

## TL;DR

- **Intelligence:** Needs **scanner** and **scrappy_auto** running, and at least one successful Scrappy run that produces notes and symbol snapshots. If `/v1/intelligence/*` is empty, Scrappy hasn’t written any snapshots yet.
- **AI Referee:** Off by default. Set **`AI_REFEREE_ENABLED=true`** and **`AI_REFEREE_MODE=advisory`** (or `required`) in `.env`, and provide **`OPENAI_API_KEY`** (or OAuth). Referee runs inside the **worker** when a candidate passes strategy + Scrappy gating.

---

## Intelligence (symbol intelligence snapshots)

### How it works

1. **Scanner** (and/or opportunity engine) runs and pushes top symbols to Redis (`stockbot:scanner:top_symbols`).
2. **scrappy_auto** runs on a timer (`SCRAPPY_AUTO_REFRESH_SEC`, default 120). It reads those symbols from Redis, or falls back to the Scrappy watchlist.
3. **Scrappy run** fetches content, creates notes, then builds **symbol intelligence snapshots** and inserts them into `symbol_intelligence_snapshots` (in `run_service.py`).
4. **API** endpoints `/v1/intelligence/latest`, `/v1/intelligence/recent`, `/v1/intelligence/summary` read from that table.

### Why you see no output

| Cause | What to do |
|-------|------------|
| **Scanner not running or not writing to Redis** | Ensure `scanner` service is up. Scanner must run and publish top symbols to Redis so scrappy_auto has a symbol list. |
| **scrappy_auto not running** | Ensure `scrappy_auto` container is running. If `SCRAPPY_AUTO_ENABLED=false`, enable it in `.env`. |
| **Market session** | scrappy_auto only runs when session is **premarket** or **regular** (not `closed` or `overnight`). |
| **No symbols** | If Redis has no top symbols and watchlist is empty, scrappy_auto skips the run. Run scanner first or configure a watchlist. |
| **Scrappy run produces no notes** | Scrappy needs sources and (optionally) LLM configured. If every run creates 0 notes, no snapshots are built. Check scrappy_auto logs and Scrappy source/LLM config. |
| **DB table empty** | Until at least one Scrappy run completes and inserts snapshots, `/v1/intelligence/*` will be empty. |

### Quick checks

```bash
# Is scrappy_auto running?
docker compose -f infra/compose.yaml -p infra ps scrappy_auto

# Recent Scrappy runs / status
curl -sS http://localhost:8000/v1/scrappy/status | jq .

# Intelligence summary (will be empty until snapshots exist)
curl -sS http://localhost:8000/v1/intelligence/summary | jq .
```

---

## AI Referee

### How it works

- **AI Referee** is **not** a separate service. It runs **inside the worker** when evaluating a candidate symbol.
- When a symbol passes strategy filters and Scrappy gating, the worker optionally calls the referee (OpenAI or OAuth Codex) to get an assessment. The result is stored in `ai_referee_assessments` and linked to the signal.
- **API** endpoints `/v1/ai-referee/recent`, `/v1/ai-referee/assessments/{id}`, etc. read from that table.

### Why you see no output

| Cause | What to do |
|-------|------------|
| **Referee is off by default** | In `config.py`, `ai_referee_enabled` defaults to **False** and `ai_referee_mode` to **"off"**. So the worker never calls the referee unless you turn it on. |
| **Env not set** | Add to `.env`: `AI_REFEREE_ENABLED=true`, `AI_REFEREE_MODE=advisory` (or `required`). Restart the **worker** so it picks up the new config. |
| **No OpenAI / OAuth** | For **api_key** auth (default): set `OPENAI_API_KEY=sk-...`. For **oauth**: set `AI_REFEREE_AUTH=oauth` and configure Codex/OAuth. |
| **No candidates reaching referee** | Referee is only called when a symbol has already passed strategy and Scrappy gating. If the worker has no such candidates (e.g. no bars, no Scrappy snapshot, or all rejected earlier), you’ll never see referee output. |

### Enable AI Referee

In `.env`:

```bash
# Enable referee (worker only; not order authority)
AI_REFEREE_ENABLED=true
AI_REFEREE_MODE=advisory

# For API-key auth (default)
OPENAI_API_KEY=sk-your-key-here

# Optional: model (default gpt-4o-mini)
# AI_REFEREE_MODEL=gpt-4o-mini
```

Restart the worker:

```bash
docker compose -f infra/compose.yaml -p infra up -d --force-recreate worker
```

### Quick checks

```bash
# Config: referee should show enabled
curl -sS http://localhost:8000/v1/config | jq '.AI_REFEREE_ENABLED, .AI_REFEREE_MODE'

# Recent referee assessments (empty until worker produces some)
curl -sS "http://localhost:8000/v1/ai-referee/recent?limit=5" | jq .
```

---

## Summary

| Component | Where it runs | Default | To get output |
|-----------|----------------|---------|----------------|
| **Intelligence** | Data produced by **Scrappy** (run_service), served by **API** | scrappy_auto on, but needs scanner + successful run | Ensure scanner + scrappy_auto run; wait for a Scrappy run that creates notes and snapshots. |
| **AI Referee** | **Worker** (only when evaluating a candidate) | **Off** (`AI_REFEREE_ENABLED=false`, `AI_REFEREE_MODE=off`) | Set `AI_REFEREE_ENABLED=true`, `AI_REFEREE_MODE=advisory`, `OPENAI_API_KEY=...`; restart worker; need candidate flow (strategy + Scrappy passing). |

Neither component is a standalone daemon; both depend on the rest of the stack (scanner, worker, Scrappy, and for referee: OpenAI or OAuth).
