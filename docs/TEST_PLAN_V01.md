# Test Plan Additions (v0.1)

## One-connection fan-out test

Only one Alpaca market-data connection is active; downstream consumers still receive all events.

- **Location**: `tests/test_market_gateway_fanout.py`
- **Assertion**: `StreamClient` owns a single WebSocket; handlers are registered for internal fan-out. Fan-out handler pushes to Redis streams.

## Binary-frame trade-update test

Paper `trade_updates` parser handles the paper stream correctly (including binary frames).

- **Location**: `tests/test_trade_gateway_binary_frames.py`
- **Assertion**: `TradingStreamClient._parse_update` parses both text JSON and decoded binary payloads.

## Recovery test

Kill the market stream, reseed from snapshots/latest, then resume without duplicating bars or quote state.

- **Location**: `tests/test_recovery_reseed.py`
- **Assertion**: `reseed_from_snapshots` calls REST snapshots and dispatches quote/trade to the same handlers used by the stream.

## Idempotency test

Re-sending the same signal UUID does not create a second paper order because `client_order_id` is reused.

- **Location**: `tests/test_idempotency_client_order_id.py`
- **Assertion**: `create_order` sends `client_order_id` in the request; `get_order_by_client_order_id` queries by it.

## BOD reconciliation test

Internal ledger stays stable even when Alpaca's position average fields change after BOD sync.

- **Location**: `tests/test_bod_reconciliation.py`
- **Assertion**: `FillEvent` carries `avg_fill_price` as canonical; `alpaca_avg_entry_price` is informational only.

## SSH deploy smoke test

`docker --context um790 ps` and `docker --context um790 compose ps` work over the tailnet; no Docker TCP listener is exposed.

- **Manual**: After creating the context, run from laptop and confirm containers list. Do not open Docker on a TCP port on the UM790.

## Access-control test

Tailnet policy only allows your user to SSH to the UM790. Tailscale's access-control model is deny-by-default and policy-driven.

- **Manual**: Configure in Tailscale admin (ACLs / SSH). Document in OPS_RUNBOOK_TAILSCALE_SSH.md.
