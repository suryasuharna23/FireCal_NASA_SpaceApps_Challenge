import threading
from typing import Any, Literal

from cachetools import TTLCache
from fastapi import APIRouter, Depends, Query

from app.db import Dataset, get_connection, get_dataset
from app.series import RangeError, parse_ym
from app.settings import get_settings

router = APIRouter(tags=["globe"])

#: NFR-12: the globe renders at >= 30 fps with up to 5,000 cells.
MAX_CELLS = 5000

_cache: TTLCache = TTLCache(maxsize=512, ttl=get_settings().cache_ttl_seconds)
_lock = threading.Lock()


@router.get("/globe")
def get_globe(
    year: int = Query(..., ge=2000),
    month: int = Query(..., ge=1, le=12),
    mode: Literal["harmonized", "raw"] = "harmonized",
    con=Depends(get_connection),
    ds: Dataset = Depends(get_dataset),
) -> dict[str, Any]:
    """World hotspot cells for one month on a 0.5° grid (FR-W-23, NFR-12).

    Only cells with a value > 0 are returned, as compact ``[lon, lat, value]``
    triples. ``mode=raw`` returns the unconverted count of that month's source
    sensor (FR-W-26). Above 5,000 cells the strongest cells are kept
    (``truncated: true``). Responses are gzip-compressed and cached.
    """
    meta = ds.meta(con)
    if not parse_ym(meta["start_month"]) <= (year, month) <= parse_ym(meta["end_month"]):
        raise RangeError(
            f"Month is outside the available data ({meta['start_month']} – {meta['end_month']})"
        )
    key = (ds.uri, meta.get("data_version"), year, month, mode)
    with _lock:
        if key in _cache:
            return _cache[key]

    column = "harmonized" if mode == "harmonized" else "raw"
    rows = con.execute(
        f"""SELECT lon, lat, {column} AS value
            FROM read_parquet('{ds.path("globe.parquet")}')
            WHERE year = ? AND month = ? AND {column} > 0
            ORDER BY value DESC""",
        [year, month],
    ).fetchall()
    month_info = con.execute(
        f"SELECT source, has_nrt FROM {ds.months} WHERE year = ? AND month = ?", [year, month]
    ).fetchone() or ("MODIS", False)
    cells = [[round(lon, 2), round(lat, 2), round(value, 2)] for lon, lat, value in rows]
    body = {
        "year": year,
        "month": month,
        "mode": mode,
        "res": 0.5,
        "source": month_info[0],
        "provisional": bool(month_info[1]),
        "count": len(cells),
        "total": round(sum(c[2] for c in cells), 1),
        "max": cells[0][2] if cells else 0,
        "truncated": len(cells) > MAX_CELLS,
        "cells": cells[:MAX_CELLS],
        "data_version": meta.get("data_version"),
    }
    with _lock:
        _cache[key] = body
    return body
