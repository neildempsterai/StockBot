# Run lint/test in container so no local venv needed.
# For docker compose config: POSTGRES_PASSWORD=... ALPACA_API_KEY_ID=... ALPACA_API_SECRET_KEY=... make compose-config

.PHONY: lint test compose-config

lint:
	docker run --rm -v "$(CURDIR):/app" -w /app python:3.11-slim bash -c "pip install -q ruff mypy '.[dev]' && ruff check src tests --fix && ruff format src tests && mypy src"

test:
	docker run --rm -v "$(CURDIR):/app" -w /app -e ALPACA_API_KEY_ID=dummy -e ALPACA_API_SECRET_KEY=dummy -e DATABASE_URL=sqlite:///tmp/db -e REDIS_URL=redis://localhost:6379/0 python:3.11-slim bash -c "pip install -q '.[dev]' && pytest tests -v --tb=short"

compose-config:
	POSTGRES_PASSWORD=$${POSTGRES_PASSWORD?} ALPACA_API_KEY_ID=$${ALPACA_API_KEY_ID?} ALPACA_API_SECRET_KEY=$${ALPACA_API_SECRET_KEY?} docker compose -f infra/compose.yaml config --quiet && echo "docker compose config OK"
