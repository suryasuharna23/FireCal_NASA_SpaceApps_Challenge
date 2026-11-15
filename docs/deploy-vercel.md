# FireCal on Vercel

Production frontend: <https://firecal-nasa-spaceapps.vercel.app>

Production API: <https://firecal-nasa-api.vercel.app>

The frontend is the Vite app in `web/`. Its Vercel project uses Node 22, `pnpm build`, `dist`, and `web/vercel.json` for single-page routes. Set `VITE_API_BASE_URL=https://firecal-nasa-api.vercel.app` in the frontend project's Production and Preview environments. Vite embeds this public URL at build time.

The API is a **read-only snapshot** of the processed Indonesia dataset, hosted as a separate FastAPI Vercel project. Its `CORS_ORIGINS` includes the exact frontend production origin. The snapshot currently ends on 2026-11-14. It does not refresh automatically: deploying new frontend code or pushing to GitHub does not update the observations.

## Redeploy the API snapshot without committing data

The source observations in `data/interim/` are deliberately ignored by Git. To publish a newer local snapshot, update `data/live/current.json` through the pipeline, then stage a copy:

```sh
.venv/bin/python scripts/stage_vercel_api.py
```

The command prints a new `data/interim/vercel-api-stage-*` directory. It copies the API and processed dataset, then recompresses point partitions without dropping records so the CLI upload stays under the Vercel Hobby 100 MB source limit. From that directory, link to the existing `firecal-nasa-api` project and deploy:

```sh
cd data/interim/vercel-api-stage-YYYYMMDD-HHMMSS
vercel link --project firecal-nasa-api
vercel deploy --prod
```

Check `https://firecal-nasa-api.vercel.app/health` and `/meta` after the deployment. For local development, the frontend still defaults to `http://localhost:8000` unless `VITE_API_BASE_URL` is set.

## Frontend Git integration

The frontend Vercel project is connected to this repository with **Root Directory `web`**. Changes pushed to `main` build and deploy the frontend. The API snapshot remains a local CLI deployment because its 86 MB of processed data is not committed to Git. Keep `web/public/logo/` in Git so the deployed logo and favicon remain available on Git builds.
