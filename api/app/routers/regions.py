import json
from typing import Any

import shapely
from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import Dataset, get_connection, get_dataset
from app.settings import get_settings

router = APIRouter(tags=["regions"])

FIELDS = "id, name, level, country, parent, area_km2, west, south, east, north"


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
    limit: int = Query(20, ge=1, le=100),
    con=Depends(get_connection),
    ds: Dataset = Depends(get_dataset),
) -> dict[str, Any]:
    """Search administrative regions (country, province/state, district) (FR-W-03).

    Name matches rank before country matches, then lower levels and shorter names.
    ``too_large`` marks regions above ``MAX_AOI_KM2`` that cannot be analysed.
    """
    pattern = f"%{q.strip().lower()}%"
    where = ["(lower(name) LIKE ? OR lower(country) LIKE ?)"]
    params: list[Any] = [pattern, pattern]
    if level is not None:
        where.append("level = ?")
        params.append(level)
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


@router.get("/regions/{region_id}")
def get_region(
    region_id: str, con=Depends(get_connection), ds: Dataset = Depends(get_dataset)
) -> dict[str, Any]:
    """One region with its simplified boundary as a GeoJSON Feature."""
    row = con.execute(
        f"SELECT {FIELDS}, geometry FROM {_table(ds)} WHERE id = ?", [region_id]
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"Unknown region {region_id!r}")
    props = _row(row[:-1], get_settings().max_aoi_km2)
    geometry = json.loads(shapely.to_geojson(shapely.from_wkb(row[-1])))
    return {"type": "Feature", "id": props["id"], "properties": props, "geometry": geometry}
