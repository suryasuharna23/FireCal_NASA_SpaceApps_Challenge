.DEFAULT_GOAL := help
.PHONY: help setup data synth dev api web lint format test e2e clean

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-8s\033[0m %s\n", $$1, $$2}'

setup: ## Install Python + JS dependencies and pre-commit hooks
	uv sync --all-packages
	pnpm install --dir web
	uv run pre-commit install

data: ## Run the full pipeline: data/raw -> data/processed (+ land cells once)
	@test -f data/processed/cells.parquet || uv run firecal cells
	uv run firecal run

synth: ## Generate a synthetic FIRMS archive in data/raw/synthetic (no MAP_KEY needed)
	uv run firecal synth

dev: ## Run API and web together via Docker Compose
	docker compose up --build

api: ## Run the API locally with auto-reload (http://localhost:8000/docs)
	uv run uvicorn app.main:app --reload --port 8000 --app-dir api

web: ## Run the Vite dev server (http://localhost:5173)
	pnpm --dir web dev

lint: ## Lint Python and TypeScript
	uv run ruff check .
	uv run ruff format --check .
	pnpm --dir web lint
	pnpm --dir web format:check
	pnpm --dir web typecheck

format: ## Auto-format Python and TypeScript
	uv run ruff check --fix .
	uv run ruff format .
	pnpm --dir web format

test: lint ## Ruff, pytest, ESLint and Vitest
	uv run pytest
	pnpm --dir web test

e2e: ## Playwright end-to-end tests
	pnpm --dir web exec playwright test

clean: ## Remove build and cache artifacts
	rm -rf .pytest_cache .ruff_cache web/dist web/coverage
