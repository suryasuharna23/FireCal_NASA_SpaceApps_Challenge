"""Area of interest handling: GeoJSON parsing, validation and grid-cell weights."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import shapely
from pyproj import Geod
from shapely.geometry import shape
from shapely.validation import make_valid

GEOD = Geod(ellps="WGS84")


class AoiError(ValueError):
    """Invalid or unsupported area of interest (mapped to HTTP 422)."""


def geodesic_area_km2(geom: shapely.Geometry) -> float:
    area, _ = GEOD.geometry_area_perimeter(geom)
    return abs(area) / 1e6


def parse_geometry(geojson: dict[str, Any]) -> shapely.Geometry:
    """Accept a GeoJSON geometry, Feature or single-feature FeatureCollection."""
    obj = geojson
    if obj.get("type") == "FeatureCollection":
        features = obj.get("features") or []
        if len(features) != 1:
            raise AoiError("Provide exactly one polygon feature")
        obj = features[0]
    if obj.get("type") == "Feature":
        obj = obj.get("geometry") or {}
    if obj.get("type") not in {"Polygon", "MultiPolygon"}:
        raise AoiError("AOI must be a Polygon or MultiPolygon")
    try:
        geom = shape(obj)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise AoiError(f"Malformed GeoJSON geometry: {exc}") from exc
    if geom.is_empty:
        raise AoiError("AOI geometry is empty")
    minx, miny, maxx, maxy = geom.bounds
    if minx < -180 or maxx > 180 or miny < -90 or maxy > 90:
        raise AoiError("Coordinates must be longitude [-180, 180] and latitude [-90, 90]")
    if not geom.is_valid:
        geom = make_valid(geom)
        polys = [g for g in getattr(geom, "geoms", [geom]) if g.geom_type.endswith("Polygon")]
        geom = shapely.union_all(polys)
    return geom


@dataclass(frozen=True)
class Aoi:
    geometry: shapely.Geometry
    area_km2: float
    key: str

    @classmethod
    def from_geojson(cls, geojson: dict[str, Any], max_km2: float) -> Aoi:
        geom = parse_geometry(geojson)
        area = geodesic_area_km2(geom)
        if area > max_km2:
            raise AoiError(
                f"AOI is {area:,.0f} km²; the maximum is {max_km2:,.0f} km². Draw a smaller area."
            )
        canonical = shapely.to_wkb(shapely.set_precision(geom, 1e-6), hex=True)
        return cls(geom, area, hashlib.sha1(canonical.encode()).hexdigest())

    def to_geojson(self) -> dict[str, Any]:
        return json.loads(shapely.to_geojson(self.geometry))


@dataclass(frozen=True)
class Grid:
    res: float

    @property
    def ncols(self) -> int:
        return round(360 / self.res)

    @property
    def nrows(self) -> int:
        return round(180 / self.res)

    def cell_weights(self, geom: shapely.Geometry) -> pd.DataFrame:
        """Cells intersecting ``geom`` with ``w`` = fraction of the cell inside the AOI.

        Fractions are computed in lon/lat space, which is accurate within a single
        0.25° cell. Summing ``value * w`` apportions each cell by intersection area.
        """
        minx, miny, maxx, maxy = geom.bounds
        c0 = int(np.clip(np.floor((minx + 180) / self.res), 0, self.ncols - 1))
        c1 = int(np.clip(np.floor((maxx + 180) / self.res), 0, self.ncols - 1))
        r0 = int(np.clip(np.floor((90 - maxy) / self.res), 0, self.nrows - 1))
        r1 = int(np.clip(np.floor((90 - miny) / self.res), 0, self.nrows - 1))
        rows, cols = np.meshgrid(np.arange(r0, r1 + 1), np.arange(c0, c1 + 1), indexing="ij")
        rows, cols = rows.ravel(), cols.ravel()
        west = -180 + cols * self.res
        north = 90 - rows * self.res
        boxes = shapely.box(west, north - self.res, west + self.res, north)
        shapely.prepare(geom)
        hit = shapely.intersects(geom, boxes)
        inter = shapely.area(shapely.intersection(boxes[hit], geom))
        w = inter / (self.res * self.res)
        ids = rows[hit].astype("int64") * self.ncols + cols[hit]
        out = pd.DataFrame({"cell_id": ids, "w": np.clip(w, 0, 1)})
        return out[out.w > 1e-9].reset_index(drop=True)
