# Fixed-coefficient bias audit: continuation protocol

Prepared 14 November 2026 for `feat/firms-api-acquisition`, following commit
`54a2ed9` and the supplied [handover](handover-bias-audit.md). This protocol defines
diagnostics, not a replacement model. Report the existing national/regional
failures even when a satellite subset makes one result look better.

## Inputs and immutability

The default input is experimental snapshot `593ae2d95fdf`, under
`data/interim/indonesia-extended-20261114/processed`. Retain the original
acquisition directory, including plan, availability, progress, all eight source
manifests, CSV responses and receipt sidecars. Retain the previous
`regional-audit/selection_lock.json`. These ignored local files are absent from
a fresh Git clone; the continuation does not redownload them automatically.

Before aggregation, hash all consumed files and relevant source/protocol files.
Record the Git commit, actual code hashes, grid resolution, calibration window,
test years, data version, and analysis windows. Recheck hashes before publishing.
Never overwrite a prior audit directory. Never run the existing verifier against
the frozen input as a preparation step: it rewrites snapshot reports.

The input manifest is written before numerical aggregation. A failed run retains
that lock but has no completed `audit.json`; choose a new output directory for
a subsequent attempt. Missing prerequisite inputs produce no audit directory.

The audit reads the saved coefficients without calling calibration. It writes
only a new audit directory, not `.env`, serving products, snapshot reports, or
the previous selection lock. Receipt path relocation uses expected filenames
inside the acquisition tree rather than following paths from the old computer.
Credential-bearing URLs and `.env` contents are not copied into audit manifests.

## Baseline and accounting

1. Compare full retained counts by platform/source/date with the saved
   `satellite_source_counts.csv` and clean totals in `extended_summary.json`.
2. Verify receipt completeness/checksums separately from retained clean counts:
   bbox responses precede country/quality filtering and cannot equal clean totals.
3. Reconcile per-cell MODIS/VIIRS counts and global-month satellite divisors
   against `grid_monthly.parquet` before computing diagnostics.
4. Reproduce every row in the saved `regional_regression.csv`, including all
   provinces, national results, eligibility and target status. Do not restrict
   output to the successful provinces. Eligibility remains >=1,000 training
   MODIS counts weighted by province overlap. Report the three pilot provinces.
5. Compare MODIS with `sum(k_cell * VIIRS_cell / divisor * area_fraction)` for
   every diagnostic period, including pre-transition months. Do not substitute
   the merged historical MODIS series for a VIIRS prediction.

Keep zero-detection province months when the global subset divisor is positive.
If an entire selected satellite subset has no retained detections in a month,
its divisor is zero and its prediction is unavailable, not an observed zero.
Reports show requested, usable, and unavailable month counts. The absence of
detections never establishes valid observation exposure.

## Fixed diagnostic family

All calculations retain the snapshot's `k` values:

- Baseline: S-NPP, NOAA-20, NOAA-21 together.
- Leave-one-platform-out: each of the three VIIRS platforms omitted in turn.
- Single-platform diagnostics: each VIIRS platform on its own.

Recompute the divisor using distinct retained VIIRS satellites in the **same
scenario and month across the complete input geography**, before selecting an
AOI. Do not derive the divisor from a province or leave the three-satellite
divisor in place after removing a platform.

Compare every prediction with combined Terra+Aqua observations. Also display
Terra and Aqua separately, clearly labeled uncalibrated reference comparisons;
the conversion was fitted against combined MODIS. No subset is selected as a
new model based on its 2026 result.

Output monthly counts, denominator, prediction, residual, platform counts,
source versions and area. Output baseline platform/source/version contributions:
VIIRS contributes positive converted counts, MODIS contributes negative observed
counts, and their sum is the total residual. This identity is accounting, not
causal attribution of bias to an instrument or SP/NRT algorithm.

## Periods and metric interpretation

Report known 2016/2019, known 2022-2025, each 2022-2025 year separately, and:

| 2026 period | Handover description to check against actual records |
| --- | --- |
| January-July | SP/SP comparison |
| August | MODIS SP versus VIIRS NRT |
| September-October | NRT/NRT, complete calendar months but exposure unresolved |
| November | Partial through November 14, S-NPP availability reported through November 2 |

The period labels in code intentionally do not assert source modes; inspect
`retained_platform_source_versions.csv` for the actual modes/versions.

Bias is `(sum(predicted)-sum(observed))/sum(observed)`; MAE is mean absolute
monthly residual. Show bias/MAE even for a single month. Correlation requires at
least three paired months and variation in both vectors. A zero MODIS total
leaves percentage bias undefined. Missing predictions remain missing. A partial
month never establishes a full-month accuracy target.

The historical verifier omits every metric for a zero-total reference. Baseline
reproduction accommodates that legacy convention while new diagnostics can
still show an absolute error for such an area. Target status is assessed only
for complete requested pairs with defined r and bias, combined MODIS reference,
and a non-partial period. No claim of independent accuracy follows from a pass.

## Exposure evidence

NASA's [outage notices](https://firms.modaps.eosdis.nasa.gov/content/notifications/firms/outages.html)
describe platform disruptions and quality cautions; these are evidence worth
investigating, not Indonesia-specific valid-observation exposure measurements.
The notice history includes S-NPP interruptions during 2026 and a brief NOAA-21
gap in July. No numerical bias contribution is assigned to them here.

The [missing-data page](https://firms.modaps.eosdis.nasa.gov/api/missing_data/)
describes daily gaps by satellite/product and limits displayed NRT gaps to dates
after standard availability. On 14 November 2026 its public table returned a
load failure, so no row-level gap inventory was obtained in this continuation.
There is no assumption that an empty table means zero outages.

See [the evidence register](bias-audit-exposure-evidence.csv). Preserve retrieval
time, platform, product, interval, geography, status and URL for later additions.
Resolve notice inconsistencies and obtain missing-data records or valid swaths
before calculating exposure fractions. Classify request success with zero
detections, confirmed upstream notices, and unknown exposure separately. Never
use the number of detection-bearing days as valid-observation days.

## Conditional next evaluation, not a selected correction

No correction is chosen until the real-data diagnostic tables are available.
The following hypotheses require additional evidence:

- If valid swath exposure demonstrates partial sampling, compare a denominator
  based on measured platform/time/area exposure with the detection-based divisor.
- If matched same-place/same-time SP/NRT products show systematic processing
  differences, estimate a processing adjustment using development data only.
- If platform effects persist after controlling exposure and processing, compare
  platform-aware calibration with the frozen baseline. A smaller bias from
  excluding NOAA-21 alone does not establish a NOAA-21 defect.

Before fitting any candidate, lock its exact definition, evidence inputs,
training years, candidate family, eligibility and selection rule in a new
versioned protocol. The old seven training years and known evaluation spans
remain development/regression evidence. Do not call them fresh hold-outs.

A possible genuinely prospective evaluation is the complete months December
2026-November 2027, using standard products once available, with predictions and
all choices locked before viewing those outcomes. This is a proposed future
window, not a completed or available dataset. Record any later exposure-data
revision and postpone rather than replace missing months opportunistically.

For a future finite candidate family, use training-only leave-one-year-out
selection and a predeclared rule: >=5% improvement in eligible-province macro
normalized MAE, no worse macro absolute aggregate bias, and no lower regional
pass share. Report national and every eligible province separately, including
all failures and incomplete evidence. Predictive intervals need their own
coverage assessment. No serving promotion is automatic.

## Commands and outputs

From the branch checkout:

```powershell
uv run --no-sync python scripts/audit_indonesia_bias.py --check-inputs
uv run --no-sync python scripts/audit_indonesia_bias.py
```

For a transferred dataset, pass explicit `--processed`, `--acquisition`, and
`--prior-audit` directories. Relative paths are resolved from the working
directory. Old absolute receipt paths are not used. Choose a new `--out` for
each frozen run. `--expected-version` must agree with the supplied snapshot;
changing it is an explicit different-input audit, not a reproduction of hsbu's.

| Output | Purpose |
| --- | --- |
| `input_manifest.json` | Input/code hashes and frozen configuration |
| `monthly_sensitivity.csv` | All areas/months/scenarios, platform counts and divisors |
| `platform_source_contributions.csv` | Baseline accounting by platform, SP/NRT, version |
| `period_metrics.csv` | All scenarios, references, periods and areas |
| `retained_platform_source_versions.csv` | Actual monthly retained source composition |
| `request_exposure_inventory.csv` | Saved request evidence; exposure explicitly unknown |
| `satellite_source_counts.csv` | Independently recomputed retained count/range table |
| `audit.json` | Reconciliation, baseline reproduction, national result and limitations |

Sensitivity outputs also include changes in prediction, bias (percentage points)
and MAE from the baseline. These changes describe arithmetic sensitivity, not
evidence that the best-looking subset is a valid correction.

Numerical execution is incomplete until the real inputs have been transferred
and every baseline check succeeds. A tested runner is not a completed bias audit.
