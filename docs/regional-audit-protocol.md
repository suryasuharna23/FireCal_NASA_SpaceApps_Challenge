# Regional harmonization audit protocol

The Indonesia pilot (`a9443c4efd84`) passes the country aggregate target but
underestimates held-out totals in Riau and South Sumatra. This audit investigates
the implementation and records candidate selection before reading the unused
2022-2025 evaluation outcomes. The 2016/2019 results are already known and are
treated as regression checks, not a new independent test.

## Data and checks

- Preserve the existing processed dataset; experiment outputs go under
  `data/interim/regional-audit/`.
- Reconcile monthly totals against per-satellite point counts and recorded
  active-satellite denominators. Detection-free days are not evidence of a
  satellite outage, so detection counts must not be used as observation exposure.
- Inspect training residuals by year, province, and cell/fallback method.
- Keep the 2013-2021 calibration window and exclude 2016 and 2019 throughout.

## Finite candidate family

Compare the existing ratio/shrinkage estimator with these fixed choices:

1. Regional prior: existing latitude bands, or administrative provinces (dominant
   province/cell overlap). Administrative strata are explicitly not biomes.
2. Shrinkage pseudo-count: 0, 25, 100 (existing), or 400. Minimum cell/region counts
   remain 50/500.
3. Optional regional training-total correction: after shrinkage, multiply cell
   coefficients by the training observed/predicted regional total ratio. This
   checks whether shrinkage loses regional mass. It uses training rows only.

The 16 configurations include the unchanged baseline (latitude, 100, no correction).
No calibration-window, satellite-exposure, or filter tuning is included.

## Selection and evaluation

- Leave one training year out at a time over 2013, 2014, 2015, 2017, 2018, 2020,
  2021. Predict all 12 months of each excluded year.
- Score every province with at least 1,000 observed MODIS detections over those
  training years, determined without inspecting either evaluation period.
- Primary score: equal-province mean of MAE / mean observed monthly count.
- Prefer baseline if improvement is below 5%, macro absolute aggregate bias
  worsens, or the share meeting r >= 0.9 and absolute bias <= 10% decreases.
- Save the selected configuration, selection scores, source SHA-256, and protocol
  SHA-256 before reading 2022-2025 outcomes.
- Refit on the same seven training years. Evaluate baseline and the locked
  candidate on known 2016/2019 and untouched 2022-2025, per province and nationally.
- Report every eligible province, the named three pilot provinces, and years
  separately. Do not retune after this evaluation. Report uncertainty and failures;
  the later MODIS record is a reference with its own limitations, not fire truth.
- Do not replace the serving dataset automatically. A selected candidate remains
  experimental until its evidence and geographic coverage are reviewed.

## Sensor coverage references

NASA's FIRMS outage notices and missing-data API provide observation-gap evidence:
https://firms.modaps.eosdis.nasa.gov/content/notifications/firms/outages.html
and https://firms.modaps.eosdis.nasa.gov/api/missing_data/ . A full exposure-aware
model requires those records or valid-observation swaths; dividing by the count
of satellites with any detections is only an approximation.
