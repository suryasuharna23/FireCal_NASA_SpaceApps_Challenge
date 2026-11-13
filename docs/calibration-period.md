# Calibration period (T-10)

**Decision:** `CALIBRATION_PERIOD=2013-01:2021-12`, with the hold-out validation years of
T-13 (`TEST_YEARS`) removed from the fit. The merged series switches from MODIS to
harmonized VIIRS after the end of this period (FR-D-10).

## Why this window

| Bound        | Reason                                                                                                                                                                                                                         |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Start 2013-01 | VIIRS 375 m (S-NPP) starts on 20 January 2012. 2012 is treated as a ramp-up year, so calibration starts with the first full year after it.                                                                                  |
| End 2021-12  | Terra (from 2020) and Aqua (from 2021) stopped inclination-control manoeuvres; their equator crossing times drift later from 2022 onward, which changes MODIS diurnal sampling and therefore the MODIS/VIIRS ratio. |
| In between   | VIIRS counts are normalized per active satellite, so NOAA-20 joining in April 2018 does not change the scale. NOAA-21 (2024) falls outside the window.                                                                       |

## How to re-check it on the full archive

```bash
uv run firecal overlap             # writes processed/reports/overlap.json and overlap_ratios.csv
jupyter lab pipeline/notebooks/T-10_overlap_analysis.ipynb
```

`firecal overlap` keeps the longest contiguous run of full years (after the VIIRS start
year, up to `--drift-year`) whose global ratio stays within `--tolerance` (default ±15 %)
of the median. If it suggests a shorter window, for example because one exceptional fire
season distorts a year, update `CALIBRATION_PERIOD` in `.env` and record the reason
here.

## Status

The decision rule and tooling are in place and verified on the synthetic archive, where
the ratio recovered (≈0.31) matches the generator's truth. The window above follows the
known sensor history. Re-run `firecal overlap` once the full FIRMS archive is
ingested and confirm or adjust the window.
