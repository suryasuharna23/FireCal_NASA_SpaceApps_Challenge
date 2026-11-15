import json
from typing import Any

import shapely
from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import Dataset, DataUnavailableError, get_connection, get_dataset, get_global_dataset
from app.settings import get_settings

router = APIRouter(tags=["regions"])

FIELDS = "id, name, level, country, parent, area_km2, west, south, east, north"
SCOPES = Query("indonesia", pattern="^(indonesia|global)$", description="Data coverage")


def _scoped_dataset(scope: str) -> Dataset:
    """Region tables follow the data scope: Indonesia snapshot or worldwide snapshot."""
    getter = get_global_dataset if scope == "global" else get_dataset
    try:
        return getter()
    except DataUnavailableError as exc:
        raise HTTPException(503, str(exc)) from exc


def _row(row: tuple, max_km2: float) -> dict[str, Any]:
    rid, name, level, country, parent, area, w, s, e, n = row
    return {
        "id": rid,
        "name": name,
        "level": int(level),
        "country": country,
        "parent": parent,
        "area_km2": round(float(area), 1),
        "bbox": [round(w, 4), round(s, 4), round(e, 4), round(n, 4)],
        "too_large": float(area) > max_km2,
    }


def _table(ds: Dataset) -> str:
    if not ds.exists("regions.parquet"):
        raise HTTPException(503, "Region boundaries not built; run 'firecal regions'")
    return f"read_parquet('{ds.path('regions.parquet')}')"


@router.get("/regions")
def search_regions(
    q: str = Query("", max_length=80, description="Name or country, case-insensitive"),
    level: int | None = Query(None, ge=0, le=2),
    country: str | None = Query(None, max_length=80, description="Exact country name filter"),
    limit: int = Query(20, ge=1, le=500),
    scope: str = SCOPES,
    con=Depends(get_connection),
) -> dict[str, Any]:
    """Search administrative regions (country, province/state, district) (FR-W-03).

    Name matches rank before country matches, then lower levels and shorter names.
    ``too_large`` marks regions above ``MAX_AOI_KM2`` that cannot be analysed.
    The ``global`` scope searches every Natural Earth country and admin-1 province.
    """
    ds = _scoped_dataset(scope)
    pattern = f"%{q.strip().lower()}%"
    where = ["(lower(name) LIKE ? OR lower(country) LIKE ?)"]
    params: list[Any] = [pattern, pattern]
    if level is not None:
        where.append("level = ?")
        params.append(level)
    if country is not None:
        where.append("country = ?")
        params.append(country)
    rows = con.execute(
        f"""SELECT {FIELDS} FROM {_table(ds)}
            WHERE {" AND ".join(where)}
            ORDER BY (lower(name) = ?) DESC, (lower(name) LIKE ?) DESC,
                     (lower(name) LIKE ?) DESC, level, length(name), name
            LIMIT ?""",
        [*params, q.strip().lower(), f"{q.strip().lower()}%", pattern, limit],
    ).fetchall()
    max_km2 = get_settings().max_aoi_km2
    return {"query": q, "results": [_row(r, max_km2) for r in rows]}


@router.get("/regions/boundaries")
def region_boundaries(
    scope: str = SCOPES,
    country: str | None = Query(None, max_length=80, description="Global scope: one country"),
    con=Depends(get_connection),
) -> dict[str, Any]:
    """Saved administrative boundaries for map selection.

    Indonesia scope returns the country and every province. The global scope
    returns every country at level 0, or one country's provinces when ``country``
    is given (payloads stay bounded).
    """
    ds = _scoped_dataset(scope)
    if scope == "global" and country is None:
        condition = "level = 0"
        params: list[Any] = []
    elif scope == "global":
        condition = "level IN (0, 1) AND country = ?"
        params = [country]
    else:
        condition = "level IN (0, 1) AND country = 'Indonesia'"
        params = []
    rows = con.execute(
        f"SELECT {FIELDS}, geometry FROM {_table(ds)} WHERE {condition} ORDER BY level, name",
        params,
    ).fetchall()
    max_km2 = get_settings().max_aoi_km2
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": row[0],
                "properties": _row(row[:-1], max_km2),
                "geometry": json.loads(shapely.to_geojson(shapely.from_wkb(row[-1]))),
            }
            for row in rows
        ],
    }


@router.get("/regions/{region_id}")
def get_region(
    region_id: str,
    scope: str = SCOPES,
    con=Depends(get_connection),
) -> dict[str, Any]:
    """One region with its simplified boundary as a GeoJSON Feature."""
    ds = _scoped_dataset(scope)
    row = con.execute(
        f"SELECT {FIELDS}, geometry FROM {_table(ds)} WHERE id = ?", [region_id]
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"Unknown region {region_id!r}")
    props = _row(row[:-1], get_settings().max_aoi_km2)
    geometry = json.loads(shapely.to_geojson(shapely.from_wkb(row[-1])))
    return {"type": "Feature", "id": props["id"], "properties": props, "geometry": geometry}
