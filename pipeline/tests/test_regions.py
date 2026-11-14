import json

import pandas as pd
import pytest
import shapely

from firecal.regions import build_regions


def _fc(features: list[tuple[dict, shapely.Geometry]]) -> str:
    return json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": p, "geometry": shapely.geometry.mapping(g)}
                for p, g in features
            ],
        }
    )


@pytest.fixture
def ne_files(tmp_path):
    admin0 = tmp_path / "ne_admin_0.geojson"
    admin0.write_text(
        _fc([({"ADM0_A3": "IDN", "NAME": "Indonesia"}, shapely.box(95, -11, 141, 6))])
    )
    admin1 = tmp_path / "ne_admin_1.geojson"
    admin1.write_text(
        _fc(
            [
                (
                    {"adm1_code": "IDN-1", "name": "Riau", "admin": "Indonesia"},
                    shapely.box(100, -1, 104, 2),
                ),
                (
                    {"adm1_code": "IDN-2", "name": "Kalimantan Tengah", "admin": "Indonesia"},
                    shapely.box(110, -4, 116, 1),
                ),
            ]  # fmt: skip
        )
    )
    return [admin0, admin1]


def test_build_regions_from_natural_earth(ne_files, tmp_path) -> None:
    out = tmp_path / "regions.parquet"
    df = build_regions(ne_files, out)
    assert set(df.id) == {"NE0-IDN", "NE1-IDN-1", "NE1-IDN-2"}
    riau = df.set_index("id").loc["NE1-IDN-1"]
    assert riau["name"] == "Riau" and riau.level == 1 and riau.country == "Indonesia"
    assert riau.area_km2 == pytest.approx(4 * 3 * 111.3**2, rel=0.02)
    assert (riau.west, riau.south, riau.east, riau.north) == (100, -1, 104, 2)
    saved = pd.read_parquet(out)
    geom = shapely.from_wkb(saved.geometry.iloc[0])
    assert geom.is_valid
    assert list(saved.level) == sorted(saved.level)
