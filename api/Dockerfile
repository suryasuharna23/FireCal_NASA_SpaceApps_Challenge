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
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
