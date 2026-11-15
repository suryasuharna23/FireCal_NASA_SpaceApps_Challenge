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
    month: int = Query(1, ge=1, le=12),
    period: Literal["year", "month", "day", "hour"] = "month",
    day: int | None = Query(None, ge=1, le=31),
    hour: int | None = Query(None, ge=0, le=23),
    mode: Literal["harmonized", "raw"] = "harmonized",
    con=Depends(get_connection),
    ds: Dataset = Depends(get_dataset),
) -> dict[str, Any]:
    """Hotspot cells for a year, month, day or UTC hour on a 0.5° grid.

    Only cells with a value > 0 are returned, as compact ``[lon, lat, value]``
    triples. ``mode=raw`` returns the unconverted count of that month's source
    sensor (FR-W-26). Above 5,000 cells the strongest cells are kept
    (``truncated: true``). Responses are gzip-compressed and cached.
    """
    meta = ds.meta(con)
    from datetime import date

    if period == "year":
        valid = int(meta["start_month"][:4]) <= year <= int(meta["end_month"][:4])
    else:
        valid = parse_ym(meta["start_month"]) <= (year, month) <= parse_ym(meta["end_month"])
    if not valid:
        raise RangeError(
            f"Period is outside the available data ({meta['start_month']} – {meta['end_month']})"
        )
    if period in ("day", "hour"):
        if day is None:
            raise RangeError("Day is required for daily and hourly views")
        try:
            chosen_date = date(year, month, day)
        except ValueError as exc:
            raise RangeError("Invalid date") from exc
        if meta.get("last_acq_date") and chosen_date > date.fromisoformat(meta["last_acq_date"]):
            raise RangeError("Date is after the latest acquisition")
        if period == "hour" and hour is None:
            raise RangeError("Hour is required for hourly view")
    key = (ds.uri, meta.get("data_version"), period, year, month, day, hour, mode)
    with _lock:
        if key in _cache:
            return _cache[key]

    column = "harmonized" if mode == "harmonized" else "raw"
    if period in ("year", "month"):
        where = "year = ?" if period == "year" else "year = ? AND month = ?"
        args = [year] if period == "year" else [year, month]
        rows = con.execute(
            f"""SELECT lon, lat, SUM({column}) AS value
                FROM read_parquet('{ds.path("globe.parquet")}')
                WHERE {where}
                GROUP BY lon, lat HAVING SUM({column}) > 0
                ORDER BY value DESC""",
            args,
        ).fetchall()
    else:
        # Acquisition timestamps are UTC. Raw point partitions cover Indonesia.
        value = "COALESCE(weight, 0)" if mode == "harmonized" else "1"
        hour_clause = "AND hour(acq_datetime) = ?" if period == "hour" else ""
        args = [month, day] + ([hour] if period == "hour" else [])
        try:
            rows = con.execute(
                f"""SELECT floor(longitude * 2) / 2 + 0.25 AS lon,
                           floor(latitude * 2) / 2 + 0.25 AS lat,
                           SUM({value}) AS value
                    FROM {ds.points_year(year)}
                    WHERE month = ? AND in_series AND day(acq_datetime) = ? {hour_clause}
                    GROUP BY lon, lat HAVING SUM({value}) > 0
                    ORDER BY value DESC""",
                args,
            ).fetchall()
        except Exception as exc:
            if "No files found" not in str(exc):
                raise
            rows = []
    if period == "year":
        month_info = con.execute(
            f"SELECT source, BOOL_OR(has_nrt) FROM {ds.months} WHERE year = ? "
            "GROUP BY source ORDER BY COUNT(*) DESC LIMIT 1", [year]
        ).fetchone() or ("MODIS", False)
    else:
        month_info = con.execute(
            f"SELECT source, has_nrt FROM {ds.months} WHERE year = ? AND month = ?", [year, month]
        ).fetchone() or ("MODIS", False)
    cells = [[round(lon, 2), round(lat, 2), round(value, 2)] for lon, lat, value in rows]
    body = {
        "year": year,
        "month": month,
        "period": period,
        "day": day if period in ("day", "hour") else None,
        "hour": hour if period == "hour" else None,
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
