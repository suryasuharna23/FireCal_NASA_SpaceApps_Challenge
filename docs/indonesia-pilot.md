# Indonesia real-data pilot

This pilot uses NASA FIRMS annual country standard-processing CSVs. Data are
downloaded directly from NASA, retained unmodified under `data/raw/Indonesia/`,
and excluded from Git. No synthetic observations are used.

## Sources and coverage

- Official archive entry point: https://firms.modaps.eosdis.nasa.gov/download/
- Machine-readable catalog: https://firms.modaps.eosdis.nasa.gov/data/country/yearly_summary_files.txt
- MODIS: annual files for 2000-2025 (the record starts in November 2000).
  The version audit found codes `6.2` (2000-2017), `6.03` (2018-2022), and
  `61.03` (2023-2025). A homogeneous C6.1 history has not been verified; the
  earlier blanket C6.1 label was incorrect for this pilot.
- VIIRS S-NPP: annual files for 2012-2025.
- VIIRS NOAA-20 (`viirs-jpss1`): annual files for 2018-2025.
- NOAA-21 and 2026 are not included in this historical pilot.

`archive_manifest.json` records the original URLs, catalog timestamps, byte sizes,
SHA-256 checksums, row counts, detection date ranges, satellite codes, and reported
versions on new downloads. `source_versions.json` audits ingested version codes.
The downloader refuses missing expected product-years and does not publish a
truncated download as a CSV. Completed files are reused on retry.
Use `--reuse-catalog` to resume with the saved catalog during a NASA outage.

The FireOps reference implementation was inspected at
`backend/fireops/ingest/firms_nrt.py` and
`backend/fireops/data_prep/firms_weather.py`. It downloads public SouthEast Asia
24-hour/7-day feeds with retry/cache handling and spatial filtering. Those feeds
are useful for recent snapshots; they cannot supply the missing 2026 history or
the multiyear calibration record. Recent snapshots are kept out of this run to
avoid turning the intervening missing months into apparent zero-fire months.

## Reproduce

From the FireCal repository root, install the locked dependencies, then run:

```powershell
uv sync --all-packages --locked
uv run firecal download-archive --country Indonesia --start 2000 --end 2025
uv run python scripts/prepare_indonesia.py
uv run python scripts/verify_indonesia.py
```

The local `.env` uses `COVERAGE_BBOX=94,-12,142,7` and the existing defaults:
`CALIBRATION_PERIOD=2013-01:2021-12`, `TEST_YEARS=2016,2019`,
`GRID_RES_DEG=0.25`. A MAP_KEY is not required for these annual downloads.
The preparation script rejects unmanifested CSV inputs, preserves raw downloads,
and rebuilds the derived tables in the configured `DATA_ROOT`.

The script creates an Indonesia land-cell grid, administrative region table,
clean points, monthly counts, calibration coefficients, harmonized series, globe
cube, point weights, and hold-out validation report. Natural Earth provides the
country/province boundaries. Latitude bands supply the existing coarse regional
fallback; an ecological biome map has not been supplied for this pilot.

## Interpretation

The preselected calibration window is retained independently of held-out results;
2016 and 2019 are excluded from fitting. Overlap diagnostics are recorded without
automatically changing the calibration window. Targets are Pearson r >= 0.9 and
absolute aggregate bias <= 10%; failure is recorded and must not be described as
validated harmonization.

`validation.json` uses the existing key `global` for the aggregate of the loaded
dataset. Here that means Indonesia only. A country-wide pass does not establish
accuracy for every province, grid cell, satellite, or future year. The 90%
intervals are model estimates; their empirical coverage has not been established.

All generated outputs and the manifest live in `data/processed/`, including
`reports/indonesia_pilot.json`, `reports/validation.json`,
`reports/validation_series.csv`, and `reports/validation.png`. The pilot's
coverage and actual included satellites are recorded in `meta.json`.

The verification script checks three provinces with area-weighted grid cells,
reconciles point weights with the harmonized cube, and exercises the actual API
and CSV downloads. It adds provincial failures to `validation.json` limitations
so the methodology API reports them alongside the country-wide metrics.

## Run results (14 November 2026)

- Data version: `a9443c4efd84`.
- 48 verified source files; 503,428,055 bytes; 6,355,534 raw detections.
- MODIS: 1,533,411 raw -> 1,342,820 retained.
- VIIRS: 4,822,123 raw -> 4,256,142 retained.
- 302 months, November 2000-December 2025; last detection 31 December 2025.
- 282,784 active cell-month records over 3,234 cells.
- Calibration: 2,166 cell coefficients and 1,068 regional fallbacks.
- Hold-out evaluation: 24 monthly totals across 2016 and 2019.

| Area | Correlation r | Bias | MAE (detections/month) | Meets target |
| --- | ---: | ---: | ---: | --- |
| Indonesia aggregate | 0.9992 | -5.86% | 359.33 | Yes |
| Riau | 0.9950 | -13.81% | 70.76 | No |
| South Sumatra | 0.9979 | -12.82% | 66.33 | No |
| Central Kalimantan | 0.9997 | -9.16% | 81.69 | Yes |

The aggregate raw VIIRS-per-satellite bias was +391.96%, reduced to -5.86% after
harmonization. Riau and South Sumatra retain systematic underestimation beyond
the 10% target. These outputs are an initial calibrated dataset with documented
regional limitations. Regional accuracy needs further work before wider use.

The overlap diagnostic suggests 2013-2019; the preselected 2013-2021 window was
retained for this first evaluation. Any model/window revision needs training-only
selection and a fresh evaluation protocol, rather than tuning to these hold-outs.

The subsequent [regional audit](regional-audit-findings.md) found that only 9 of
27 training-eligible provinces pass on 2022-2025. The country aggregate still
passes, but that does not establish regional validity. The serving dataset is
marked experimental, and its original coefficients are retained.

To extend through 2026, acquire the missing standard-processing/NRT history with
the FIRMS archive/API and inspect per-satellite availability before appending
recent public feeds. NOAA-21 needs its own coverage audit. The default historical
reference range (2003-2022) is fully within this pilot's archive period.
