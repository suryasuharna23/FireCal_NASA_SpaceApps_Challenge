"""Verify real processed data, three provincial hold-outs, and actual API responses."""

import io
import time

import duckdb
import pandas as pd
import shapely
from fastapi.testclient import TestClient

from app.aoi import Grid
from app.main import create_app
from firecal.config import get_settings
from firecal.io import read_json, write_json
from firecal.validate import _metrics

PROVINCES = ["Riau", "Sumatera Selatan", "Kalimantan Tengah"]


def main() -> None:
    """Check provincial accuracy without fitting or choosing new parameters."""
    settings = get_settings()
    paths = settings.paths
    meta = read_json(paths.meta)
    assert meta["coverage"]["country"] == "Indonesia"
    regions = pd.read_parquet(paths.regions)
    tests = ",".join(map(str, settings.harmonize_config.test_years))
    with duckdb.connect() as con:
        grid = con.execute(
            f"SELECT g.*, c.k FROM read_parquet('{paths.grid_monthly.as_posix()}') g "
            f"JOIN read_parquet('{paths.coefficients.as_posix()}') c USING(cell_id) "
            f"WHERE g.year IN ({tests}) AND g.n_viirs_sats > 0"
        ).df()
        balance_error = con.execute(
            f"""WITH p AS (
                SELECT cell_id, year, month, sum(weight) AS weighted
                FROM read_parquet('{paths.points.as_posix()}/**/*.parquet')
                WHERE in_series GROUP BY ALL
            ) SELECT max(abs(coalesce(weighted, 0) - coalesce(n_harmonized, 0)))
            FROM p FULL JOIN read_parquet('{paths.harmonized.as_posix()}') h
            USING(cell_id, year, month)"""
        ).fetchone()[0]
    assert balance_error < 1e-8, balance_error

    results = []
    with TestClient(create_app()) as client:
        assert client.get("/meta").json()["end_month"] == meta["end_month"]
        globe = client.get("/globe", params={"year": 2023, "month": 9})
        assert globe.status_code == 200 and globe.json()["count"] > 0
        for name in PROVINCES:
            row = regions[regions.name == name].iloc[0]
            geom = shapely.from_wkb(row.geometry)
            weights = Grid(settings.grid_res_deg).cell_weights(geom)
            subset = grid.merge(weights, on="cell_id")
            subset["observed"] = subset.n_modis * subset.w
            subset["raw"] = subset.n_viirs / subset.n_viirs_sats * subset.w
            subset["predicted"] = subset.raw * subset.k
            monthly = subset.groupby(["year", "month"])[["observed", "raw", "predicted"]].sum()
            assert len(monthly) == 12 * len(settings.harmonize_config.test_years)
            after = _metrics(monthly.observed.to_numpy(), monthly.predicted.to_numpy())
            before = _metrics(monthly.observed.to_numpy(), monthly.raw.to_numpy())
            body = {"aoi": shapely.geometry.mapping(geom), "start": "2001-01", "end": "2025-12"}
            start = time.perf_counter()
            calendar = client.post("/calendar", json=body)
            elapsed = time.perf_counter() - start
            assert calendar.status_code == 200, calendar.text
            assert len(calendar.json()["months"]) == 300
            stats = client.post("/stats", json=body)
            assert stats.status_code == 200, stats.text
            exported = client.post("/export", json={**body, "kind": "monthly"})
            assert exported.status_code == 200
            csv = pd.read_csv(io.StringIO(exported.text), comment="#")
            assert csv.n_harmonized.round(2).tolist() == [
                month["value"] for month in calendar.json()["months"]
            ]
            points = client.post("/points", json={"aoi": body["aoi"], "year": 2019, "month": 9})
            assert points.status_code == 200 and points.json()["count"] > 0
            results.append(
                {
                    "province": name,
                    "before": before,
                    "after": after,
                    "meets_target": after["r"] >= 0.9 and abs(after["bias"]) <= 0.1,
                    "calendar_seconds": elapsed,
                    "points_2019_09": points.json()["count"],
                    "api_checks": "calendar, stats, points, monthly CSV agreement passed",
                }
            )
    report = {
        "data_version": meta["data_version"],
        "test_years": settings.test_years,
        "max_weight_balance_error": balance_error,
        "provinces": results,
        "spatial_method": "0.25 degree grid weighted by province/cell intersection area",
        "timing_note": "Single local requests; these timings are not a production p95 benchmark.",
    }
    write_json(paths.reports / "indonesia_verification.json", report)
    validation = read_json(paths.reports / "validation.json")
    validation.setdefault("administrative_regions", {}).update(
        {r["province"]: {k: r[k] for k in ("before", "after", "meets_target")} for r in results}
    )
    validation["limitations"] = [
        text
        for text in validation.get("limitations", [])
        if not any(text.startswith(f"Province {name}:") for name in PROVINCES)
    ] + [
        f"Province {r['province']}: hold-out r={r['after']['r']:.4f}, "
        f"bias={r['after']['bias']:+.2%} misses the regional target (|bias| <= 10%)."
        for r in results
        if not r["meets_target"]
    ]
    write_json(paths.reports / "validation.json", validation)
    pilot = read_json(paths.reports / "indonesia_pilot.json")
    pilot["validation"] = validation
    write_json(paths.reports / "indonesia_pilot.json", pilot)
    for result in results:
        print(result)


if __name__ == "__main__":
    main()
