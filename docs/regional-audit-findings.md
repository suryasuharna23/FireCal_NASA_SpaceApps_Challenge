# Indonesia regional audit findings

Audit date: 14 November 2026. Baseline data version: `a9443c4efd84`.
The protocol was saved before the first 2022-2025 outcome read; the selection
lock records source/protocol checksums and the timestamp. Repeated runs reuse
that lock. These years have now been examined and are regression data for future
iterations, not a fresh independent test set.

## Findings

1. **Version homogeneity is unverified.** Annual MODIS files report `6.2` for
   2000-2017 (1,269,627 rows), `6.03` for 2018-2022 (170,239 rows), and `61.03`
   for 2023-2025 (93,545 rows). The earlier C6.1-only pilot description was too
   broad. VIIRS rows report `2`; that field alone does not establish the upstream
   type-field processing revision. Preserve original codes and request a
   consistent, documented MODIS archive before treating the record as homogeneous.
2. **No count/denominator implementation mismatch was found.** All 302 monthly
   grid totals and active-VIIRS satellite counts reconcile with the point table.
   This verifies arithmetic, not observation exposure. NASA's outage notices
   document partial-month gaps; a satellite with some detections still receives
   a whole-satellite denominator in the present model. The size of that exposure
   effect has not been quantified here.
3. **Shrinkage alone is insufficient.** Removing shrinkage changes the Riau
   in-sample training bias from -1.01% to -0.14% and South Sumatra from -0.72% to
   approximately zero. These small in-sample shifts do not establish a remedy for
   their larger held-out biases. No single causal explanation has been proven.

The official source references are [NASA's country archive readme](https://firms.modaps.eosdis.nasa.gov/data/country/AttributesReadme.txt),
[missing-data table](https://firms.modaps.eosdis.nasa.gov/api/missing_data/), and
[FIRMS outage notices](https://firms.modaps.eosdis.nasa.gov/content/notifications/firms/outages.html).
The readme is cached under `data/raw/reference/AttributesReadme.txt`.

## Training-only model selection

Sixteen fixed candidates were evaluated by leave-one-year-out CV across seven
training years, excluding 2016/2019. Eligibility was fixed by training MODIS
volume (at least 1,000 detections), yielding 27 provinces.

| Measure | Existing latitude prior, alpha 100 | Best CV candidate: province prior, alpha 100, balanced |
| --- | ---: | ---: |
| Macro normalized MAE | 0.22517 | 0.22081 |
| Macro absolute aggregate bias | 5.59% | 4.39% |
| Provinces meeting both targets | 23/27 | 25/27 |

Normalized MAE improved by only **1.94%**, below the predeclared 5% adoption
threshold. The existing model was selected and retained. The rejected best-CV
candidate was not evaluated on 2022-2025, and no new serving coefficients or
candidate confidence intervals were published.

## Baseline evaluation

| Area | Known 2016/2019 bias | 2022-2025 bias | 2022-2025 correlation |
| --- | ---: | ---: | ---: |
| Indonesia aggregate | -5.86% | -2.38% | 0.9941 |
| Riau | -13.81% | -40.16% | 0.9427 |
| South Sumatra | -12.82% | -12.45% | 0.9952 |
| Central Kalimantan | -9.16% | -13.21% | 0.9976 |

Only **12/27** eligible provinces pass the known hold-outs and **9/27** pass
2022-2025. Country-level metrics hide substantial regional failures. Riau's
year-specific biases are -50.19%, -47.66%, -48.62%, and -13.80% for 2022-2025.
These comparisons use MODIS as a reference, not independent fire truth.

## Changes and reproduction

- The API, CSV/PNG attribution, and Methodology page no longer claim that all
  pilot MODIS data are C6.1. The API exposes actual source versions, dataset scope,
  and experimental status. Methodology displays the dataset's dates and NRT state.
- Provincial and temporal limitations are added to serving metadata with an
  explicit annotation command. Calibrated values and point weights are preserved.
- The downloader now records per-file reported version counts. Preparation writes
  a separate version audit and carries its warnings into validation metadata.

```powershell
uv run python scripts/audit_regional_harmonization.py
# Explicitly add audit limitations to existing metadata:
uv run python scripts/audit_regional_harmonization.py --annotate-metadata
```

Outputs: `data/interim/regional-audit/selection_lock.json`, `evaluation.csv`,
monthly predictions, training diagnostics, candidate coefficients, source version
audit, and normalization checks. Metadata annotation also writes
`data/processed/reports/regional_audit.json`.

CI remains unresolved: Actions run `43568891251` ended `startup_failure` with zero
jobs and workflow path `BuildFailed`; GitHub marks that synthetic workflow as
deleted. All four repository workflow YAML files parse, and actionlint 1.7.12
reports no errors. This evidence does not identify the remote startup cause.

Validation: 111 Python tests and 86 frontend tests pass; Ruff, ESLint, Prettier,
typecheck, production build, and real-data API/CSV checks pass. Frontend tests ran
on Node 22.23.5. The old local Node 22.13.1 cannot load the locked undici version,
so the declared minimum is corrected to 22.19.0. An incomplete accessibility-test
points fixture was also corrected to include the actual API's count field.

Next: acquire consistent documented MODIS processing and valid-observation/gap
metadata; complete 2026 and NOAA-21 with a local FIRMS MAP_KEY. Revise selection
using training data and freeze a new evaluation protocol before inspecting a
fresh period. Avoid promoting a model solely to make the known hold-outs pass.
