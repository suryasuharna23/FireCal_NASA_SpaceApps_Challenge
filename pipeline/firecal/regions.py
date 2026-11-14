"""Administrative boundaries for region search (T-24, FR-W-03).

Sources:

* **GADM 4.1** levels GeoPackage (``gadm_410-levels.gpkg``, layers ``ADM_0``..``ADM_2``) —
  the FRD's reference source for countries, provinces/states and districts.
* **Natural Earth** admin-0 countries and admin-1 states/provinces GeoJSON — a light
  default that needs no registration.

Output ``processed/regions.parquet``: ``id, name, level, country, parent, area_km2,
west, south, east, north, geometry`` (WKB, simplified) sorted by level and name.
"""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely
from pyproj import Geod

from firecal.paths import DataPaths

log = logging.getLogger(__name__)

NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson"
DEFAULT_SOURCES = (
    f"{NE}/ne_50m_admin_0_countries.geojson",
    f"{NE}/ne_10m_admin_1_states_provinces.geojson",
)
SIMPLIFY_DEG = 0.005
GEOD = Geod(ellps="WGS84")


def _first(df: pd.DataFrame, *names: str) -> pd.Series:
    for name in names:
        if name in df.columns:
            return df[name].astype("string")
    return pd.Series(pd.NA, index=df.index, dtype="string")


def from_natural_earth(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    cols = {c.lower(): c for c in gdf.columns}
    if "adm1_code" in cols:  # admin-1 states/provinces
        df = gdf.rename(columns=str.lower)
        return pd.DataFrame(
            {
                "id": "NE1-" + _first(df, "adm1_code"),
                "name": _first(df, "name", "name_en"),
                "level": 1,
                "country": _first(df, "admin", "geonunit"),
                "parent": _first(df, "admin", "geonunit"),
                "geometry": gdf.geometry.values,
            }
        )
    df = gdf.rename(columns=str.lower)
    return pd.DataFrame(
        {
            "id": "NE0-" + _first(df, "adm0_a3", "iso_a3"),
            "name": _first(df, "name", "admin"),
            "level": 0,
            "country": _first(df, "name", "admin"),
            "parent": pd.Series(pd.NA, index=df.index, dtype="string"),
            "geometry": gdf.geometry.values,
        }
    )


def from_gadm(path: Path, levels: tuple[int, ...] = (0, 1, 2)) -> pd.DataFrame:
    frames = []
    for level in levels:
        gdf = gpd.read_file(path, layer=f"ADM_{level}")
        name = "COUNTRY" if level == 0 else f"NAME_{level}"
        parent = None if level == 0 else ("COUNTRY" if level == 1 else f"NAME_{level - 1}")
        frames.append(
            pd.DataFrame(
                {
                    "id": "GADM-" + gdf[f"GID_{level}"].astype(str),
                    "name": gdf[name].astype("string"),
                    "level": level,
                    "country": gdf["COUNTRY"].astype("string"),
                    "parent": gdf[parent].astype("string") if parent else pd.NA,
                    "geometry": gdf.geometry.values,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def load_source(path: Path) -> pd.DataFrame:
    if path.suffix == ".gpkg":
        return from_gadm(path)
    return from_natural_earth(gpd.read_file(path))


def build_regions(sources: list[Path], out: Path) -> pd.DataFrame:
    df = pd.concat([load_source(p) for p in sources], ignore_index=True)
    df = df[df.geometry.notna() & df.name.notna()].copy()
    geoms = shapely.make_valid(df.geometry.to_numpy())
    geoms = shapely.simplify(geoms, SIMPLIFY_DEG, preserve_topology=True)
    df["area_km2"] = [abs(GEOD.geometry_area_perimeter(g)[0]) / 1e6 for g in geoms]
    bounds = shapely.bounds(geoms)
    df[["west", "south", "east", "north"]] = bounds
    df["geometry"] = shapely.to_wkb(geoms)
    df = (
        df.drop_duplicates("id")
        .sort_values(["level", "country", "name"], ignore_index=True)
        .astype({"level": "int8"})
    )
    df.to_parquet(out, index=False)
    log.info("Wrote %d regions (%s)", len(df), df.level.value_counts().to_dict())
    return df


def regions(paths: DataPaths, sources: list[str] | None = None) -> pd.DataFrame:
    from firecal.io import resolve_source

    local = [resolve_source(s, paths.reference) for s in (sources or DEFAULT_SOURCES)]
    return build_regions(local, paths.regions)
