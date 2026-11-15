# Included dataset and automatic NASA catch-up

## Included real data

Both complete original archives are included in normal Git as 281 binary pieces
under datasets/indonesia/593ae2d95fdf. The catalog pins every piece and complete
archive by SHA-256. Bootstrap assembles them automatically, verifies all file
manifests, and never overwrites differing existing work. A normal clone contains
the data; no LFS budget or separate ZIP transfer is needed.

The frozen snapshot remains separate from live versions and retains the audit's
known scientific limitations. Original supplied ZIPs remain a supported local
fallback. The failed temporary transport branches from earlier attempts were removed.

## Run it

From the repository root:

```powershell
uv sync --all-packages --locked --python 3.12
uv run firecal bootstrap
# Configure FIRMS_MAP_KEY in root .env for new NASA downloads.
uv run firecal serve
```

Start the frontend in another terminal using the pnpm version in `web/package.json`.
Its default API URL is `http://localhost:8000`.

`serve` uses `data/live/current.json`, seeds it from the saved snapshot, and starts
a background check immediately and every 3,600 seconds. `--refresh-seconds` can
change the interval, with a minimum of 60 seconds. Downloads are server-side;
the browser never receives the MAP_KEY. A missing key leaves the saved snapshot
available and is reported as an unavailable live update.

For existing Uvicorn deployments, select the live pointer explicitly:

```dotenv
DATA_URI=./data/live/current.json
LIVE_AUTO_REFRESH=true
LIVE_REFRESH_SECONDS=3600
LIVE_REPO_ROOT=.
```

Bootstrap must already have completed and the repository/data workspace must be
available to the server. Keep `LIVE_AUTO_REFRESH=false` for an intentionally
frozen audit/API session. The original Docker Compose mounts data read-only and
selects the old processed directory; it does not automatically enable this live
mode. A container enabling refresh needs a writable data volume and the catalog.

## How missing dates are handled

1. Read the current complete version and per-source successful-request cursors.
   Initial cursors come from the frozen acquisition receipts, not from the most
   recent fire detection. A successful zero-detection query still has coverage.
2. Ask NASA for current availability of all MODIS/VIIRS SP/NRT sources.
3. Plan every missing date, split into requests of at most five days. A long gap
   is backfilled in multiple requests rather than only fetching the last five days.
4. Request new standard data first. It supersedes corresponding NRT intervals.
5. Refresh a two-day overlap of available NRT data to include delayed/revised
   observations. Paused platforms are reported using their actual available end.
6. Verify response payloads/checksums and apply the same Indonesia boundary and
   quality/static-source rules as the included snapshot.
7. Replace successfully queried intervals, including revisions to zero, and
   deduplicate detections. No NRT row supersedes a verified SP interval.
8. Rebuild monthly products using the existing coefficients without recalibration.
9. Publish the complete version through an atomic pointer replacement. Only then
   advance the stored cursors. Failed refreshes leave the previous version active.

If NASA no longer offers a missing interval and SP data cannot cover it, the
update fails instead of labeling an incomplete catch-up complete. Request success
does not establish valid satellite observation exposure or prove that no fire
occurred. Source outages and sparse observations remain scientific limitations.

The updater uses an OS file lock to prevent two processes from publishing at once.
Locks release after a crash. Each attempted version keeps its acquisition receipts;
partial/failed working directories are not selected by `current.json`.

## Freshness in the application

The API resolves `current.json` for each request, so new requests select a complete
published version. Existing in-flight requests keep their previous version. Data
version/URI keys separate the API caches, and the browser polls metadata each
minute. A changed data version invalidates its cached calendars, charts and map
queries. Update errors retain the previous visible dataset.

The status bar distinguishes the latest **detection date** from when NASA was
**checked**. A source can legitimately lag. NASA timestamps/date ranges use UTC;
the browser displays check timestamps in the user's locale. Current-day NRT data
are provisional and can change as more observations arrive.

## Actual verification on November 15, 2026

- The original supplied archives were verified exactly. Both
  complete archive checksums and all 1,043 packaged file checksums passed.
- A fresh qualification installation extracted 53 processed-package entries
  and 992 sources-package entries, including their two manifests.
- The provided MAP_KEY was validated and stored only in ignored local `.env`.
  A credential scan of the uncompressed text data found none of that key.
- Three live requests covered November 13-15 for MODIS, NOAA-20 and NOAA-21.
- The published live version is `66c6ba8829e1`, with 7,717,322 retained detections
  and latest acquisition date November 15, 2026.
- S-NPP availability remained November 2; it was flagged as lagging rather than
  labeled current or treated as a verified day-long outage.
- Every frozen snapshot file was unchanged, and coefficient file bytes matched.
- Point weights reconciled with the new cube to `2.70e-11` maximum absolute
  difference. The live-pointer API/calendar/CSV check passed.

These checks establish data integrity and update behavior, not new scientific
accuracy. The original November 14 audit remains reproducible at its own version.

## Operator checks

```powershell
uv run firecal live-update --plan-only
uv run firecal live-update
Get-Content data/live/status.json
Get-Content data/live/current.json
Invoke-RestMethod http://localhost:8000/meta
```

Retain failed download directories when investigating a provider problem. Do not
manually point the API at an unfinished run. `data/live/` is ignored by Git;
the immutable starting snapshot is the included Git data, while fresh observations
are fetched using each running backend's server credential.
