"""Read-only fixed-coefficient diagnostics, never a model-selection procedure.

Counts of satellites with detections are retained as the baseline denominator.
They are not observation exposure. Contributions are an accounting identity,
not causal attribution to instruments or SP/NRT processing.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

VIIRS = ("S-NPP", "NOAA-20", "NOAA-21")
PLATFORMS = {"Terra": "MODIS", "Aqua": "MODIS", **dict.fromkeys(VIIRS, "VIIRS")}
COUNT_COLUMNS = {
    "Terra": "n_terra",
    "Aqua": "n_aqua",
    "S-NPP": "n_snpp",
    "NOAA-20": "n_noaa20",
    "NOAA-21": "n_noaa21",
}
YEARS = (2016, 2019, 2022, 2023, 2024, 2025, 2026)
PERIODS = {
    "known_2016_2019": [(y, m) for y in (2016, 2019) for m in range(1, 13)],
    "known_2022_2025": [(y, m) for y in range(2022, 2026) for m in range(1, 13)],
    **{f"known_{y}": [(y, m) for m in range(1, 13)] for y in range(2022, 2026)},
    "2026_Jan_Oct_provisional": [(2026, m) for m in range(1, 11)],
    "2026_Jan_Jul": [(2026, m) for m in range(1, 8)],
    "2026_Aug": [(2026, 8)],
    "2026_Sep_Oct": [(2026, 9), (2026, 10)],
    "2026_Nov_partial": [(2026, 11)],
}


def metrics(observed: np.ndarray, predicted: np.ndarray) -> dict:
    """Report one-month bias/MAE even when correlation cannot be estimated."""
    obs, pred = np.asarray(observed, float), np.asarray(predicted, float)
    if obs.shape != pred.shape or obs.ndim != 1:
        raise ValueError("Metric inputs must be matching vectors")
    finite = np.isfinite(obs) & np.isfinite(pred)
    o, p = obs[finite], pred[finite]
    total = float(o.sum()) if len(o) else None
    bias = float((p.sum() - o.sum()) / total) if total else None
    has_variation = len(o) >= 3 and np.std(o) > 0 and np.std(p) > 0
    return {
        "months_requested": len(obs),
        "months": int(finite.sum()),
        "months_unavailable": int((~finite).sum()),
        "observed": total,
        "predicted": float(p.sum()) if len(p) else None,
        "residual": float((p - o).sum()) if len(p) else None,
        "bias": bias,
        "mae": float(np.abs(p - o).mean()) if len(p) else None,
        "r": float(np.corrcoef(o, p)[0, 1]) if has_variation else None,
        "r_status": "available" if has_variation else "insufficient_months_or_variation",
        "bias_status": "available" if bias is not None else "zero_reference_or_no_pairs",
    }


def check_counts(counts: pd.DataFrame, coefficients: pd.DataFrame) -> None:
    """Reject ambiguous platforms, non-finite data and missing calibration rows."""
    columns = {"cell_id", "year", "month", "sensor", "satellite", "source", "version", "n"}
    if not columns.issubset(counts):
        raise ValueError("Platform counts do not have the required columns")
    if counts.empty or counts[list(columns)].isna().any().any():
        raise ValueError("Platform counts must be nonempty without missing fields")
    n = counts.n.to_numpy(float)
    if not np.isfinite(n).all() or (n <= 0).any() or (n != np.floor(n)).any():
        raise ValueError("Platform counts must be positive finite integers")
    if not counts.satellite.isin(PLATFORMS).all():
        raise ValueError("Unrecognized satellite; do not silently drop its detections")
    if not counts.sensor.eq(counts.satellite.map(PLATFORMS)).all():
        raise ValueError("Satellite and sensor disagree")
    if not counts.source.isin(["SP", "NRT"]).all():
        raise ValueError("Unrecognized SP/NRT source")
    if not counts.month.between(1, 12).all():
        raise ValueError("Invalid calendar month")
    if coefficients.cell_id.duplicated().any():
        raise ValueError("Duplicate coefficients")
    k = coefficients.k.to_numpy(float)
    if not np.isfinite(k).all() or (k < 0).any():
        raise ValueError("Coefficients must be finite and nonnegative")
    if not counts.cell_id.isin(coefficients.cell_id).all():
        raise ValueError("Missing fixed coefficient for a detection cell")


def reconcile_grid(counts: pd.DataFrame, grid: pd.DataFrame) -> dict:
    """Check cell counts and global-month satellite divisors before diagnostics."""
    keys = ["cell_id", "year", "month"]
    if grid.duplicated(keys).any():
        raise ValueError("Duplicate monthly grid rows")
    p = counts.pivot_table(index=keys, columns="sensor", values="n", aggfunc="sum", fill_value=0)
    p = p.reindex(columns=["MODIS", "VIIRS"], fill_value=0).rename(
        columns={"MODIS": "point_modis", "VIIRS": "point_viirs"}
    )
    joined = grid.merge(p.reset_index(), on=keys, how="outer").fillna(0)
    mismatch = (~np.isclose(joined.n_modis, joined.point_modis, rtol=0, atol=0)) | (
        ~np.isclose(joined.n_viirs, joined.point_viirs, rtol=0, atol=0)
    )
    sats = counts[counts.sensor == "VIIRS"].groupby(["year", "month"]).satellite.nunique()
    divisor = grid.groupby(["year", "month"]).n_viirs_sats.agg(["min", "max"])
    divisor["actual"] = sats.reindex(divisor.index, fill_value=0)
    bad_divisor = (divisor["min"] != divisor["max"]) | (divisor["max"] != divisor.actual)
    if mismatch.any() or bad_divisor.any():
        raise ValueError("Published points do not reconcile with grid counts/satellite divisors")
    return {"cell_months_checked": len(joined), "months_checked": len(divisor), "mismatches": 0}


def scenarios() -> dict[str, tuple[str, ...]]:
    return {
        "baseline": VIIRS,
        **{f"without_{sat}": tuple(s for s in VIIRS if s != sat) for sat in VIIRS},
        **{f"only_{sat}": (sat,) for sat in VIIRS},
    }


def diagnose(
    counts: pd.DataFrame,
    coefficients: pd.DataFrame,
    weights: pd.DataFrame,
    months: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return zero-filled AOI/month scenarios and baseline accounting contributions.

    ``weights`` is a long table of cell_id/area/w, including national weight 1.
    Every scenario recalculates its divisor globally from its own satellite subset,
    before applying AOI weights. A globally absent subset has unknown prediction,
    whereas a zero-detection province with a global divisor retains a true zero.
    """
    check_counts(counts, coefficients)
    if weights.duplicated(["cell_id", "area"]).any() or weights.empty:
        raise ValueError("AOI weights must be nonempty and unique")
    if not np.isfinite(weights.w).all() or not weights.w.between(0, 1).all():
        raise ValueError("AOI weights must be finite fractions")
    if weights.area.isna().any() or not weights.cell_id.isin(coefficients.cell_id).all():
        raise ValueError("Invalid area or unknown weight cell")
    if months.duplicated(["year", "month"]).any() or months.empty:
        raise ValueError("Month index must be nonempty and unique")
    if (
        not counts.merge(months, on=["year", "month"], how="left", indicator=True)["_merge"]
        .eq("both")
        .all()
    ):
        raise ValueError("Detection month absent from index")

    base = weights[["area"]].drop_duplicates().merge(months, how="cross")
    base = base.sort_values(["area", "year", "month"]).reset_index(drop=True)
    marked = counts.merge(coefficients[["cell_id", "k"]], on="cell_id", validate="many_to_one")
    tables, contributions = [], []
    for name, subset in scenarios().items():
        viirs = marked.sensor.eq("VIIRS") & marked.satellite.isin(subset)
        keep = marked.sensor.eq("MODIS") | viirs
        selected = marked[keep].copy()
        sats = marked[viirs].groupby(["year", "month"]).satellite.nunique().rename("denominator")
        selected = selected.merge(sats, on=["year", "month"], how="left")
        selected["observed_contribution"] = np.where(selected.sensor.eq("MODIS"), selected.n, 0)
        selected["predicted_contribution"] = np.where(
            selected.sensor.eq("VIIRS"), selected.n * selected.k / selected.denominator, 0
        )
        spatial = selected.merge(weights, on="cell_id", validate="many_to_many")
        for column in ("n", "observed_contribution", "predicted_contribution"):
            spatial[column] = spatial[column] * spatial.w
        keys = ["area", "year", "month"]
        totals = spatial.groupby(keys)[["observed_contribution", "predicted_contribution"]].sum()
        table = base.merge(totals, on=keys, how="left").fillna(
            {"observed_contribution": 0, "predicted_contribution": 0}
        )
        table = table.merge(sats, on=["year", "month"], how="left")
        table["denominator"] = table.denominator.fillna(0).astype(int)
        table["prediction_available"] = table.denominator > 0
        table.loc[~table.prediction_available, "predicted_contribution"] = np.nan
        table = table.rename(
            columns={"observed_contribution": "observed", "predicted_contribution": "predicted"}
        )
        platform = (
            spatial.pivot_table(
                index=keys, columns="satellite", values="n", aggfunc="sum", fill_value=0
            )
            .reindex(columns=list(PLATFORMS), fill_value=0)
            .rename(columns=COUNT_COLUMNS)
        )
        table = table.merge(platform, on=keys, how="left").fillna(
            dict.fromkeys(COUNT_COLUMNS.values(), 0)
        )
        table["n_viirs"] = table[[COUNT_COLUMNS[s] for s in VIIRS]].sum(axis=1)
        table["residual"] = table.predicted - table.observed
        table["scenario"] = name
        tables.append(table)
        if name == "baseline":
            detail = (
                spatial.groupby(keys + ["satellite", "sensor", "source", "version"])[
                    ["n", "observed_contribution", "predicted_contribution"]
                ]
                .sum()
                .reset_index()
            )
            detail["residual_contribution"] = (
                detail.predicted_contribution - detail.observed_contribution
            )
            contributions.append(detail.merge(sats, on=["year", "month"]))
    monthly = pd.concat(tables, ignore_index=True)
    baseline = monthly[monthly.scenario == "baseline"][
        ["area", "year", "month", "predicted", "denominator"]
    ].rename(columns={"predicted": "baseline_predicted", "denominator": "baseline_denominator"})
    monthly = monthly.merge(baseline, on=["area", "year", "month"], validate="many_to_one")
    monthly["delta_predicted"] = monthly.predicted - monthly.baseline_predicted
    return monthly, pd.concat(contributions, ignore_index=True)


def summarize(monthly: pd.DataFrame, eligible: dict[str, bool]) -> pd.DataFrame:
    """Known-period diagnostics; single-platform references are not calibrated targets."""
    rows = []
    for (scenario, area), group in monthly.groupby(["scenario", "area"]):
        series = group.set_index(["year", "month"])
        for period, pairs in PERIODS.items():
            part = series.reindex(pd.MultiIndex.from_tuples(pairs, names=["year", "month"]))
            for reference, column in (
                ("Terra+Aqua", "observed"),
                ("Terra", "n_terra"),
                ("Aqua", "n_aqua"),
            ):
                result = metrics(part[column].to_numpy(float), part.predicted.to_numpy(float))
                assessable = (
                    reference == "Terra+Aqua"
                    and result["r"] is not None
                    and result["bias"] is not None
                    and result["months_unavailable"] == 0
                    and period != "2026_Nov_partial"
                )
                rows.append(
                    {
                        "scenario": scenario,
                        "area": area,
                        "period": period,
                        "reference": reference,
                        "eligible": eligible[area],
                        **result,
                        "target_assessable": assessable,
                        "meets_target": bool(result["r"] >= 0.9 and abs(result["bias"]) <= 0.1)
                        if assessable
                        else None,
                    }
                )
    result = pd.DataFrame(rows)
    keys = ["area", "period", "reference"]
    baseline = result[result.scenario == "baseline"][keys + ["bias", "mae"]].rename(
        columns={"bias": "baseline_bias", "mae": "baseline_mae"}
    )
    result = result.merge(baseline, on=keys, validate="many_to_one")
    result["delta_bias_percentage_points"] = (result.bias - result.baseline_bias) * 100
    result["delta_mae"] = result.mae - result.baseline_mae
    return result


def compare_reference(summary: pd.DataFrame, reference: pd.DataFrame) -> dict:
    """Reproduce every saved province/national result, including ineligible regions."""
    baseline = summary[(summary.scenario == "baseline") & (summary.reference == "Terra+Aqua")]
    keys = ["period", "area"]
    if reference.empty or reference.duplicated(keys).any():
        raise ValueError("Saved baseline regression must be nonempty and unique")
    compared = reference.merge(
        baseline,
        on=keys,
        suffixes=("_saved", "_audit"),
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    if not compared._merge.eq("both").all():
        raise ValueError("Saved regression contains unsupported area/period")
    for field in ("r", "bias", "mae", "months"):
        audit_values = compared[f"{field}_audit"].astype(float).copy()
        if field == "mae":
            # The previous verifier suppresses absolute error for zero MODIS totals.
            audit_values.loc[compared.observed.eq(0)] = np.nan
        if not np.allclose(
            compared[f"{field}_saved"].astype(float),
            audit_values,
            rtol=1e-8,
            atol=1e-8,
            equal_nan=True,
        ):
            raise ValueError(f"Fixed-model baseline does not reproduce saved {field}")
    if not compared.eligible_saved.eq(compared.eligible_audit).all():
        raise ValueError("Training eligibility differs from the saved baseline")
    if (
        "meets_target_saved" in compared
        and not compared.meets_target_saved.eq(compared.meets_target_audit.fillna(False)).all()
    ):
        raise ValueError("Target status differs from the saved baseline")
    return {"rows_compared": len(compared), "matches": True, "rtol": 1e-8, "atol": 1e-8}
