#!/usr/bin/env bash
# Release gate: migrations, DB tests, replay, optional UM790 smoke.
# Modes: local (default), --docker (run gate in validate container), --docker-inner (inside container).
# Exit non-zero on first failure. Writes report to artifacts/release_gate/.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
COMPOSE_MAIN="-f infra/compose.yaml"
COMPOSE_TEST="-f infra/compose.yaml -f infra/compose.test.yaml"
RUN_UM790=false
START_INFRA=false
USE_DOCKER=false
DOCKER_INNER=false
DOCKER_NO_BUILDX=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --docker) USE_DOCKER=true; shift ;;
    --docker-inner) DOCKER_INNER=true; shift ;;
    --docker-no-buildx) DOCKER_NO_BUILDX=true; shift ;;
    --um790) RUN_UM790=true; shift ;;
    --start-infra) START_INFRA=true; shift ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# ---- Docker mode (host): run gate inside validate container ----
if [[ "$USE_DOCKER" == true ]] && [[ "$DOCKER_INNER" != true ]]; then
  export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-stockbot}"
  export ALPACA_API_KEY_ID="${ALPACA_API_KEY_ID:-dummy}"
  export ALPACA_API_SECRET_KEY="${ALPACA_API_SECRET_KEY:-dummy}"
  if [[ "$START_INFRA" == true ]]; then
    echo "[release_gate] Starting postgres + redis..."
    docker compose $COMPOSE_TEST up -d postgres redis
    echo "[release_gate] Waiting for postgres..."
    for i in 1 2 3 4 5 6 7 8 9 10; do
      if docker compose $COMPOSE_TEST exec -T postgres pg_isready -U stockbot 2>/dev/null; then
        break
      fi
      [[ $i -eq 10 ]] && { echo "Postgres did not become ready" >&2; exit 1; }
      sleep 2
    done
    sleep 2
  fi
  if [[ "$DOCKER_NO_BUILDX" == true ]]; then
    echo "[release_gate] Building validate image with classic docker build..."
    docker build -f infra/Dockerfile.validate -t stockbot-validate:local .
    # Run using pre-built image on the same network as postgres/redis
    NETWORK="$(docker compose $COMPOSE_TEST ps -q postgres 2>/dev/null | xargs -r docker inspect --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}' 2>/dev/null | head -1)"
    [[ -z "$NETWORK" ]] && { echo "Could not determine compose network (is postgres running?)" >&2; exit 1; }
    echo "[release_gate] Running gate in validate container (classic)..."
    docker run --rm -v "$ROOT:/app" -w /app --network "$NETWORK" \
      -e DATABASE_URL="postgresql+asyncpg://stockbot:${POSTGRES_PASSWORD}@postgres:5432/stockbot" \
      -e REDIS_URL="redis://redis:6379/0" \
      -e ALPACA_API_KEY_ID="${ALPACA_API_KEY_ID}" \
      -e ALPACA_API_SECRET_KEY="${ALPACA_API_SECRET_KEY}" \
      -e PYTHONPATH=/app:/app/src \
      stockbot-validate:local bash -c "scripts/release_gate.sh --docker-inner"
  else
    echo "[release_gate] Running gate in validate container..."
    docker compose $COMPOSE_TEST run --rm -v "$ROOT:/app" -w /app validate bash -c "scripts/release_gate.sh --docker-inner"
  fi
  exit $?
fi

export PYTHONPATH="${ROOT}:${ROOT}/src"
export ALPACA_API_KEY_ID="${ALPACA_API_KEY_ID:-dummy}"
export ALPACA_API_SECRET_KEY="${ALPACA_API_SECRET_KEY:-dummy}"

# ---- Required env (for DB tests and replay); when --docker-inner, compose sets DATABASE_URL/REDIS_URL ----
if [[ -z "${DATABASE_URL:-}" ]]; then
  if [[ -n "${POSTGRES_PASSWORD:-}" ]]; then
    export DATABASE_URL="postgresql+asyncpg://stockbot:${POSTGRES_PASSWORD}@localhost:5432/stockbot"
  else
    echo "Set DATABASE_URL or POSTGRES_PASSWORD" >&2
    exit 1
  fi
fi
if [[ -z "${REDIS_URL:-}" ]]; then
  export REDIS_URL="redis://localhost:6379/0"
fi

# ---- Optional: start test infra (local mode only) ----
if [[ "$START_INFRA" == true ]]; then
  echo "[release_gate] Starting postgres + redis..."
  export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-stockbot}"
  docker compose $COMPOSE_TEST up -d postgres redis
  echo "[release_gate] Waiting for postgres..."
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if docker compose $COMPOSE_TEST exec -T postgres pg_isready -U stockbot 2>/dev/null; then
      break
    fi
    [[ $i -eq 10 ]] && { echo "Postgres did not become ready" >&2; exit 1; }
    sleep 2
  done
  sleep 2
  export DATABASE_URL="postgresql+asyncpg://stockbot:${POSTGRES_PASSWORD}@localhost:5432/stockbot"
  export REDIS_URL="redis://localhost:6379/0"
fi

# ---- Report state ----
GIT_COMMIT=""
MIGRATION_STATUS=""
DB_TEST_PASSED=false
DB_TEST_COUNT=""
REPLAY_PASSED=false
REPLAY_DIFF_STATUS=""
SMOKE_PASSED=""
SMOKE_STATUS="skipped"
TIMESTAMP=""
REPORT_DIR="${ROOT}/artifacts/release_gate"
REPORT_JSON=""
REPORT_MD=""

GIT_COMMIT="$(git rev-parse HEAD 2>/dev/null || echo "n/a")"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)"

run_report_script() {
  mkdir -p "$REPORT_DIR"
  REPORT_JSON="${REPORT_DIR}/report_$(date +%Y%m%d_%H%M%S).json"
  REPORT_MD="${REPORT_DIR}/report_$(date +%Y%m%d_%H%M%S).md"
  python3 scripts/write_release_gate_report.py \
    --git-commit "$GIT_COMMIT" \
    --migration-status "${MIGRATION_STATUS}" \
    --db-test-passed "$DB_TEST_PASSED" \
    --db-test-count "${DB_TEST_COUNT}" \
    --replay-passed "$REPLAY_PASSED" \
    --replay-diff-status "${REPLAY_DIFF_STATUS}" \
    --smoke-status "${SMOKE_STATUS}" \
    --timestamp "$TIMESTAMP" \
    --out-json "$REPORT_JSON" \
    --out-md "$REPORT_MD"
  echo "[release_gate] Report: $REPORT_JSON $REPORT_MD"
}

# ---- 1. Migrations ----
echo "[release_gate] Migrations..."
if python3 -m alembic -c alembic.ini upgrade head 2>/dev/null; then
  MIGRATION_STATUS="ok"
else
  MIGRATION_STATUS="fail"
  echo "Migrations failed" >&2
  run_report_script
  exit 1
fi

# ---- Isolated state: print DB and reset validation tables ----
echo "[release_gate] Database: $(echo "$DATABASE_URL" | sed 's/:[^:@]*@/:***@/')"
echo "[release_gate] Resetting validation state (signals, shadow_trades, scrappy_gate_rejections, symbol_intelligence_snapshots)..."
if ! python3 scripts/reset_validation_state.py; then
  echo "reset_validation_state failed" >&2
  run_report_script
  exit 1
fi

# ---- 2. DB-backed tests ----
echo "[release_gate] DB-backed tests..."
DB_OUT="$(mktemp)"
if pytest tests -v --tb=line -k "e2e or replay or worker_scrappy or signal_attribution or api_intelligence_db or intelligence" 2>"$DB_OUT"; then
  DB_TEST_PASSED=true
  DB_TEST_COUNT="$(grep -E 'passed|failed' "$DB_OUT" | tail -1 || echo "")"
else
  DB_TEST_PASSED=false
  DB_TEST_COUNT=""
  cat "$DB_OUT" >&2
  rm -f "$DB_OUT"
  run_report_script
  exit 1
fi
rm -f "$DB_OUT"

# ---- Reset again before replay so replay sees clean state ----
echo "[release_gate] Resetting validation state before replay..."
if ! python3 scripts/reset_validation_state.py; then
  echo "reset_validation_state failed" >&2
  run_report_script
  exit 1
fi

# ---- 3. Replay ----
echo "[release_gate] Replay session_001..."
REPLAY_OUT="$(mktemp)"
if python3 scripts/run_replay.py --session replay/session_001 2>"$REPLAY_OUT"; then
  REPLAY_PASSED=true
  REPLAY_DIFF_STATUS="match"
else
  REPLAY_PASSED=false
  REPLAY_DIFF_STATUS="mismatch"
  cat "$REPLAY_OUT" >&2
  rm -f "$REPLAY_OUT"
  run_report_script
  exit 1
fi
rm -f "$REPLAY_OUT"

# ---- 4. Optional UM790 smoke (host only; skipped when --docker-inner) ----
if [[ "$RUN_UM790" == true ]] && [[ "$DOCKER_INNER" != true ]]; then
  echo "[release_gate] Smoke UM790..."
  if ./scripts/smoke_um790.sh 2>/dev/null; then
    SMOKE_STATUS="ok"
  else
    SMOKE_STATUS="fail"
    run_report_script
    exit 1
  fi
fi

# ---- Summary ----
echo ""
echo "--- Release gate summary ---"
echo "  migrations: $MIGRATION_STATUS"
echo "  db_tests:   $DB_TEST_PASSED"
echo "  replay:     $REPLAY_PASSED"
echo "  smoke:      $SMOKE_STATUS"
echo "  git:        $GIT_COMMIT"
echo "------------------------------"
echo "PASS"

run_report_script
exit 0
