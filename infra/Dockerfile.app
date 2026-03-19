# Single app image for api, worker, scheduler, scanner, scrappy_auto, gateways, reconciler.
# Build from repo root: docker build -f infra/Dockerfile.app -t infra-app .
FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Project files
COPY pyproject.toml alembic.ini ./
COPY migrations ./migrations
COPY scripts/entrypoint_api.sh ./scripts/
COPY src ./src

# Install app (editable so src is used)
RUN pip install --no-cache-dir -e .

# All services use same image; compose overrides command.
ENV PYTHONPATH=/app/src
ENV APP_DIR=/app

# API default (compose overrides for worker, scheduler, etc.)
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
ENTRYPOINT ["/app/scripts/entrypoint_api.sh"]
