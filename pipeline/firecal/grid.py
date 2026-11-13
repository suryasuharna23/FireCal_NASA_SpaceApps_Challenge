"""Global regular lat/lon grid (T-03) and monthly aggregation (T-09).

Cells are numbered row-major from the north-west corner::

    cell_id = row * ncols + col,  row = floor((90 - lat) / res),  col = floor((lon + 180) / res)

At the default 0.25° resolution the grid has 1440 x 720 = 1,036,800 cells.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import shapely
from shapely import STRtree

log = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0088

#: Latitude bands used as a biome fallback when no ecoregion map is supplied.
LATITUDE_ZONES: list[tuple[float, str]] = [
    (23.5, "lat:tropical"),
    (35.0, "lat:subtropical"),
    (55.0, "lat:temperate"),
    (66.5, "lat:boreal"),
    (90.1, "lat:polar"),
]


@dataclass(frozen=True)
class GridSpec:
    res: float = 0.25

    def __post_init__(self) -> None:
        if not 0.01 <= self.res <= 5 or abs(360 / self.res - round(360 / self.res)) > 1e-9:
            raise ValueError(f"Grid resolution must divide 360 evenly, got {self.res}")

    @property
    def ncols(self) -> int:
        return round(360 / self.res)

    @property
    def nrows(self) -> int:
        return round(180 / self.res)

    @property
    def size(self) -> int:
        return self.ncols * self.nrows

    def cell_ids(self, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
        lon = np.asarray(lon, dtype="float64")
        lat = np.asarray(lat, dtype="float64")
        col = np.clip(np.floor((lon + 180.0) / self.res), 0, self.ncols - 1).astype("int64")
        row = np.clip(np.floor((90.0 - lat) / self.res), 0, self.nrows - 1).astype("int64")
        return row * self.ncols + col

    def cell_sql(self, lon: str = "longitude", lat: str = "latitude") -> str:
        """DuckDB expression computing the cell id of a point."""
        return (
            f"(LEAST(GREATEST(CAST(FLOOR((90.0 - {lat}) / {self.res}) AS BIGINT), 0), "
            f"{self.nrows - 1}) * {self.ncols} + "
            f"LEAST(GREATEST(CAST(FLOOR(({lon} + 180.0) / {self.res}) AS BIGINT), 0), "
            f"{self.ncols - 1}))"
        )

    def bounds(self, cell_id: np.ndarray) -> tuple[np.ndarray, ...]:
        """Return (west, south, east, north) arrays for the given cell ids."""
        cell_id = np.asarray(cell_id, dtype="int64")
        row, col = np.divmod(cell_id, self.ncols)
        west = -180.0 + col * self.res
        north = 90.0 - row * self.res
        return west, north - self.res, west + self.res, north

    def centers(self, cell_id: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        west, south, east, north = self.bounds(cell_id)
        return (west + east) / 2, (south + north) / 2

    def area_km2(self, cell_id: np.ndarray) -> np.ndarray:
        """Exact spherical area of each cell."""
        _, south, _, north = self.bounds(cell_id)
        dlon = np.deg2rad(self.res)
        return EARTH_RADIUS_KM**2 * dlon * (np.sin(np.deg2rad(north)) - np.sin(np.deg2rad(south)))


def latitude_zone(lat: np.ndarray) -> np.ndarray:
    """Coarse biome proxy from absolute latitude."""
    abs_lat = np.abs(np.asarray(lat, dtype="float64"))
    edges = [edge for edge, _ in LATITUDE_ZONES]
    names = np.array([name for _, name in LATITUDE_ZONES])
    return names[np.searchsorted(edges, abs_lat, side="right").clip(0, len(names) - 1)]


def land_cell_ids(spec: GridSpec, land: list[shapely.Geometry]) -> np.ndarray:
    """Ids of all cells whose footprint intersects any land polygon."""
    ids = np.arange(spec.size, dtype="int64")
    west, south, east, north = spec.bounds(ids)
    boxes = shapely.box(west, south, east, north)
    tree = STRtree(land)
    box_idx, land_idx = tree.query(boxes, predicate="intersects")
    # Drop cells that merely share an edge or corner with land.
    land_arr = np.asarray(land, dtype=object)
    real = ~shapely.touches(boxes[box_idx], land_arr[land_idx])
    return np.unique(box_idx[real]).astype("int64")


def build_cells(
    spec: GridSpec,
    land: list[shapely.Geometry],
    ecoregions: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build the ``cells`` table: land cells with id, geometry bounds and biome class.

    ``ecoregions`` (optional) is a GeoDataFrame with a ``biome`` column, e.g. the
    RESOLVE Ecoregions 2017 map. Cells outside every ecoregion polygon (coasts,
    small islands) and runs without an ecoregion map fall back to latitude zones.
    """
    ids = land_cell_ids(spec, land)
    west, south, east, north = spec.bounds(ids)
    lon, lat = (west + east) / 2, (south + north) / 2
    biome = latitude_zone(lat).astype(object)

    if ecoregions is not None and len(ecoregions):
        points = shapely.points(lon, lat)
        tree = STRtree(ecoregions.geometry.values)
        pt_idx, eco_idx = tree.query(points, predicate="within")
        first = pd.Series(eco_idx, index=pt_idx).groupby(level=0).first()
        biome[first.index.to_numpy()] = ecoregions["biome"].to_numpy()[first.to_numpy()]

    cells = pd.DataFrame(
        {
            "cell_id": ids,
            "lon": lon,
            "lat": lat,
            "west": west,
            "south": south,
            "east": east,
            "north": north,
            "area_km2": spec.area_km2(ids),
            "biome": biome.astype(str),
        }
    )
    log.info("Built %d land cells at %.3f°", len(cells), spec.res)
    return cells


def read_land(path: Path) -> list[shapely.Geometry]:
    import geopandas as gpd

    gdf = gpd.read_file(path)
    return list(gdf.geometry.explode(index_parts=False).values)


def read_ecoregions(path: Path, biome_field: str = "BIOME_NAME") -> pd.DataFrame:
    import geopandas as gpd

    gdf = gpd.read_file(path)
    if biome_field not in gdf.columns:
        raise ValueError(f"Ecoregion file has no {biome_field!r} column")
    gdf = gdf[[biome_field, "geometry"]].rename(columns={biome_field: "biome"})
    return gdf[gdf.geometry.notna() & gdf["biome"].notna()].reset_index(drop=True)
