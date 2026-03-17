# API, worker, scheduler
FROM python:3.11-slim AS builder
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
COPY pyproject.toml src/ ./
RUN pip install --no-cache-dir -e .

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONPATH=/app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app /app
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
