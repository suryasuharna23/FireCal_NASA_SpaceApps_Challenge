# FireCal

**Harmonized MODIS–VIIRS Fire Activity Calendar** — NASA Space Apps Challenge.

FireCal is a web app that shows a monthly calendar of fire hotspot activity, from November 2000 to today, for any area the user selects. It combines MODIS and VIIRS data from [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov) that are harmonized to a common MODIS-equivalent scale, so the switch between sensors does not create false trends.

The full specification, user stories and tickets are in [`docs/FRD-Tickets-FireCal.pdf`](docs/FRD-Tickets-FireCal.pdf) (in Indonesian, the original project brief).

## Architecture

```
NASA FIRMS ──► pipeline (ingest → clean → grid → harmonize → validate) ──► Parquet
                                                                              │ DuckDB
                         web (React + MapLibre) ◄── JSON ── api (FastAPI)
```

The pipeline runs daily and writes Parquet files. The API and the web app only read those results, so queries stay fast and keep working when FIRMS is unavailable.

## Repository layout

| Path                 | Contents                                                              |
| -------------------- | --------------------------------------------------------------------- |
| `data/`              | `raw/`, `interim/`, `processed/` — not committed                      |
| `pipeline/firecal/`  | Python package and `firecal` Typer CLI (ingest, clean, grid, harmonize, validate) |
| `pipeline/notebooks` | Analysis notebooks (T-10, T-13)                                       |
| `api/app/`           | FastAPI service: `/calendar`, `/stats`, `/points`, `/export`, `/globe`, `/regions`, `/meta` |
| `web/src/`           | React + TypeScript + Vite: interactive globe, area tools, calendar, statistics |
| `.github/workflows/` | CI (lint, tests and build on every pull request) and the daily NRT job |
| `docs/`              | Functional requirements and tickets (FRD)                             |

## Prerequisites

- Git, [Python 3.12](https://www.python.org/), and [uv](https://docs.astral.sh/uv/) 0.5 or newer
- [Node.js 22 LTS](https://nodejs.org/) and [pnpm](https://pnpm.io/) 9 or newer (`corepack enable`)
- Docker and Docker Compose v2 (optional)
- A free FIRMS `MAP_KEY` from the [FIRMS API page](https://firms.modaps.eosdis.nasa.gov/api/map_key/)

## Running locally

```bash
git clone https://github.com/suryasuharna23/FireCal_NASA_SpaceApps_Challenge.git firecal
cd firecal

# 1. Configuration: set FIRMS_MAP_KEY in .env (never commit it)
cp .env.example .env
cp web/.env.example web/.env

# 2. Dependencies and pre-commit hooks
make setup

# 3. Data: put the FIRMS archive CSVs (per year and sensor) in data/raw/, then:
make data                       # narrow COVERAGE_BBOX to one country for a quick test
uv run firecal nrt --days 5     # latest near-real-time detections

# 4. Run
make api                        # http://localhost:8000/docs
make web                        # http://localhost:5173
# or both at once with Docker:
make dev
```

No synthetic data? Run `make synth` to generate a FIRMS-format archive for development without a MAP_KEY.

Without `make` (for example on Windows), run the commands in the [`Makefile`](Makefile) directly.

After setting `FIRMS_MAP_KEY`, check it with `uv run firecal check-key`. For CI, store the same key as the GitHub secret `FIRMS_MAP_KEY` and run the **Check FIRMS MAP_KEY** workflow.

## Commands

| Command       | What it does                                                      |
| ------------- | ----------------------------------------------------------------- |
| `make setup`  | Install Python and JavaScript dependencies and the pre-commit hooks |
| `make data`   | Run the whole pipeline from `data/raw/` to `data/processed/`      |
| `make synth`  | Generate a synthetic FIRMS archive in `data/raw/synthetic/`       |
| `make dev`    | Run the API and the web app together with Docker Compose          |
| `make test`   | Ruff, pytest, ESLint, Prettier, typecheck and Vitest              |
| `make e2e`    | Playwright end-to-end tests                                       |
| `make format` | Auto-format the Python and TypeScript code                        |

Run `make test` before opening a pull request.

## Deployment

The web app is a static site (Cloudflare Pages), the API is a container (Fly.io or Cloud Run) and the processed data live in an S3-compatible bucket (Cloudflare R2). `.github/workflows/deploy.yml` pushes the API image to GHCR on every push to `main` and deploys each target once its credentials are configured. See [`docs/deployment.md`](docs/deployment.md) for the step-by-step setup and a local production check.

## Environment variables

The backend and pipeline read `.env` in the repository root; the frontend reads `web/.env`. Only variables starting with `VITE_` reach the browser, so `FIRMS_MAP_KEY` stays on the server (NFR-08). See [`.env.example`](.env.example) and [`web/.env.example`](web/.env.example).

## Contributing

- Branch from `main` with the name `<type>/<ticket>-<short-name>`, for example `feat/T-15-calendar-endpoint`.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/), for example `feat(api): add /calendar endpoint`.
- CI must pass before a pull request is merged.

## License and attribution

The code is released under the [MIT license](LICENSE). Hotspot data comes from **NASA FIRMS** (Fire Information for Resource Management System), using MODIS Collection 6.1 and VIIRS 375 m (S-NPP, NOAA-20 and NOAA-21).
