# Run lint/test in container so no local venv needed.
# Replay: use DATABASE_URL + REDIS_URL (Postgres + Redis). make replay runs session_001 and compares to golden.
# For docker compose config: POSTGRES_PASSWORD=... ALPACA_API_KEY_ID=... ALPACA_API_SECRET_KEY=... make compose-config

.PHONY: lint test test-full up-infra compose-config replay replay-diff test-db test-replay test-scrappy-db smoke-um790 release-gate release-gate-um790 release-gate-docker release-gate-docker-classic validate-docker runtime-truth-validate

lint:
	docker run --rm -v "$(CURDIR):/app" -w /app python:3.11-slim bash -c "pip install -q ruff mypy '.[dev]' && ruff check src tests scripts --fix && ruff format src tests scripts && mypy src"

test:
	docker run --rm -v "$(CURDIR):/app" -w /app -e ALPACA_API_KEY_ID=dummy -e ALPACA_API_SECRET_KEY=dummy -e DATABASE_URL=sqlite:///tmp/db -e REDIS_URL=redis://localhost:6379/0 python:3.11-slim bash -c "pip install -q '.[dev]' && pytest tests -v --tb=short"

# Bring up Postgres + Redis, run migrations, then run full test suite (including DB-backed tests).
# Requires infra/compose.yaml and .env. Use: make up-infra first if needed.
test-full:
	@bash -c "cd '$(CURDIR)' && ./scripts/ensure_infra.sh && export PYTHONPATH='$(CURDIR):$(CURDIR)/src' && pytest tests -v --tb=short"

# Start Postgres + Redis and run migrations. After this, run the API/worker or pytest with DB.
up-infra:
	@cd '$(CURDIR)' && ./scripts/ensure_infra.sh

test-db:
	PYTHONPATH=.:src pytest tests -v --tb=short -k "e2e or replay or worker_scrappy or signal_attribution or api_intelligence_db or intelligence"

test-replay:
	PYTHONPATH=.:src pytest tests/test_replay_expected_outputs.py tests/test_replay_runner.py -v --tb=short

test-scrappy-db:
	PYTHONPATH=.:src pytest tests/test_scrappy_intelligence.py tests/test_worker_scrappy_e2e.py tests/test_api_intelligence_db.py tests/test_signal_attribution_e2e.py -v --tb=short -k "e2e or replay or worker_scrappy or signal_attribution or api_intelligence_db"

replay:
	PYTHONPATH=.:src python scripts/run_replay.py --session replay/session_001

replay-diff:
	@echo "Usage: python scripts/replay_diff.py <output_a.json> <output_b.json>"
	PYTHONPATH=.:src python scripts/replay_diff.py replay/session_001/expected_outputs.json replay/session_001/expected_outputs.json || true

smoke-um790:
	./scripts/smoke_um790.sh

release-gate:
	./scripts/release_gate.sh

release-gate-um790:
	./scripts/release_gate.sh --um790

# Docker-native: no host venv; runs migrations, DB tests, replay in validate container. Report in artifacts/release_gate/
release-gate-docker:
	./scripts/release_gate.sh --docker --start-infra

# Same as release-gate-docker but use classic docker build (no buildx). Use if buildx has permission issues.
release-gate-docker-classic:
	./scripts/release_gate.sh --docker --docker-no-buildx --start-infra

validate-docker:
	docker compose -f infra/compose.yaml -f infra/compose.test.yaml run --rm -v "$(CURDIR):/app" -w /app validate

# Validate compose file. Requires POSTGRES_PASSWORD, ALPACA_API_KEY_ID, ALPACA_API_SECRET_KEY in env or .env.
compose-config:
	@cd "$(CURDIR)" && ( test -f infra/compose.yaml || (echo "infra/compose.yaml not found" >&2; exit 1) ) && \
	POSTGRES_PASSWORD=$${POSTGRES_PASSWORD?} ALPACA_API_KEY_ID=$${ALPACA_API_KEY_ID?} ALPACA_API_SECRET_KEY=$${ALPACA_API_SECRET_KEY?} docker compose -f infra/compose.yaml -p infra config --quiet && echo "docker compose config OK"

# Full-stack: compose config, migrations, up, then HTTP checks. Use API_ONLY=1 for external API only.
runtime-truth-validate:
	bash ./scripts/runtime_truth_validate.sh
