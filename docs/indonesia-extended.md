# Indonesia extension through 14 November 2026

The downloaded snapshot is complete against its saved request plan: 463 FIRMS
API responses across eight SP/NRT sources, containing 3,015,711 bbox detections.
This verifies request completeness and file integrity, not uninterrupted sensor
observation coverage. Raw responses, checksums, dates and quota receipts remain
under `data/interim/api-acquisition/`; credentials are excluded.

The new experimental dataset is stored separately at
`data/interim/indonesia-extended-20261114/processed/` with version
`593ae2d95fdf`. The historical serving dataset and `.env` are unchanged.

## Preparation and outputs

All 48 historical country files and the new API responses were filtered using
the same Natural Earth 10m Indonesia pixel-centre polygon. The resulting
8,779,922 staged detections include one duplicate removed during the NRT merge.
Confidence/static-source filtering retains 7,716,551 detections:
1,469,069 MODIS and 6,247,482 VIIRS.

The snapshot spans 313 months, November 2000-November 2026, with detections through
14 November 2026. It includes Terra, Aqua, S-NPP, NOAA-20 and NOAA-21. NOAA-21
starts on 1 March 2023. SP and NRT are staged separately and merged before
cleaning, gridding and harmonization; each retains its provenance. Historical
MODIS version heterogeneity remains unresolved.

Calibration retains the preselected 2013-2021 window excluding 2016 and 2019.
No candidate model selection or tuning to 2026 results was performed. The new
common country mask changes the historical coastal selection, so this is a new
snapshot with its own recalculated baseline coefficients. Excluded coastal
pixels are not established false detections.

Key outputs inside the processed directory:

- `harmonized.parquet`: harmonized cell-month series.
- `meta.json`: coverage, versions and experimental status.
- `reports/country_filter.json`: input/output checksums and geographic selection.
- `reports/extended_summary.json`: processing counts and validation summary.
- `reports/extended_verification.json`: real API/CSV and point-weight checks.
- `reports/satellite_source_counts.csv`: actual retained satellite/date coverage.
- `reports/regional_regression.csv`: all 33 administrative regions and Indonesia.
- `reports/validation.json`: metrics and explicit limitations exposed by the API.

## Verification and interpretation

Point weights reconcile with the harmonized cube to a maximum absolute error
of 1.74e-11. Calendar, statistics, points and monthly CSV checks pass for Riau,
South Sumatra and Central Kalimantan across the eleven 2026 months. The globe
and metadata endpoints also pass against the isolated dataset.

Code validation: 126 Python tests passed, Ruff lint/format checks passed, and
`git diff --check` passed. The test run reports one dependency deprecation warning
from Starlette's HTTPX-based TestClient.

Targets remain r >= 0.9 and absolute aggregate bias <= 10% against MODIS.
These are descriptive checks using already known periods; they are not fresh
independent hold-outs or confirmation of actual fire counts.

| Period | National r | National bias | Eligible provinces meeting both targets |
| --- | ---: | ---: | ---: |
| 2016 and 2019 | 0.9992 | -6.20% | 12/27 |
| 2022-2025 | 0.9949 | -2.88% | 9/27 |
| January-October 2026, provisional | 0.9944 | -12.20% | 8/27 |

Province eligibility uses at least 1,000 training MODIS detections weighted by
province overlap. Monthly metrics retain zero-detection months. Administrative
boundaries are inherited from the historical 33-province pilot and do not
represent all current Indonesian administrative divisions.

The national 2026 bias misses the target. Regional transfer, including transfer
to NOAA-21, needs further investigation. November is excluded from the above
comparison because the snapshot ends on 14 November and S-NPP availability ends
on 2 November. The existing monthly satellite-count divisor does not correct
partial-month exposure or other outages. SP/NRT differences and mixed MODIS
versions also limit interpretation; correlation alone cannot resolve them.

## Reproduce from the saved downloads

Run from the repository root with its locked environment:

```powershell
uv run --no-sync python scripts/prepare_indonesia_extended.py
uv run --no-sync python scripts/verify_indonesia_extended.py
```

Preparation verifies the saved plans and every source checksum, reuses verified
country-filtered staging files, and rebuilds the isolated derived output.
Verification selects that output only inside its own process; it does not edit
the serving configuration. No further API downloads are needed for this snapshot.

The next model investigation should separate SP/NRT and satellite-specific
effects, review sensor observation exposure, and establish a new evaluation
protocol before selecting any correction using these now-observed results.
