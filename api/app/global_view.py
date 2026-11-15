"""Worldwide views expose observed counts without borrowing Indonesia corrections."""

import calendar
from collections import defaultdict
from datetime import date
from math import floor

from app.db import Dataset
from app.series import RangeError


def validate_global_period(meta, year, month, period, day=None, hour=None):
    start = date.fromisoformat(meta["start_date"])
    end = date.fromisoformat(meta["last_acq_date"])
    if period == "year":
        valid = start.year <= year <= end.year
    else:
        valid = (start.year, start.month) <= (year, month) <= (end.year, end.month)
    if not valid:
        raise RangeError(f"Global observations cover {start} through {end}")
    if period in ("day", "hour"):
        try:
            chosen = date(year, month, day)
        except (ValueError, TypeError) as exc:
            raise RangeError("A valid UTC day is required") from exc
        if not start <= chosen <= end:
            raise RangeError(f"Global observations cover {start} through {end}")
        if period == "hour" and hour is None:
            raise RangeError("Hour is required for hourly view")


def global_globe(con, ds: Dataset, year, month, period, day, hour, mode):
    if mode != "raw":
        raise RangeError("Global harmonization is unavailable; use raw NASA detection counts")
    meta = ds.meta(con)
    validate_global_period(meta, year, month, period, day, hour)
    clauses, args = ["year = ?"], [year]
    if period != "year":
        clauses.append("month = ?")
        args.append(month)
    if period in ("day", "hour"):
        clauses.append("day(acq_date) = ?")
        args.append(day)
    if period == "hour":
        clauses.append("hour = ?")
        args.append(hour)
    rows = con.execute(
        f"SELECT lon::DOUBLE,lat::DOUBLE,sum(raw) AS value "
        f"FROM read_parquet('{ds.path('globe.parquet')}') "
        f"WHERE {' AND '.join(clauses)} GROUP BY lon,lat ORDER BY value DESC,lon,lat",
        args,
    ).fetchall()
    resolution = 0.5
    original_cells = len(rows)
    while len(rows) > 5000:
        resolution *= 2
        bins = defaultdict(int)
        for lon, lat, value in rows:
            x = floor((lon + 180) / resolution) * resolution - 180 + resolution / 2
            y = floor((lat + 90) / resolution) * resolution - 90 + resolution / 2
            bins[x, y] += value
        rows = sorted(((x, y, n) for (x, y), n in bins.items()), key=lambda r: (-r[2], r[0], r[1]))
    return {
        "scope": "global",
        "year": year,
        "month": month,
        "period": period,
        "day": day,
        "hour": hour,
        "mode": "raw",
        "res": resolution,
        "original_cell_count": original_cells,
        "source": "MODIS+VIIRS",
        "provisional": meta["provisional"],
        "count": len(rows),
        "total": sum(r[2] for r in rows),
        "max": rows[0][2] if rows else 0,
        "truncated": len(rows) > 5000,
        "cells": [[lon, lat, value] for lon, lat, value in rows[:5000]],
        "data_version": meta["data_version"],
        "start_date": meta["start_date"],
        "last_acq_date": meta["last_acq_date"],
        "partial_period": period == "year"
        or (
            period == "month"
            and (
                (year, month) == tuple(map(int, meta["start_date"][:7].split("-")))
                and meta["start_date"][-2:] != "01"
                or (year, month) == tuple(map(int, meta["last_acq_date"][:7].split("-")))
                and date(year, month, int(meta["last_acq_date"][-2:])).day
                < calendar.monthrange(year, month)[1]
            )
        ),
        "lagging_sources": meta["lagging_sources"],
    }
