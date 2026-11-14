"""Small hand-calculated cases; these are not results for the Indonesia snapshot."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from firecal.bias_audit import compare_reference, diagnose, metrics, reconcile_grid, summarize


@pytest.fixture
def inputs():
    rows = [
        (1, 1, "Terra", 10),
        (2, 1, "Aqua", 2),
        (1, 1, "S-NPP", 8),
        (2, 1, "NOAA-20", 12),
        (1, 1, "NOAA-21", 6),
        (2, 2, "Aqua", 3),
        (2, 2, "NOAA-20", 9),
        (1, 3, "Terra", 4),
    ]
    counts = pd.DataFrame(rows, columns=["cell_id", "month", "satellite", "n"])
    counts["year"] = 2026
    counts["sensor"] = np.where(counts.satellite.isin(["Terra", "Aqua"]), "MODIS", "VIIRS")
    counts["source"] = "SP"
    counts["version"] = "test"
    coefficients = pd.DataFrame({"cell_id": [1, 2], "k": [0.5, 1.0]})
    weights = pd.DataFrame(
        {
            "cell_id": [1, 2, 1, 2],
            "area": ["Indonesia", "Indonesia", "Province", "Empty"],
            "w": [1, 1, 0.5, 0],
        }
    )
    months = pd.DataFrame({"year": [2026] * 3, "month": [1, 2, 3]})
    return counts, coefficients, weights, months


def test_single_month_metrics_keep_bias_and_mae_without_correlation():
    result = metrics(np.array([10]), np.array([8]))
    assert result["bias"] == pytest.approx(-0.2)
    assert result["mae"] == 2
    assert result["r"] is None and result["months"] == 1


def test_missing_predictions_and_zero_reference_are_explicit():
    result = metrics(np.array([0, 0, 2]), np.array([1, 0, np.nan]))
    assert result["months_requested"] == 3 and result["months_unavailable"] == 1
    assert result["bias"] is None and result["mae"] == 0.5
    assert metrics(np.array([0]), np.array([np.nan]))["mae"] is None


def test_subset_divisors_are_global_and_recomputed_before_aoi_weights(inputs):
    monthly, _ = diagnose(*inputs)
    table = monthly.set_index(["scenario", "area", "month"])
    baseline = table.loc[("baseline", "Indonesia", 1)]
    assert baseline.denominator == 3
    assert baseline.predicted == pytest.approx((8 * 0.5 + 12 + 6 * 0.5) / 3)
    omitted = table.loc[("without_NOAA-21", "Indonesia", 1)]
    assert omitted.denominator == 2 and omitted.predicted == 8
    assert omitted.delta_predicted == pytest.approx(8 - baseline.predicted)
    # NOAA-20 appears only outside this AOI; its global divisor remains one.
    local = table.loc[("only_NOAA-20", "Province", 1)]
    assert local.denominator == 1 and local.prediction_available and local.predicted == 0


def test_zero_local_months_are_preserved_but_absent_global_subset_is_unavailable(inputs):
    monthly, _ = diagnose(*inputs)
    table = monthly.set_index(["scenario", "area", "month"])
    zero = table.loc[("baseline", "Province", 2)]
    assert zero.observed == zero.predicted == 0 and zero.prediction_available
    missing = table.loc[("baseline", "Indonesia", 3)]
    assert missing.observed == 4 and np.isnan(missing.predicted) and missing.denominator == 0
    assert len(monthly) == 7 * 3 * 3


def test_source_contributions_sum_to_baseline_residual_and_preserve_versions(inputs):
    counts, coef, weights, months = inputs
    counts.loc[counts.satellite == "NOAA-21", ["source", "version"]] = ["NRT", "2.0NRT"]
    monthly, detail = diagnose(counts, coef, weights, months)
    baseline = monthly.query("scenario == 'baseline' and prediction_available")
    total = detail.groupby(["area", "year", "month"]).residual_contribution.sum()
    for row in baseline.itertuples():
        assert total.get((row.area, row.year, row.month), 0) == pytest.approx(row.residual)
    assert detail.query("satellite == 'NOAA-21'").version.eq("2.0NRT").all()


def test_grid_counts_and_divisors_must_reconcile(inputs):
    counts, *_ = inputs
    grid = pd.DataFrame(
        [
            (1, 2026, 1, 10, 14, 3),
            (2, 2026, 1, 2, 12, 3),
            (2, 2026, 2, 3, 9, 1),
            (1, 2026, 3, 4, 0, 0),
        ],
        columns=["cell_id", "year", "month", "n_modis", "n_viirs", "n_viirs_sats"],
    )
    assert reconcile_grid(counts, grid)["mismatches"] == 0
    grid.loc[0, "n_viirs_sats"] = 2
    with pytest.raises(ValueError, match="reconcile"):
        reconcile_grid(counts, grid)


@pytest.mark.parametrize("problem", ["unknown_platform", "missing_coefficient", "negative_count"])
def test_invalid_inputs_cannot_silently_change_the_denominator(inputs, problem):
    counts, coef, weights, months = inputs
    if problem == "unknown_platform":
        counts.loc[0, "satellite"] = "unknown"
    elif problem == "missing_coefficient":
        coef = coef.iloc[:1]
    else:
        counts.loc[0, "n"] = -1
    with pytest.raises(ValueError):
        diagnose(counts, coef, weights, months)


def test_monthly_aoi_fraction_is_applied_after_fixed_cell_conversion(inputs):
    monthly, _ = diagnose(*inputs)
    selected = monthly.query("scenario == 'baseline' and area == 'Province' and month == 1").iloc[0]
    assert selected.observed == 5
    assert selected.predicted == pytest.approx((8 + 6) * 0.5 / 3 * 0.5)


def test_baseline_comparison_checks_values_and_training_eligibility(inputs):
    monthly, _ = diagnose(*inputs)
    summary = summarize(monthly, {"Indonesia": True, "Province": True, "Empty": False})
    row = summary.query(
        "scenario == 'baseline' and area == 'Indonesia' and reference == 'Terra+Aqua'"
    )
    reference = row[["period", "area", "eligible", "r", "bias", "mae", "months"]].copy()
    assert compare_reference(summary, reference)["matches"]
    reference.loc[reference.period == "2026_Jan_Jul", "bias"] += 0.1
    with pytest.raises(ValueError, match="saved bias"):
        compare_reference(summary, reference)


def runner():
    path = Path(__file__).resolve().parents[2] / "scripts/audit_indonesia_bias.py"
    spec = importlib.util.spec_from_file_location("audit_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_receipts(root):
    module = runner()
    available, plans = [], []
    for source in module.SOURCES:
        available.append({"data_id": source, "min_date": "2026-11-14", "max_date": "2026-11-14"})
        plans.append(
            {"source": source, "requested_start": "2026-11-14", "requested_end": "2026-11-14"}
        )
        folder = root / "responses" / source
        target = folder / source / f"{source}_2026-11-14_1d.csv"
        target.parent.mkdir(parents=True)
        target.write_text("latitude,longitude,acq_date\n", encoding="utf-8")
        request = {"source": source, "start": "2026-11-14", "days": 1}
        receipt = {
            "request": request,
            "sha256": module.sha(target),
            "bytes": target.stat().st_size,
            "path": "C:/old-machine/ignored-path.csv",
            "rows": 0,
        }
        module.write(target.with_suffix(".json"), receipt)
        module.write(
            folder / "manifest.json",
            {
                "complete": True,
                "bbox": [94, -12, 142, 7],
                "planned_windows": [request],
                "records": [receipt],
            },
        )
    module.write(root / "plan.json", {"sources": plans, "bbox": [94, -12, 142, 7]})
    module.write(root / "availability.json", {"sources": available})
    module.write(root / "progress.json", {"complete": True})
    return module


def test_receipts_relocate_without_old_paths_and_zero_requests_do_not_prove_exposure(tmp_path):
    module = make_receipts(tmp_path)
    paths, windows = module.receipt_inventory(tmp_path)
    assert len(paths) == 24 and len(windows) == 8
    assert all(w["observation_exposure"] == "unknown" for w in windows)
    assert all(w["request_status"] == "success_zero_detections" for w in windows)
    csv = next(tmp_path.rglob("*.csv"))
    csv.write_text("tampered")
    with pytest.raises(ValueError, match="checksum"):
        module.receipt_inventory(tmp_path)


def test_missing_data_preflight_does_not_create_outputs(tmp_path):
    module = runner()
    assert not module.inventory(
        tmp_path / "snapshot", tmp_path / "acquisition", tmp_path / "prior"
    )["ready"]
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="missing"):
        module.run(
            tmp_path / "snapshot", tmp_path / "acquisition", tmp_path / "prior", out, "fixture"
        )
    assert not out.exists()


def test_existing_output_and_overlapping_input_are_rejected_without_changes(tmp_path):
    module = runner()
    out = tmp_path / "out"
    out.mkdir()
    marker = out / "input_manifest.json"
    marker.write_text('{"locked": true}')
    with pytest.raises(ValueError, match="already exists"):
        module.run(
            tmp_path / "snapshot", tmp_path / "acquisition", tmp_path / "prior", out, "fixture"
        )
    assert json.loads(marker.read_text()) == {"locked": True}
    with pytest.raises(ValueError, match="separate"):
        module.run(tmp_path, tmp_path / "a", tmp_path / "p", tmp_path / "out2", "fixture")


def make_small_snapshot(root):
    """A fully specified, tiny numerical fixture, not the missing real snapshot."""
    from datetime import date

    import shapely

    from firecal.bias_audit import PERIODS
    from firecal.grid import GridSpec

    processed, acquisition, prior = root / "snapshot", root / "acquisition", root / "prior"
    (processed / "points").mkdir(parents=True)
    (processed / "reports").mkdir()
    prior.mkdir()
    module = make_receipts(acquisition)
    module.write(prior / "selection_lock.json", {"selected": "baseline", "fixture_only": True})
    cell = int(GridSpec().cell_ids(np.array([103.125]), np.array([-0.125]))[0])
    pairs = sorted(set(pair for pairs in PERIODS.values() for pair in pairs))
    point_rows, grid_rows, cube = [], [], []
    for year, month in pairs:
        m = 2 + month % 3
        platforms = ["S-NPP"] + (["NOAA-20"] if year >= 2018 else [])
        if year >= 2023:
            platforms.append("NOAA-21")
        for satellite in ["Terra", *platforms]:
            sensor = "MODIS" if satellite == "Terra" else "VIIRS"
            source = "NRT" if year == 2026 and month >= 9 else "SP"
            for _ in range(m if sensor == "MODIS" else 2 * m):
                point_rows.append(
                    {
                        "cell_id": cell,
                        "year": year,
                        "month": month,
                        "satellite": satellite,
                        "sensor": sensor,
                        "source": source,
                        "version": "fixture",
                        "acq_date": date(year, month, 1),
                        "weight": 1.0 if sensor == "MODIS" else 0.5 / len(platforms),
                        "in_series": sensor == ("MODIS" if year <= 2021 else "VIIRS"),
                    }
                )
        grid_rows.append(
            {
                "cell_id": cell,
                "year": year,
                "month": month,
                "n_modis": m,
                "n_viirs": 2 * m * len(platforms),
                "n_viirs_sats": len(platforms),
            }
        )
        cube.append({"cell_id": cell, "year": year, "month": month, "n_harmonized": float(m)})
    points = pd.DataFrame(point_rows)
    points.to_parquet(processed / "points/data.parquet", index=False)
    pd.DataFrame(grid_rows).to_parquet(processed / "grid_monthly.parquet", index=False)
    pd.DataFrame(cube).to_parquet(processed / "harmonized.parquet", index=False)
    pd.DataFrame(pairs, columns=["year", "month"]).to_parquet(processed / "months.parquet")
    pd.DataFrame({"cell_id": [cell], "k": [0.5], "n_cal_modis": [1001]}).to_parquet(
        processed / "coefficients.parquet"
    )
    pd.DataFrame(
        {
            "level": [1],
            "name": ["Riau"],
            "geometry": [shapely.to_wkb(shapely.box(103, -0.25, 103.25, 0))],
        }
    ).to_parquet(processed / "regions.parquet")
    meta = {
        "data_version": "fixture",
        "dataset_status": "experimental",
        "end_month": "2026-11",
        "grid_res_deg": 0.25,
        "calibration_period": "2013-01:2021-12",
        "test_years": [2016, 2019],
        "coverage": {"country": "Indonesia", "snapshot_end": "2026-11-14"},
    }
    module.write(processed / "meta.json", meta)
    counts = (
        points.groupby(["satellite", "source"])
        .agg(rows=("sensor", "size"), first_date=("acq_date", "min"), last_date=("acq_date", "max"))
        .reset_index()
    )
    counts.to_csv(processed / "reports/satellite_source_counts.csv", index=False)
    module.write(
        processed / "reports/extended_summary.json",
        {
            "clean_rows": points.groupby("sensor").size().to_dict(),
        },
    )
    for name in ("country_filter.json", "extended_verification.json"):
        module.write(processed / "reports" / name, {"fixture_only": True})
    reference = []
    for period in ("known_2016_2019", "known_2022_2025", "2026_Jan_Oct_provisional"):
        # Truth is defined independently: every platform sees 2x Terra and k=.5.
        for area in ("Indonesia", "Riau"):
            reference.append(
                {
                    "period": period,
                    "area": area,
                    "eligible": True,
                    "r": 1.0,
                    "bias": 0.0,
                    "mae": 0.0,
                    "months": len(PERIODS[period]),
                    "meets_target": True,
                }
            )
    pd.DataFrame(reference).to_csv(processed / "reports/regional_regression.csv", index=False)
    return module, processed, acquisition, prior


def test_full_runner_freezes_inputs_and_publishes_without_mutating_snapshot(tmp_path):
    module, processed, acquisition, prior = make_small_snapshot(tmp_path)
    before = {
        p: module.sha(p)
        for root in (processed, acquisition, prior)
        for p in root.rglob("*")
        if p.is_file()
    }
    out = tmp_path / "audit"
    report = module.run(processed, acquisition, prior, out, "fixture")
    assert report["baseline_reproduction"]["rows_compared"] == 6
    assert report["national_2026_jan_oct"]["bias"] == pytest.approx(0)
    assert report["max_point_weight_balance_error"] < 1e-8
    assert report["model_refitted"] is False and report["serving_changed"] is False
    assert all(module.sha(path) == digest for path, digest in before.items())
    manifest = json.loads((out / "input_manifest.json").read_text())
    assert manifest["data_version"] == "fixture"
    assert any(entry["group"] == "code" for entry in manifest["inputs"])
    monthly = pd.read_csv(out / "monthly_sensitivity.csv")
    assert len(monthly) == 83 * 2 * 7
    assert not monthly.query(
        "scenario == 'only_NOAA-21' and year == 2016"
    ).prediction_available.any()
    with pytest.raises(ValueError, match="already exists"):
        module.run(processed, acquisition, prior, out, "fixture")


def test_baseline_disagreement_prevents_audit_publication(tmp_path):
    module, processed, acquisition, prior = make_small_snapshot(tmp_path)
    reference_path = processed / "reports/regional_regression.csv"
    reference = pd.read_csv(reference_path)
    reference.loc[0, "bias"] = 0.123
    reference.to_csv(reference_path, index=False)
    out = tmp_path / "audit"
    with pytest.raises(ValueError, match="saved bias"):
        module.run(processed, acquisition, prior, out, "fixture")
    assert (out / "input_manifest.json").exists()
    assert not (out / "audit.json").exists()
