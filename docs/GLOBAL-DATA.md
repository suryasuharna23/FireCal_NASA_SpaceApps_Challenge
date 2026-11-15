# Worldwide observations for the latest three months

The repository includes a real NASA FIRMS worldwide snapshot for **15 August through
15 November 2026**, inclusive. This is three calendar months back from the requested
date, so August and November are partial calendar months. It is not the earlier
January/April/July size-study sample.

The pinned release contains **19,071,898 detections**, version `fdc638723260`.
Its repository archive is **231,462,795 bytes** (about 231 MB), stored in 221
checksum-verified pieces. Installed point files occupy 224,106,556 bytes and the
hourly globe summary occupies 9,640,591 bytes, plus small metadata and receipts.
The original CSVs used to build it total 1,588,044,656 bytes and remain local.

Run `./run.sh` on Linux/macOS or `.\run.ps1` on Windows. Both install the pinned data
from normal Git pieces, verify checksums, and start the application. No separate
download account, LFS, or NASA key is needed to use the saved observations.

Under the globe, change **Data coverage** to **Worldwide · last 3 months**. Choose
month, day, or UTC hour; enter a location and radius under Area, or upload its
GeoJSON boundary, to inspect detections. The Indonesia history
remains available as a separate choice. Shared links retain the coverage choice.

## What the counts mean

The worldwide snapshot includes MODIS (Terra/Aqua) and the three VIIRS platforms:
S-NPP, NOAA-20, and NOAA-21. For each platform and date, standard processing (SP)
takes priority; near-real-time data (NRT) supplies the subsequent available dates.
SP and NRT windows do not overlap for a platform.

Every returned detection is retained. These are satellite detections, not unique
fires; several satellites can observe the same fire. The Indonesia confidence and
duplicate filters are not applied to this separate raw dataset. No Indonesia
calibration coefficient is applied worldwide, and no global historical anomaly or
confidence interval is fabricated. Historical calendars and their comparisons are
available in the Indonesia view.

NASA reported MODIS SP through 31 August and VIIRS SP through 31 July at acquisition.
The later dates use NRT. MODIS, NOAA-20, and NOAA-21 were available through 15 November;
**S-NPP was available only through 2 November**. Metadata and the interface disclose
this difference. Successful requests do not establish uninterrupted satellite
observation coverage.

The globe uses hourly counts on a 0.5-degree grid, summed for the selected period.
If more than 5,000 occupied cells would be drawn, the API combines adjacent cells
into larger cells until all occupied cells fit. The response gives the actual
resolution; counts and regions are retained. Area detail queries read the saved
points, independently of this globe display resolution.

## Installation and updates

`uv run firecal bootstrap` verifies and installs both the existing Indonesia release
and the worldwide release. The worldwide bundle contains normalized observation
points, hourly summaries, metadata, source request receipts and original response
checksums. Original NASA CSV downloads remain in the acquisition workspace; they
are not an additional committed copy of the same observations.

Files are pinned by `datasets/global/recent/dataset.json`. Installed observations
live under `data/global/snapshots/<version>`. Neither the NASA key nor local `.env`
is included in the bundle.

`uv run firecal serve` checks both datasets for newer NASA observations at startup
and hourly. Set `FIRMS_MAP_KEY` in the root `.env` to enable downloads. To update
only the worldwide window once, run:

```sh
uv run firecal global-update
```

Updates use successful request dates as cursors, recheck recent NRT dates, and
replace covered provisional dates when SP becomes available. The retained window
moves forward with the UTC date. Every update builds a complete separate version;
the serving pointer changes only after its points and summary counts reconcile.
The original repository snapshot stays pinned.

Unavailable source dates cause an error rather than an invented zero. Missing
credentials or NASA failures are shown explicitly; any last successful real
version stays dated and is not advertised as newly verified. Older local update
versions are retained, so disk use can exceed the single installed snapshot size.

## API

```text
GET /meta
GET /globe?scope=global&mode=raw&year=2026&month=11
GET /globe?scope=global&mode=raw&year=2026&month=11&period=hour&day=15&hour=6
POST /points  {"scope":"global", "year":2026, "month":11, "aoi": <GeoJSON geometry>}
```

`/meta.global` reports its own dates, version, platform coverage, provisional status,
limitations and update status. Unsupported global harmonization or dates outside
the installed window return HTTP 422. Missing global data returns HTTP 503; the API
does not substitute Indonesia observations.

## Reproduce the snapshot

From the repository root, with a NASA key configured:

```sh
uv run python scripts/acquire_global.py --start 2026-08-15 --end 2026-11-15
```

Downloads are checkpointed under `data/interim/global-recent-20261115`. The NASA
transaction quota may require pauses. Responses are checked for dates, coordinates,
size and checksum before normalization. Each normalized file's count is reconciled
to its receipt, and the complete hourly summary reconciles to the point total.
The `--package` option creates repository pieces when no pinned worldwide catalog
exists; it refuses to replace an existing catalog automatically.

## Release verification

The [offline installation check](reports/global-20261115/offline-install.json)
assembled all 221 repository pieces into a separate temporary installation without
credentials or NASA requests. All 19,071,898 point rows matched the hourly summary.

The [running application check](reports/global-20261115/app-verification.json)
compared every available month's globe total, a daily view, an hourly view, and
areas in South America, Africa and Australia with the installed point files.
The first automatic NASA refresh added 231 detections, giving 19,072,129 observations
in local live version `4ba58bbda51d`. This live version is separate from the pinned bundle.

The [browser check](reports/global-20261115/browser-verification.json) confirmed
visible hotspot features, foreign area selection, coverage switching, daily/hourly
responses, and desktop/mobile layouts without page errors or horizontal overflow.
