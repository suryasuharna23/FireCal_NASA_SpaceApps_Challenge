import io
import time

import duckdb
import pandas as pd
import shapely


def test_export_preserves_experimental_scope_and_version_disclosure():
    from app.aoi import Aoi
    from app.routers.export import header

    aoi = Aoi.from_geojson(shapely.geometry.mapping(shapely.box(104, -2, 105, -1)), 1_000_000)
    text = header(
        "monthly",
        aoi,
        "2001-01",
        "2025-12",
        {
            "data_version": "pilot",
            "transition_month": "2021-12",
            "dataset_status": "experimental",
            "coverage": {"country": "Indonesia"},
            "source_versions": {"MODIS": ["6.03", "61.03"]},
        },
    )
    assert "coverage: Indonesia" in text and "experimental" in text
    assert "MODIS: 6.03, 61.03" in text
    assert "MODIS C6.1" not in text


def _csv(text: str) -> tuple[list[str], pd.DataFrame]:
    comments = [line for line in text.splitlines() if line.startswith("#")]
    return comments, pd.read_csv(io.StringIO(text), comment="#")


def test_monthly_export_has_attribution_and_all_columns(client, box) -> None:
    res = client.post(
        "/export",
        json={"kind": "monthly", "aoi": box(104, -2, 108, 2), "start": "2015-01", "end": "2016-12"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert 'filename="firecal_monthly_2015-01_2016-12.csv"' in res.headers["content-disposition"]
    comments, df = _csv(res.text)
    assert any("NASA FIRMS" in c for c in comments)
    assert len(df) == 24 == int(res.headers["x-row-count"])
    assert {"year", "month", "n_harmonized", "n_modis", "n_viirs", "ci_low", "ci_high",
            "anomaly_pct", "source"} <= set(df.columns)  # fmt: skip

    cal = client.post(
        "/calendar", json={"aoi": box(104, -2, 108, 2), "start": "2015-01", "end": "2016-12"}
    ).json()["months"]
    assert df.n_harmonized.round(2).tolist() == [m["value"] for m in cal]


def test_points_export_matches_raw_points(client, box, data_dir) -> None:
    bounds = (104, -2, 108, 2)
    res = client.post(
        "/export",
        json={"kind": "points", "aoi": box(*bounds), "start": "2019-03", "end": "2020-02"},
    )
    assert res.status_code == 200
    comments, df = _csv(res.text)
    assert any("NASA FIRMS" in c for c in comments)
    assert list(df.columns) == [
        "latitude", "longitude", "acq_datetime", "daynight", "confidence", "frp",
        "sensor", "satellite", "source", "weight",
    ]  # fmt: skip
    glob = (data_dir / "points" / "**" / "*.parquet").as_posix()
    raw = duckdb.sql(
        f"""SELECT longitude, latitude FROM read_parquet('{glob}', hive_partitioning = true)
            WHERE year * 100 + month BETWEEN 201903 AND 202002"""
    ).df()
    expected = int(shapely.contains_xy(shapely.box(*bounds), raw.longitude, raw.latitude).sum())
    assert len(df) == expected > 0
    assert df.weight.notna().all()


def test_points_export_streams_quickly(client, box) -> None:
    started = time.perf_counter()
    res = client.post(
        "/export", json={"kind": "points", "aoi": box(100, -4, 108, 4), "start": "2011-01"}
    )
    assert res.status_code == 200
    assert time.perf_counter() - started < 30
