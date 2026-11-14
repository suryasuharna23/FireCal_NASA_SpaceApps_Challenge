# Calibration period (T-10)

**Decision:** `CALIBRATION_PERIOD=2013-01:2021-12`, with the hold-out validation years of
T-13 (`TEST_YEARS`) removed from the fit. The merged series switches from MODIS to
harmonized VIIRS after the end of this period (FR-D-10).

## Why this window

| Bound        | Reason                                                                                                                                                                                                                         |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Start 2013-01 | VIIRS 375 m (S-NPP) starts on 20 January 2012. 2012 is treated as a ramp-up year, so calibration starts with the first full year after it.                                                                                  |
| End 2021-12  | Terra (from 2020) and Aqua (from 2021) stopped inclination-control manoeuvres; their equator crossing times drift later from 2022 onward, which changes MODIS diurnal sampling and therefore the MODIS/VIIRS ratio. |
| In between   | VIIRS counts are normalized per active satellite to approximate platform-count changes when NOAA-20 joins in April 2018. NOAA-21 SP availability starts in March 2023, outside the window. Partial exposure remains uncorrected. |

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

The decision rule and tooling were initially verified on the synthetic archive,
where the recovered ratio (≈0.31) matches the generator's truth. The real-data
Indonesia pilot is now processed, including an isolated extension through
14 November 2026. Its historical overlap diagnostic suggested 2013-2019; the
preselected 2013-2021 window was retained, excluding 2016 and 2019 from fitting.

The [regional audit](regional-audit-findings.md) and
[extended snapshot report](indonesia-extended.md) document regional and temporal
transfer failures. No revised window or model was selected using these observed
evaluation results. Further selection requires a new evaluation protocol.
