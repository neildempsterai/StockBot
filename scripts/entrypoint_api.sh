#!/usr/bin/env bash
# When RUN_MIGRATIONS=1 (api service only): run migrations with same env as app, then start server.
# Single process = single DATABASE_URL = no auth mismatch.
set -e
cd "${APP_DIR:-/app}"
if [ "${RUN_MIGRATIONS}" = "1" ] && [ -n "${DATABASE_URL}" ]; then
  echo "[entrypoint] Running migrations..."
  migrate_out=$(python3 -m alembic -c alembic.ini upgrade head 2>&1) || {
    echo "[entrypoint] Migration failed." >&2
    echo "$migrate_out" >&2
    echo "$migrate_out" | grep -q "password authentication failed" && {
      echo "[entrypoint] Postgres password mismatch (volume was inited with a different password)." >&2
      echo "[entrypoint] Run once:  docker compose down -v && docker compose up -d" >&2
    }
    exit 1
  }
  echo "[entrypoint] Migrations done."
fi
exec "$@"
