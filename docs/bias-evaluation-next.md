# Next model evaluation: proposal locked before fitting

Date: 14 November 2026. Based on the [completed diagnostic audit](bias-audit-findings.md).
No candidate has been fitted, selected or promoted under this proposal. The
[JSON lock](bias-evaluation-next-lock.json) records the exact scope and rules.

## Decision and evidence gate

Retain snapshot `593ae2d95fdf` and the current serving model. The audit does not
support solving the problem with NOAA-21 exclusion or a multiplier chosen from
the known 2026 national error.

Before a correction experiment begins, obtain valid-observation coverage by
cell/month/platform/product and the relevant source processing versions. A
minimum evidence table needs `cell_id`, date or acquisition interval, platform,
source mode, valid observed area/time, expected observable area/time, quality
definition, source URI, retrieval time and checksum. The upstream definition of
an observation opportunity must be documented and comparable within a platform.

Missing-day flags alone do not meet this gate. In particular, the 31 flagged May
days with retained S-NPP observations cannot be treated as 31 completely lost
days. No exposure fraction will be inferred from fire-bearing days.

Define cell-month effective exposure `e_p` as valid observed opportunities
divided by expected opportunities for the **same platform**, using the approved
coverage data. The value must be finite in [0,1]. Audit spatial/temporal coverage
and distinguish cloud/quality exclusion from spacecraft/processing outage.
Freeze this derivation and its input hashes before fitting. A future scientific
review may reject that exposure definition; if so, version the protocol before
examining any candidate scores rather than silently changing it.

MODIS remains an imperfect reference. Only use reference cell-months with
documented combined MODIS exposure >=0.95 in the exposure-qualified comparison.
Use the same spatial/monthly support for all candidates. Report excluded support
and do not convert unknown exposure to zero. The legacy all-data comparison is
reported separately, so a changed support is not mistaken for improved fit.

Obtain matched-place/date SP and NRT products if a processing-mode correction is
to be proposed. This snapshot has no such matched pairs for its main 2026 regime
transitions, so processing-specific correction is outside the finite family below.

## Fixed development data and candidates

Development uses SP observations in January 2013-December 2025, excluding 2016
and 2019 from fitting. All eleven remaining years are already observed data:
2013, 2014, 2015, 2017, 2018, 2020, 2021, 2022, 2023, 2024 and 2025. Expanding
training beyond the original seven years is an explicit model experiment,
not a revision to the frozen diagnostic baseline.

The original calibration and known 2016/2019, 2022-2025, and 2026 diagnostic
outcomes are not independent evaluation sets. Do not use January-October 2026
to choose a subset, multiplier, window, or hyperparameter. November is partial
and excluded from selection. Any unexpected post-lock investigation is logged
as exploratory and cannot consume the future evaluation for retuning.

Use exactly four development configurations, all with the original confidence
and country filters, 0.25-degree grid, latitude priors, shrinkage 100 and
cell/region evidence thresholds 50/500:

| ID | Definition | Purpose |
| --- | --- | --- |
| B0 | Original ratio estimator and original seven fitting years; detection-based divisor | Reference algorithm, refitted correctly within each CV fold |
| B1 | Same estimator/divisor on the eleven development years | Isolate the effect of expanding the fitting window |
| E1 | Eleven years; fit shared cell ratio using `v_norm = sum(n_p)/sum(e_p)` | Test an evidence-based effective-platform divisor |
| E2 | Eleven years; fit a separate shrunk `k_cell,p` per platform from `n_p/e_p`; predict `sum(k_cell,p * n_p)/sum(e_p)` | Test platform-specific conversion in addition to measured exposure |

For E2, fit each platform's ratio only on qualifying MODIS/platform month pairs;
use the corresponding platform's regional then global prior when cell evidence
is sparse. A platform with no training support is not silently assumed equivalent:
its prediction is unavailable and the affected evaluation support is reported.
NOAA-21 enters available SP development data in March 2023, not the old 2013-2021
window. Fit no platform-specific prior using evaluation-period observations.

Do not add a shrinkage grid or processing correction after looking at scores.
New hypotheses require a new versioned protocol before new model fitting.

## Training-only selection

1. Keep the audit's existing 27 eligible province names frozen in the JSON lock.
   Report all 33 source provinces and national results, but do not improve the
   headline score by changing eligibility after seeing errors.
2. Leave one development year out at a time. Every candidate is refitted without
   that year; B0 is not allowed to use its saved coefficients on a year that was
   part of the old fit. When a fold year falls outside B0's fitting window, its
   old fitting years are still used without adding the fold year.
3. Evaluate all twelve months of each fold where common exposure-qualified
   support is established. Keep genuine zero-detection months, and report unknown
   support separately. Compare candidates only on the same documented support.
4. Primary score: equal-province mean normalized MAE. Normalize each province by
   its frozen mean monthly MODIS count over eligible development support.
   Report absolute errors as well so low-volume regions are interpretable.
5. Accept a non-baseline candidate only if macro normalized MAE improves by at
   least 5%, macro absolute aggregate bias does not worsen, and the regional
   combined-target pass share does not decrease. Otherwise retain B0.
6. Rank qualifying candidates by primary score; ties at numeric tolerance retain
   the simpler configuration in order B0, B1, E1, E2.
7. Save selection scores, complete candidate definitions, support masks, input/code
   hashes and selected model before retrieving the prospective outcome data.

Qualification is not automatic model approval. If coverage evidence cannot
support the predeclared comparisons, report the experiment as not assessable.
Do not score a different support for each model and call the comparison fair.

## Genuinely prospective evaluation

The planned untouched window is **December 2026-November 2027**, twelve complete
future months. At this protocol date those months have not occurred. Use standard
products when published, with NRT comparisons kept as a separately labeled
provisional report. Lock candidate choices before reading either future stream.

Evaluate the selected candidate and frozen operational baseline nationally and
for every frozen eligible province, plus all other source provinces descriptively.
Report bias, MAE, correlation, sample counts and missing exposure. Targets remain
r >=0.9 and absolute aggregate bias <=10%. A partial or unsupported regional
window is not counted as a target pass; do not remove difficult months to qualify.

The primary future comparison remains on common documented support, alongside
an all-available operational view with its limitations. Report both so exposure
qualification cannot hide failures. Retain every unsuccessful region. National
agreement alone cannot approve a model for province-level accuracy claims.

Assess predictive-interval coverage separately; the old 90% bounds are not
automatically valid for refitted or exposure-adjusted estimates. Record reference
MODIS limitations and upstream revisions. Use no future result to retune this
same test; a failed candidate returns to a new development/evaluation cycle.

This is a prospective plan, not a scheduled automation, an available dataset,
or a claim that future products/exposure evidence have already been obtained.
The present diagnostic work is complete. Its remaining scientific limitation is
explicit, and model correction remains gated on new evidence and this evaluation.
