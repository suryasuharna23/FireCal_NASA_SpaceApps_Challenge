import time

import duckdb
import pytest
import shapely

from app.aoi import Aoi, AoiError, Grid, parse_geometry


def _box(west, south, east, north) -> dict:
    ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
    return {"type": "Polygon", "coordinates": [ring]}


def test_calendar_returns_full_year_month_matrix(client, box) -> None:
    res = client.post("/calendar", json={"aoi": box(104, -2, 108, 2)})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["start"] == "2011-01" and body["end"] == "2020-12"  # default: data range
    assert len(body["months"]) == 120  # zero-filled, no gaps
    assert body["aoi"]["cells"] == 16 * 16
    assert body["aoi"]["area_km2"] == pytest.approx(197_000, rel=0.02)
    first = body["months"][0]
    assert {"value", "n_modis", "n_viirs", "ci_low", "ci_high", "source", "anomaly_pct"} <= set(
        first
    )
    assert {m["source"] for m in body["months"]} == {"MODIS", "VIIRS"}
    assert body["max_value"] == max(m["value"] for m in body["months"])


def test_calendar_matches_cube_for_aligned_aoi(client, data_dir, box) -> None:
    res = client.post(
        "/calendar", json={"aoi": box(104, -2, 108, 2), "start": "2019-01", "end": "2019-12"}
    )
    months = res.json()["months"]
    expected = dict(
        duckdb.sql(
            f"""SELECT month, sum(n_harmonized)
                FROM read_parquet('{(data_dir / "harmonized.parquet").as_posix()}')
                WHERE year = 2019 AND cell_id IN (
                    SELECT r * 1440 + c FROM range(352, 360) t(r), range(1136, 1152) u(c)
                ) GROUP BY month"""
        ).fetchall()
    )
    # rows 352..359 = lat 2..0, i.e. the northern half of the AOI
    north = client.post(
        "/calendar", json={"aoi": box(104, 0, 108, 2), "start": "2019-01", "end": "2019-12"}
    ).json()["months"]
    for m in north:
        assert m["value"] == pytest.approx(expected.get(m["month"], 0), abs=0.02)
    assert sum(m["value"] for m in months) >= sum(m["value"] for m in north)


def test_partial_cells_are_weighted_by_area() -> None:
    weights = Grid(0.25).cell_weights(shapely.box(100.0, 0.0, 100.125, 0.25))
    assert len(weights) == 1
    assert weights.w.iloc[0] == pytest.approx(0.5)


def test_reference_years_drive_anomaly(client, box) -> None:
    res = client.post(
        "/calendar",
        json={"aoi": box(104, -2, 108, 2), "reference_years": [2012, 2014]},
    ).json()
    assert res["reference_years"] == [2012, 2014]
    m = next(m for m in res["months"] if m["median"])
    assert m["anomaly_pct"] == pytest.approx(
        (m["value"] - m["median"]) / m["median"] * 100, abs=0.1
    )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"start": "1999-01"}, "outside the available data"),
        ({"start": "2020-05", "end": "2019-01"}, "must not be after"),
        ({"aoi": _box(60, -40, 150, 40)}, "maximum"),
        ({"aoi": {"type": "Point", "coordinates": [1, 2]}}, "Polygon"),
        ({"aoi": _box(170, 0, 190, 5)}, "Coordinates"),
    ],
)
def test_invalid_requests_are_rejected_with_clear_message(client, box, payload, message) -> None:
    res = client.post("/calendar", json={"aoi": box(104, -2, 108, 2), **payload})
    assert res.status_code == 422
    assert message in res.json()["detail"]


def test_bad_month_format_is_rejected(client, box) -> None:
    res = client.post("/calendar", json={"aoi": box(104, -2, 108, 2), "start": "2019-13"})
    assert res.status_code == 422


def test_feature_input_and_self_intersection_are_accepted() -> None:
    bowtie = {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]}
    geom = parse_geometry({"type": "Feature", "properties": {}, "geometry": bowtie})
    assert geom.is_valid and geom.area > 0
    with pytest.raises(AoiError):
        Aoi.from_geojson({"type": "FeatureCollection", "features": []}, 1e6)


def test_calendar_is_fast(client, box) -> None:
    aoi = {"aoi": box(101, -3, 110.5, 3.5)}  # ~ 760,000 km²
    started = time.perf_counter()
    assert client.post("/calendar", json=aoi).status_code == 200
    assert time.perf_counter() - started < 3.0
