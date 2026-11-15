import json

import duckdb
import pytest

from app.db import Dataset
from app.global_view import global_globe


@pytest.fixture
def global_data(tmp_path, monkeypatch, client):
    from app.settings import get_settings

    root = tmp_path / "world"
    root.mkdir()
    meta = {
        "format": "firecal-global-v1",
        "data_version": "global-fixture",
        "start_date": "2026-08-15",
        "start_month": "2026-08",
        "end_month": "2026-11",
        "last_acq_date": "2026-11-15",
        "provisional": True,
        "grid_res_deg": 0.5,
        "lagging_sources": [{"source": "VIIRS_SNPP_NRT", "available_through": "2026-11-02"}],
    }
    (root / "meta.json").write_text(json.dumps(meta))
    folder = root / "points/year=2026"
    folder.mkdir(parents=True)
    with duckdb.connect() as con:
        con.execute(f"""COPY (SELECT -8::DOUBLE AS longitude,40::DOUBLE AS latitude,
            TIMESTAMP '2026-11-15 12:00:00' AS acq_datetime,11 AS month,
            'D' AS daynight,'nominal' AS confidence,5.0 AS frp,'VIIRS' AS sensor,
            'NOAA-20' AS satellite,'NRT' AS source,NULL::DOUBLE AS weight,72704 AS cell_id)
            TO '{(folder / "test.parquet").as_posix()}' (FORMAT parquet)""")
        con.execute(f"""COPY (SELECT 2026 AS year,11 AS month,DATE '2026-11-15' AS acq_date,
            12 AS hour,-7.75 AS lon,39.75 AS lat,1 AS raw)
            TO '{(root / "globe.parquet").as_posix()}' (FORMAT parquet)""")
    monkeypatch.setenv("GLOBAL_DATA_URI", str(root))
    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


def test_global_globe_and_foreign_area_points_use_actual_world_dataset(client, global_data, box):
    params = {
        "scope": "global",
        "mode": "raw",
        "year": 2026,
        "month": 11,
        "period": "hour",
        "day": 15,
        "hour": 12,
    }
    globe = client.get("/globe", params=params)
    assert globe.status_code == 200
    assert globe.json()["total"] == 1
    assert globe.json()["data_version"] == "global-fixture"
    body = {**params, "aoi": box(-9, 39, -7, 41)}
    points = client.post("/points", json=body)
    assert points.status_code == 200
    assert points.json()["count"] == 1
    assert points.json()["features"][0]["properties"]["satellite"] == "NOAA-20"
    params["hour"] = 11
    assert client.get("/globe", params=params).json()["total"] == 0


@pytest.mark.parametrize(
    "extra",
    [
        {"mode": "harmonized"},
        {"month": 7},
        {"month": 8, "period": "day", "day": 14},
        {"period": "day", "day": 16},
    ],
)
def test_global_unsupported_correction_and_unavailable_dates_fail(client, global_data, extra):
    params = {"scope": "global", "mode": "raw", "year": 2026, "month": 11, **extra}
    assert client.get("/globe", params=params).status_code == 422


def test_missing_global_data_fails_instead_of_showing_indonesia(client, tmp_path, monkeypatch):
    from app.settings import get_settings

    monkeypatch.setenv("GLOBAL_DATA_URI", str(tmp_path / "missing.json"))
    get_settings.cache_clear()
    assert (
        client.get(
            "/globe", params={"scope": "global", "mode": "raw", "year": 2026, "month": 11}
        ).status_code
        == 503
    )
    get_settings.cache_clear()


def test_adaptive_globe_keeps_all_regions_and_all_counts(global_data):
    with duckdb.connect() as con:
        p = global_data / "globe.parquet"
        con.execute(f"""COPY (SELECT 2026 AS year,11 AS month,DATE '2026-11-15' AS acq_date,
            12 AS hour,(x%720)*0.5-179.75 AS lon,floor(x/720)*0.5-89.75 AS lat,1 AS raw
            FROM range(10000) t(x)) TO '{p.as_posix()}' (FORMAT parquet)""")
        result = global_globe(con, Dataset(str(global_data)), 2026, 11, "month", None, None, "raw")
        assert result["res"] > 0.5
        assert len(result["cells"]) <= 5000
        assert sum(row[2] for row in result["cells"]) == result["total"] == 10000
        assert result["truncated"] is False
