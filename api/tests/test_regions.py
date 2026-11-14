import json

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
    assert country[0]["too_large"] is True  # 1.9M km² > MAX_AOI_KM2


def test_region_geometry_can_be_used_as_aoi(client, regions_built) -> None:
    feature = client.get("/regions/NE1-IDN-1").json()
    assert feature["properties"]["name"] == "Riau"
    assert feature["geometry"]["type"] == "Polygon"
    res = client.post("/calendar", json={"aoi": feature})
    assert res.status_code == 200
    assert res.json()["aoi"]["cells"] == 16 * 12


def test_unknown_region_is_404(client, regions_built) -> None:
    assert client.get("/regions/nope").status_code == 404
