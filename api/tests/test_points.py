import duckdb
import shapely


def _expected(data_dir, bounds, year, month) -> int:
    glob = (data_dir / "points" / f"year={year}" / "*.parquet").as_posix()
    df = duckdb.sql(
        f"SELECT longitude, latitude FROM read_parquet('{glob}') WHERE month = {month}"
    ).df()
    poly = shapely.box(*bounds)
    return int(shapely.contains_xy(poly, df.longitude, df.latitude).sum())


def test_points_returns_geojson_inside_aoi(client, box, data_dir) -> None:
    bounds = (100, -4, 108, 4)
    res = client.post("/points", json={"aoi": box(*bounds), "year": 2019, "month": 9})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["type"] == "FeatureCollection" and body["aggregated"] is False
    assert body["count"] == len(body["features"]) == _expected(data_dir, bounds, 2019, 9) > 0
    props = body["features"][0]["properties"]
    assert {"sensor", "satellite", "frp", "time", "confidence", "weight"} <= set(props)
    for f in body["features"]:
        x, y = f["geometry"]["coordinates"]
        assert 100 <= x <= 108 and -4 <= y <= 4


def test_points_switch_to_grid_above_limit(client, box) -> None:
    body = client.post(
        "/points", json={"aoi": box(100, -4, 108, 4), "year": 2019, "month": 9, "limit": 10}
    ).json()
    assert body["aggregated"] is True
    assert body["count"] > 10
    assert sum(f["properties"]["count"] for f in body["features"]) == body["count"]
    assert body["cell_size_deg"] == 0.25


def test_points_outside_range_rejected(client, box) -> None:
    res = client.post("/points", json={"aoi": box(104, -2, 108, 2), "year": 1999, "month": 1})
    assert res.status_code == 422
