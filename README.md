# FireCal

**Harmonized MODISâ€“VIIRS Fire Activity Calendar** â€” NASA Space Apps Challenge.

FireCal is a web app that shows a monthly calendar of fire hotspot activity from November 2000 to the latest processed month for a selected area. It estimates a common MODIS-equivalent scale from MODIS and VIIRS data supplied by [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov). The Indonesia pilot is experimental: regional bias and source-version limitations are documented in the [regional audit](docs/regional-audit-findings.md).

The full specification, user stories and tickets are in [`docs/FRD-Tickets-FireCal.pdf`](docs/FRD-Tickets-FireCal.pdf) (in Indonesian, the original project brief).

## Start with the real Indonesia data

**One command on Windows:** run `.\run.ps1` from the repository folder.
It installs missing project dependencies, starts the real-data API with automatic
NASA catch-up, starts the website, and opens it. Keep the terminal open; Ctrl+C
stops the services it started. Git, uv and Node.js must already be installed.

The separate commands below are useful when developing individual services.

The complete real Indonesia snapshot is included under
`datasets/indonesia/593ae2d95fdf/` as checksum-verified binary pieces.
A normal clone contains the data; `firecal bootstrap` assembles and installs it
automatically. No LFS or separate ZIP handoff is needed. The live updater fetches
newer observations into a separate local workspace.

From the repository root:

```powershell
uv sync --all-packages --locked --python 3.12
uv run firecal bootstrap
uv run firecal serve
```

`serve` starts the API on `http://localhost:8000`, checks NASA immediately, and
checks again hourly while the server runs. To enable new downloads, set
`FIRMS_MAP_KEY` in the root `.env` file. Without a key, the saved snapshot still
works. Keep that key out of Git and out of `web/.env`.

In another terminal, start the browser interface:

```powershell
npm.cmd exec --yes --package=pnpm@10.33.2 -- pnpm --dir web install --frozen-lockfile
npm.cmd exec --yes --package=pnpm@10.33.2 -- pnpm --dir web dev
```

Open `http://localhost:5173`. The status bar shows the latest detection date,
NASA check time, provisional status, and lagging platforms. Observations follow
NASA's UTC product availability; this is near-real-time, not instantaneous data.

For a single catch-up without starting the API:

```powershell
uv run firecal live-update --plan-only
uv run firecal live-update
```

The frozen audit snapshot stays unchanged. New observations are published in
separate complete versions under `data/live/`. See [the live-data guide](docs/LIVE-DATA.md).

## System architecture

```
NASA FIRMS â”€â”€â–º pipeline (ingest â†’ clean â†’ grid â†’ harmonize â†’ validate) â”€â”€â–º Parquet
                                                                              â”‚ DuckDB
                         web (React + MapLibre) â—„â”€â”€ JSON â”€â”€ api (FastAPI)
```

The pipeline runs daily and writes Parquet files. The API and the web app only read those results, so queries stay fast and keep working when FIRMS is unavailable.

## Repository layout

| Path                 | Contents                                                              |
| -------------------- | --------------------------------------------------------------------- |
| `data/`              | `raw/`, `interim/`, `processed/` â€” not committed                      |
| `pipeline/firecal/`  | Python package and `firecal` Typer CLI (ingest, clean, grid, harmonize, validate) |
| `pipeline/notebooks` | Analysis notebooks (T-10, T-13)                                       |
| `api/app/`           | FastAPI service: `/calendar`, `/stats`, `/points`, `/export`, `/globe`, `/regions`, `/meta` |
| `web/src/`           | React + TypeScript + Vite: interactive globe, area tools, calendar, statistics |
| `.github/workflows/` | CI (lint, tests and build on every pull request) and the daily NRT job |
| `docs/`              | Functional requirements and tickets (FRD)                             |

## Prerequisites

- Git, [Python 3.12](https://www.python.org/), and [uv](https://docs.astral.sh/uv/) 0.5 or newer
- [Node.js 22 LTS](https://nodejs.org/) 22.19.0 or newer and [pnpm](https://pnpm.io/) 9 or newer (`corepack enable`)
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

For the real-data Indonesia pilot, the public annual archives can be downloaded
without a MAP_KEY. See [the pilot guide](docs/indonesia-pilot.md) for the verified
download command, processing steps, coverage, and validation limits.

## Progress (14 November 2026)

Current status and evidence are maintained in the [progress tracker](docs/PROGRESS.md).
The next task is documented in the [bias-audit handover](docs/handover-bias-audit.md).
For teammates, follow the [data onboarding guide](docs/DATA-ONBOARDING.md) to
obtain the separate snapshot packages and run the app against the shared data.

- [x] Historical Indonesia archive prepared and verified through December 2025.
- [x] Regional calibration audit completed; baseline retained with documented limits.
- [x] Missing 2026 and NOAA-21 data acquired: 463 verified API responses across
  eight SP/NRT sources, through 14 November 2026 within each source's availability.
- [x] Isolated extended snapshot harmonized: 313 months, 7,716,551 retained
  detections, data version `593ae2d95fdf`.
- [x] Real-data API/CSV and point-weight checks passed; 126 Python tests and
  Ruff lint/format checks passed for this extension.
- [ ] Resolve satellite-specific, SP/NRT and observation-exposure effects. The
  January-October 2026 national bias is -12.20%; only 8/27 eligible provinces meet
  both targets. The dataset remains experimental, and November is partial.
- [ ] Establish a new evaluation protocol before selecting a revised correction.
- [ ] Promote the extended snapshot to serving after its limitations are resolved
  or an explicit experimental serving decision is made; current serving is unchanged.

See the [extended snapshot report](docs/indonesia-extended.md) for reproduction,
output locations and limitations. Remote CI's earlier startup failure remains
unresolved in the [regional audit record](docs/regional-audit-findings.md).

## Commands

The real-data 2026 bias diagnostics are complete: see the [findings and charts](docs/bias-audit-findings.md), [progress tracker](docs/PROGRESS.md), and [next evaluation proposal](docs/bias-evaluation-next.md). The national bias remains -12.20%; no correction is promoted. To reproduce the audit, start with `uv run --no-sync python scripts/audit_indonesia_bias.py --check-inputs`; the snapshot and acquisition receipts are transferred separately because they are excluded from Git.

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

The code is released under the [MIT license](LICENSE). Hotspot data comes from **NASA FIRMS** (Fire Information for Resource Management System), using MODIS and VIIRS 375 m products. Actual included satellites and reported source versions depend on the processed dataset and are exposed in `/meta`; homogeneous MODIS C6.1 coverage has not been verified for the public annual Indonesia archives.
