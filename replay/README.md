# Replay datasets

Versioned replay packs for deterministic regression. Each session is one market session (one day) with bars, quotes, trades, news, and Scrappy snapshots in deterministic order.

## Format

- **metadata.json** — session_id, date_utc, replay_version, description
- **bars.jsonl** — one JSON object per line: symbol, o, h, l, c, v, timestamp (ISO)
- **quotes.jsonl** — symbol, bp, ap, timestamp
- **trades.jsonl** — symbol, p, timestamp
- **news.jsonl** — headline, summary, symbols[], created_at
- **scrappy_snapshots.jsonl** — symbol, catalyst_direction, stale_flag, conflict_flag, freshness_minutes, snapshot_ts
- **expected_outputs.json** — golden outputs: signal_count, rejection_counts_by_reason, shadow_trade_count, etc.

All timestamps explicit; files sorted in deterministic order. Replay runner loads snapshots into DB, pushes market events to Redis in order, runs worker, then compares DB outputs to expected_outputs.json.

## session_001

Minimal fixed session: two symbols (AAPL, SPY), entry-window bars, news, and Scrappy snapshots. Proves one accepted long, one accepted short, and optional rejections (e.g. scrappy_stale).

## Refreshing golden outputs

After an intentional strategy change, run the replay, then copy the actual output JSON to `expected_outputs.json` and commit. Document the change in DECISION_LOG.md.
