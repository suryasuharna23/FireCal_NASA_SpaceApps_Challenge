"""Check the new 2026/NOAA-21 snapshot against its actual processed API outputs."""

import io
import os
from datetime import date, timedelta

import duckdb
import pandas as pd
from fastapi.testclient import TestClient

from firecal.config import get_settings
from firecal.io import read_json, write_json
from firecal.validate import _metrics


def regional_regression(processed, regions, resolution):
    """Describe fixed-model regional transfer; do not fit or select parameters."""
    import shapely

    from app.aoi import Grid

    coefficients = pd.read_parquet(processed / "coefficients.parquet").set_index("cell_id")
    with duckdb.connect() as con:
        monthly = con.execute(
            f"SELECT g.cell_id,g.year,g.month,g.n_modis, "
            f"g.n_viirs/g.n_viirs_sats::DOUBLE*c.k AS predicted "
            f"FROM read_parquet('{processed.as_posix()}/grid_monthly.parquet') g "
            f"JOIN read_parquet('{processed.as_posix()}/coefficients.parquet') c USING(cell_id) "
            "WHERE g.n_viirs_sats>0 AND (g.year IN (2016,2019) OR g.year>=2022)"
        ).df()
    areas = [("Indonesia", None)] + [
        (row["name"], shapely.from_wkb(row["geometry"]))
        for _, row in regions[regions.level == 1].iterrows()
    ]
    results = []
    for name, geometry in areas:
        if geometry is None:
            selected, eligible = monthly, True
        else:
            weights = Grid(resolution).cell_weights(geometry)
            training = weights.merge(coefficients[["n_cal_modis"]], on="cell_id")
            eligible = bool((training.n_cal_modis * training.w).sum() >= 1000)
            selected = monthly.merge(weights, on="cell_id")
            selected = selected.assign(
                n_modis=selected.n_modis * selected.w,
                predicted=selected.predicted * selected.w,
            )
        series = selected.groupby(["year", "month"])[["n_modis", "predicted"]].sum()
        periods = {
            "known_2016_2019": [(y, m) for y in [2016, 2019] for m in range(1, 13)],
            "known_2022_2025": [(y, m) for y in range(2022, 2026) for m in range(1, 13)],
            "2026_Jan_Oct_provisional": [(2026, m) for m in range(1, 11)],
        }
        for period, months in periods.items():
            # Complete source windows were verified before processing. Retain months
            # with zero detections in a province when computing correlation and MAE.
            index = pd.MultiIndex.from_tuples(months, names=["year", "month"])
            part = series.reindex(index, fill_value=0)
            metrics = _metrics(part.n_modis.to_numpy(float), part.predicted.to_numpy(float))
            passed = bool(
                metrics["r"] is not None and metrics["r"] >= 0.9 and abs(metrics["bias"]) <= 0.1
            )
            results.append(
                {
                    "period": period,
                    "area": name,
                    "eligible": eligible,
                    **metrics,
                    "meets_target": passed,
                }
            )
    pd.DataFrame(results).to_csv(processed / "reports" / "regional_regression.csv", index=False)
    report = {
        "results": results,
        "model_refit_for_this_check": False,
        "eligibility": "At least 1000 training MODIS detections, weighted by province overlap",
        "limitations": [
            "These are descriptive regression checks, not new independent hold-outs.",
            "2026 compares SP/NRT observations; MODIS is a reference, not independent fire truth.",
            "November 2026 is excluded because it is partial and S-NPP ends mid-window.",
        ],
    }
    write_json(processed / "reports" / "regional_regression.json", report)
    validation = read_json(processed / "reports" / "validation.json")
    validation["regional_regression"] = report
    warnings = [
        f"Extended regression {r['period']} {r['area']}: "
        f"r={r['r']:.4f}, bias={r['bias']:+.2%} misses the target."
        for r in results
        if r["eligible"] and not r["meets_target"] and r["r"] is not None
    ]
    validation["limitations"] = [
        text
        for text in validation.get("limitations", [])
        if not text.startswith("Extended regression ")
    ] + warnings
    write_json(processed / "reports" / "validation.json", validation)
    summary = read_json(processed / "reports" / "extended_summary.json")
    summary["validation"] = validation
    write_json(processed / "reports" / "extended_summary.json", summary)
    return report


def main() -> None:
    settings = get_settings()
    plan = read_json(settings.paths.interim / "api-acquisition" / "plan.json")
    snapshot = {p["requested_end"] for p in plan["sources"]}
    if len(snapshot) != 1:
        raise ValueError("Inconsistent acquisition snapshot dates")
    snapshot_end = snapshot.pop()
    root = settings.paths.interim / f"indonesia-extended-{snapshot_end.replace('-', '')}"
    processed = root / "processed"
    meta = read_json(processed / "meta.json")
    if meta.get("end_month") != snapshot_end[:7]:
        raise ValueError("Extended snapshot has not been processed through the requested month")
    assert meta["dataset_status"] == "experimental"
    assert "NOAA-21" in meta["coverage"]["satellites"]
    assert date.fromisoformat(meta["last_acq_date"]) >= date.fromisoformat(
        snapshot_end
    ) - timedelta(days=2)
    os.environ["DATA_URI"] = processed.as_posix()
    # Import only after selecting the isolated dataset for this process.
    import shapely

    from app.main import create_app

    points = f"{processed.as_posix()}/points/**/*.parquet"
    with duckdb.connect() as con:
        counts = con.execute(
            f"SELECT satellite, source, count(*) AS rows, min(acq_date) AS first_date, "
            f"max(acq_date) AS last_date FROM read_parquet('{points}') GROUP BY ALL ORDER BY ALL"
        ).df()
        error = con.execute(
            f"""WITH p AS (
                SELECT cell_id,year,month,sum(weight) AS weighted
                FROM read_parquet('{points}') WHERE in_series GROUP BY ALL
            ) SELECT max(abs(coalesce(weighted,0)-coalesce(n_harmonized,0)))
              FROM p FULL JOIN read_parquet('{processed.as_posix()}/harmonized.parquet')
              USING(cell_id,year,month)"""
        ).fetchone()[0]
    assert error < 1e-8
    snpp = counts[counts.satellite == "S-NPP"]
    assert pd.Timestamp(snpp.last_date.max()).date() <= date(2026, 11, 2)
    noaa21 = counts[counts.satellite == "NOAA-21"]
    assert not noaa21.empty and (noaa21["rows"] > 0).all()
    regions = pd.read_parquet(processed / "regions.parquet")
    checked = []
    with TestClient(create_app()) as client:
        api_meta = client.get("/meta").json()
        assert api_meta["data_version"] == meta["data_version"]
        assert api_meta["coverage"]["includes_nrt"]
        assert api_meta["nrt"]["provisional"]
        globe = client.get("/globe", params={"year": 2026, "month": 10})
        assert globe.status_code == 200 and globe.json()["count"] > 0
        for name in ["Riau", "Sumatera Selatan", "Kalimantan Tengah"]:
            row = regions[regions.name == name].iloc[0]
            geometry = shapely.geometry.mapping(shapely.from_wkb(row.geometry))
            body = {"aoi": geometry, "start": "2026-01", "end": meta["end_month"]}
            calendar = client.post("/calendar", json=body)
            assert calendar.status_code == 200, calendar.text
            assert len(calendar.json()["months"]) == int(meta["end_month"][-2:])
            assert sum(m["value"] for m in calendar.json()["months"]) > 0
            exported = client.post("/export", json={**body, "kind": "monthly"})
            assert exported.status_code == 200
            csv = pd.read_csv(io.StringIO(exported.text), comment="#")
            assert csv.n_harmonized.round(2).tolist() == [
                m["value"] for m in calendar.json()["months"]
            ]
            assert "experimental" in exported.text
            response = client.post("/points", json={"aoi": geometry, "year": 2026, "month": 10})
            assert response.status_code == 200 and response.json()["count"] > 0
            assert client.post("/stats", json=body).status_code == 200
            checked.append(
                {
                    "province": name,
                    "calendar_months": len(csv),
                    "points_october_2026": response.json()["count"],
                    "checks": "passed",
                }
            )
    counts.to_csv(processed / "reports" / "satellite_source_counts.csv", index=False)
    report = {
        "data_version": meta["data_version"],
        "snapshot_end": snapshot_end,
        "max_point_weight_balance_error": error,
        "api_checks": checked,
        "serving_configuration_changed": False,
    }
    write_json(processed / "reports" / "extended_verification.json", report)
    regional_regression(processed, regions, meta["grid_res_deg"])
    print(counts.to_string(index=False))
    print(report)


if __name__ == "__main__":
    main()
