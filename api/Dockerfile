# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /src
COPY pyproject.toml uv.lock README.md ./
COPY pipeline/pyproject.toml pipeline/pyproject.toml
COPY pipeline/firecal pipeline/firecal
COPY api/pyproject.toml api/pyproject.toml
COPY api/app api/app
RUN uv sync --frozen --no-dev --package firecal-api --no-editable

WORKDIR /app
RUN useradd --create-home firecal
USER firecal

ENV DATA_URI=/app/data/processed
EXPOSE 8000
# PORT is set by Cloud Run / Fly.io; proxy headers keep scheme and client IP behind HTTPS.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips=*"]
