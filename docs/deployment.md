# Deployment (T-38)

FireCal runs as three pieces (FRD 7.5):

| Piece | Hosting (hackathon) | Built from |
| --- | --- | --- |
| Web app (static) | Cloudflare Pages | `pnpm --dir web build` → `web/dist` |
| API (container) | Fly.io (or Google Cloud Run) | `api/Dockerfile` (repo root as context) |
| Processed data | Cloudflare R2 (or S3) | `make data` → `data/processed/` |

All three are served over HTTPS. The FIRMS `MAP_KEY` only lives in the pipeline and API secrets; it is never part of the web build (NFR-08).

## 1. Data bucket

1. Create an R2 bucket, e.g. `firecal-data`, and an API token with read/write access.
2. Build the data locally (`make data`) and upload it:
   ```bash
   aws s3 sync data/processed s3://firecal-data/processed \
     --endpoint-url https://<account-id>.r2.cloudflarestorage.com
   aws s3 sync data/interim/nrt s3://firecal-data/interim/nrt \
     --endpoint-url https://<account-id>.r2.cloudflarestorage.com
   ```
3. The daily NRT workflow (`nrt-daily.yml`) keeps the bucket up to date. It needs the repository variables `DATA_BUCKET` and `S3_ENDPOINT`, and the secrets `FIRMS_MAP_KEY`, `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY`.

## 2. API on Fly.io

```bash
flyctl launch --no-deploy --copy-config        # uses fly.toml (2 vCPU / 2 GB, 1 machine always on)
flyctl secrets set S3_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com \
  S3_ACCESS_KEY_ID=... S3_SECRET_ACCESS_KEY=... FIRMS_MAP_KEY=...
flyctl deploy --remote-only
curl https://firecal-api.fly.dev/health
```

Set `CORS_ORIGINS` in `fly.toml` to the web app's origin (e.g. `https://firecal.pages.dev`).

**Cloud Run alternative:**
```bash
gcloud run deploy firecal-api --image ghcr.io/<owner>/firecal-api:latest --cpu 2 --memory 2Gi --min-instances 1 --set-env-vars DATA_URI=s3://firecal-data/processed,...
```
The container reads `PORT`, so no extra configuration is needed.

## 3. Web app on Cloudflare Pages

Create a Pages project (e.g. `firecal`). The build is a plain static site:

```bash
VITE_API_BASE_URL=https://firecal-api.fly.dev pnpm --dir web build
npx wrangler pages deploy web/dist --project-name firecal
```

`web/public/_headers` caches hashed assets for a year.

## 4. Automatic deploys

`.github/workflows/deploy.yml` runs on every push to `main`:

- **api:** always builds and pushes `ghcr.io/<owner>/firecal-api:<sha>`. With the `FLY_API_TOKEN` secret it deploys that image to Fly.io and smoke-tests `API_BASE_URL/health` and `/meta`.
- **web:** builds with `VITE_API_BASE_URL = vars.API_BASE_URL`. With the `CLOUDFLARE_API_TOKEN` secret and `CLOUDFLARE_ACCOUNT_ID` variable it deploys to Pages (`CF_PAGES_PROJECT`, default `firecal`).

Targets without credentials are skipped with a notice, so the workflow never fails on a fresh fork.

| Kind | Name | Used by |
| --- | --- | --- |
| Secret | `FLY_API_TOKEN` | deploy (API) |
| Secret | `CLOUDFLARE_API_TOKEN` | deploy (web) |
| Secret | `FIRMS_MAP_KEY`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | NRT job, Fly secrets |
| Variable | `API_BASE_URL`, `CF_PAGES_PROJECT`, `CLOUDFLARE_ACCOUNT_ID` | deploy |
| Variable | `DATA_BUCKET`, `S3_ENDPOINT`, `COVERAGE_BBOX` | NRT job |

## 5. Production check without a cloud account

The same artifacts can be run locally to check a release:

```bash
docker build -f api/Dockerfile -t firecal-api:prod .
docker run --rm -p 8080:8080 -e PORT=8080 -e CORS_ORIGINS=http://localhost:4173 \
  -v "$PWD/data:/app/data:ro" firecal-api:prod
VITE_API_BASE_URL=http://localhost:8080 pnpm --dir web build
pnpm --dir web preview --port 4173      # http://localhost:4173
uv run python api/bench.py --base http://localhost:8080
```
