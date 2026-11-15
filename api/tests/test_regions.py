import json
from pathlib import Path

import pytest
import shapely


@pytest.fixture(scope="session")
def regions_built(data_dir):
    from firecal.regions import build_regions

    def fc(items):
        return json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": p, "geometry": shapely.geometry.mapping(g)}
                    for p, g in items
                ],
            }
        )

    src = data_dir.parent / "boundaries"
    src.mkdir(exist_ok=True)
    (src / "a0.geojson").write_text(
        fc([({"ADM0_A3": "IDN", "NAME": "Indonesia"}, shapely.box(95, -11, 141, 6))])
    )
    (src / "a1.geojson").write_text(
        fc(
            [
                (
                    {"adm1_code": "IDN-1", "name": "Riau", "admin": "Indonesia"},
                    shapely.box(100, -1, 104, 2),
                ),
                (
                    {"adm1_code": "IDN-2", "name": "Kalimantan Tengah", "admin": "Indonesia"},
                    shapely.box(110, -4, 116, 1),
                ),
                (
                    {"adm1_code": "IDN-3", "name": "Kalimantan Barat", "admin": "Indonesia"},
                    shapely.box(108, -3, 114, 2),
                ),
            ]  # fmt: skip
        )
    )
    build_regions([src / "a0.geojson", src / "a1.geojson"], data_dir / "regions.parquet")
    return data_dir


def test_search_ranks_name_matches_and_flags_large_regions(client, regions_built) -> None:
    body = client.get("/regions", params={"q": "kalimantan"}).json()
    names = [r["name"] for r in body["results"]]
    assert names == ["Kalimantan Barat", "Kalimantan Tengah"]
    assert body["results"][0]["too_large"] is False

    country = client.get("/regions", params={"q": "indonesia", "level": 0}).json()["results"]
    assert [r["id"] for r in country] == ["NE0-IDN"]
    assert country[0]["too_large"] is True  # fixture is a 46° × 17° box


def test_region_geometry_can_be_used_as_aoi(client, regions_built) -> None:
    feature = client.get("/regions/NE1-IDN-1").json()
    assert feature["properties"]["name"] == "Riau"
    assert feature["geometry"]["type"] == "Polygon"
    res = client.post("/calendar", json={"aoi": feature})
    assert res.status_code == 200
    assert res.json()["aoi"]["cells"] == 16 * 12


def test_all_indonesia_boundaries(client, regions_built) -> None:
    response = client.get("/regions/boundaries")
    assert response.status_code == 200
    features = response.json()["features"]
    assert [feature["properties"]["name"] for feature in features] == [
        "Indonesia",
        "Kalimantan Barat",
        "Kalimantan Tengah",
        "Riau",
    ]
    assert all(feature["geometry"]["type"] == "Polygon" for feature in features)


def test_unknown_region_is_404(client, regions_built) -> None:
    assert client.get("/regions/nope").status_code == 404


@pytest.fixture
def global_regions_data(tmp_path, monkeypatch, client):
    import duckdb

    from app.settings import get_settings
    from firecal.regions import build_regions

    root = tmp_path / "world"
    root.mkdir()
    (root / "meta.json").write_text(
        json.dumps(
            {
                "format": "firecal-global-v1",
                "data_version": "global-fixture",
                "start_month": "2026-08",
                "end_month": "2026-11",
            }
        )
    )
    with duckdb.connect() as con:
        folder = root / "points/year=2026"
        folder.mkdir(parents=True)
        con.execute(
            f"COPY (SELECT -8::DOUBLE AS longitude,40::DOUBLE AS latitude,"
            f"TIMESTAMP '2026-11-15 12:00:00' AS acq_datetime,11 AS month,"
            f"'D' AS daynight,'nominal' AS confidence,5.0 AS frp,'VIIRS' AS sensor,"
            f"'NOAA-20' AS satellite,'NRT' AS source,NULL::DOUBLE AS weight,"
            f"72704 AS cell_id) TO '{(folder / 'test.parquet').as_posix()}' (FORMAT parquet)"
        )
        con.execute(
            f"COPY (SELECT 2026 AS year,11 AS month,DATE '2026-11-15' AS acq_date,"
            f"12 AS hour,-7.75 AS lon,39.75 AS lat,1 AS raw) "
            f"TO '{(root / 'globe.parquet').as_posix()}' (FORMAT parquet)"
        )

    def boundary_file(path: Path, items: list[tuple[dict, object]]) -> Path:
        payload = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": p, "geometry": shapely.geometry.mapping(g)}
                for p, g in items
            ],
        }
        path.write_text(json.dumps(payload))
        return path

    src = tmp_path / "world-boundaries"
    src.mkdir()
    build_regions(
        [
            boundary_file(
                src / "a0.geojson",
                [
                    ({"ADM0_A3": "BRA", "NAME": "Brazil"}, shapely.box(-74, -34, -35, 6)),
                    ({"ADM0_A3": "PRT", "NAME": "Portugal"}, shapely.box(-10, 36, -6, 43)),
                ],
            ),
            boundary_file(
                src / "a1.geojson",
                [
                    (
                        {"adm1_code": "BRA-1", "name": "Amazonas", "admin": "Brazil"},
                        shapely.box(-71, -10, -60, 2),
                    ),
                    (
                        {"adm1_code": "PRT-1", "name": "Algarve", "admin": "Portugal"},
                        shapely.box(-9, 37, -7, 38),
                    ),
                ],
            ),
        ],
        root / "regions.parquet",
    )
    monkeypatch.setenv("GLOBAL_DATA_URI", str(root))
    get_settings.cache_clear()
    from app.db import _datasets

    _datasets.clear()
    yield root
    get_settings.cache_clear()
    _datasets.clear()


def test_global_scope_searches_all_countries(client, global_regions_data) -> None:
    body = client.get("/regions", params={"scope": "global", "q": "brazil"}).json()
    assert [r["id"] for r in body["results"]] == ["NE0-BRA", "NE1-BRA-1"]
    assert body["results"][0]["too_large"] is True

    provinces = client.get(
        "/regions", params={"scope": "global", "country": "Brazil", "level": 1}
    ).json()
    assert [r["name"] for r in provinces["results"]] == ["Amazonas"]

    # The Indonesia scope keeps its own snapshot and never sees the world table.
    assert client.get("/regions", params={"q": "brazil"}).json()["results"] == []


def test_global_boundaries_default_to_countries(client, global_regions_data) -> None:
    features = client.get("/regions/boundaries", params={"scope": "global"}).json()["features"]
    assert [f["properties"]["name"] for f in features] == ["Brazil", "Portugal"]

    one = client.get(
        "/regions/boundaries", params={"scope": "global", "country": "Portugal"}
    ).json()["features"]
    assert [f["properties"]["name"] for f in one] == ["Portugal", "Algarve"]


def test_global_region_aoi_and_missing_data(
    client, global_regions_data, tmp_path, monkeypatch
) -> None:
    feature = client.get("/regions/NE1-PRT-1", params={"scope": "global"}).json()
    assert feature["properties"]["name"] == "Algarve"

    from app.settings import get_settings

    monkeypatch.setenv("GLOBAL_DATA_URI", str(tmp_path / "missing.json"))
    get_settings.cache_clear()
    assert client.get("/regions", params={"scope": "global", "q": "brazil"}).status_code == 503
    get_settings.cache_clear()
