import numpy as np
import pytest
import shapely

from firecal.grid import GridSpec, build_cells, latitude_zone


def test_default_grid_is_1440_by_720() -> None:
    spec = GridSpec(0.25)
    assert (spec.ncols, spec.nrows, spec.size) == (1440, 720, 1_036_800)


def test_cell_id_roundtrip_and_edges() -> None:
    spec = GridSpec(0.25)
    lon = np.array([-180.0, 179.999, 0.1, 110.3, 180.0])
    lat = np.array([90.0, -89.999, 0.1, -1.2, -90.0])
    ids = spec.cell_ids(lon, lat)
    assert ids[0] == 0
    assert ids[1] == spec.size - 1
    assert ids[4] == spec.size - 1  # clipped onto the last cell
    clon, clat = spec.centers(ids[2:4])
    assert np.allclose(clon, [0.125, 110.375])
    assert np.allclose(clat, [0.125, -1.125])


def test_cell_sql_matches_numpy() -> None:
    import duckdb

    spec = GridSpec(0.5)
    lon = np.array([-179.9, 12.3, 140.0])
    lat = np.array([-0.2, 45.6, 89.9])
    con = duckdb.connect()
    sql_ids = [
        con.execute(f"SELECT {spec.cell_sql(str(x), str(y))}").fetchone()[0]
        for x, y in zip(lon, lat, strict=True)
    ]
    assert sql_ids == spec.cell_ids(lon, lat).tolist()


def test_cell_area_sums_to_earth_surface() -> None:
    spec = GridSpec(1.0)
    total = spec.area_km2(np.arange(spec.size)).sum()
    assert total == pytest.approx(4 * np.pi * 6371.0088**2, rel=1e-9)


def test_invalid_resolution_rejected() -> None:
    with pytest.raises(ValueError):
        GridSpec(0.7)


def test_latitude_zone() -> None:
    assert latitude_zone(np.array([0, -30, 50, 60, 80])).tolist() == [
        "lat:tropical",
        "lat:subtropical",
        "lat:temperate",
        "lat:boreal",
        "lat:polar",
    ]


def test_build_cells_keeps_only_land_and_assigns_biome() -> None:
    import geopandas as gpd

    spec = GridSpec(1.0)
    land = [shapely.box(100, -2, 102, 0)]  # 2 x 2 degree island
    eco = gpd.GeoDataFrame(
        {"biome": ["Tropical Moist Forests"]}, geometry=[shapely.box(100, -2, 101, 0)]
    )
    cells = build_cells(spec, land, eco)
    assert len(cells) == 4  # edge-touching neighbours are excluded
    interior = cells
    assert set(cells.columns) >= {"cell_id", "west", "south", "east", "north", "biome"}
    assert set(interior[interior.lon < 101].biome) == {"Tropical Moist Forests"}
    assert set(interior[interior.lon > 101].biome) == {"lat:tropical"}


def test_cells_command_writes_parquet(tmp_path, monkeypatch) -> None:
    import json

    import pandas as pd
    from typer.testing import CliRunner

    from firecal.cli import app
    from firecal.config import get_settings

    land = tmp_path / "land.geojson"
    land.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": shapely.geometry.mapping(shapely.box(10, 10, 13, 12)),
                    }
                ],
            }
        )
    )
    monkeypatch.setenv("DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("GRID_RES_DEG", "1")
    get_settings.cache_clear()
    result = CliRunner().invoke(app, ["cells", "--land", str(land)])
    get_settings.cache_clear()
    assert result.exit_code == 0, result.output
    cells = pd.read_parquet(tmp_path / "data" / "processed" / "cells.parquet")
    assert len(cells) == 6
    assert cells.cell_id.is_unique
