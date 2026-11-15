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


def global_globe(con, ds: Dataset, year, month, period, day, hour, mode, max_cells=5000):
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
    while len(rows) > max_cells:
        resolution *= 2
        bins = defaultdict(int)
        for lon, lat, value in rows:
            x = floor((lon + 180) / resolution) * resolution - 180 + resolution / 2
            y = floor((lat + 90) / resolution) * resolution - 90 + resolution / 2
            bins[x, y] += value
        rows = sorted(((x, y, n) for (x, y), n in bins.items()), key=lambda r: (-r[2], r[0], r[1]))
    representative_points = None
    if period in ("year", "month"):
        if ds.exists("representatives.parquet"):
            representatives = ds.path("representatives.parquet")
            reps = con.execute(
                f"SELECT cell_lon,cell_lat,lon,lat FROM read_parquet('{representatives}') "
                "WHERE year = ? AND (? = 0 OR month = ?) ORDER BY month,cell_lon,cell_lat",
                [year, 0 if period == "year" else month, month],
            ).fetchall()
        elif ds.exists("points"):
            # Full local installs retain all points; compact Vercel installs carry
            # the verified representatives generated during staging instead.
            reps = con.execute(
                f"""WITH raw AS (
                    SELECT floor(longitude * 2) / 2 + 0.25 AS cell_lon,
                           floor(latitude * 2) / 2 + 0.25 AS cell_lat,
                           longitude, latitude,
                           hash(longitude, latitude, acq_datetime, satellite) AS pick
                    FROM {ds.points_year(year)}
                    WHERE ? = 0 OR month = ?
                )
                SELECT cell_lon,cell_lat,arg_min(longitude,pick),arg_min(latitude,pick)
                FROM raw GROUP BY cell_lon,cell_lat ORDER BY cell_lon,cell_lat""",
                [0 if period == "year" else month, month],
            ).fetchall()
        else:
            reps = []
        if reps:
            locations = {}
            for cell_lon, cell_lat, lon, lat in reps:
                x = floor((cell_lon + 180) / resolution) * resolution - 180 + resolution / 2
                y = floor((cell_lat + 90) / resolution) * resolution - 90 + resolution / 2
                locations.setdefault((x, y), (lon, lat))
            representative_points = [
                [round(locations[(x, y)][0], 4), round(locations[(x, y)][1], 4), 1]
                for x, y, _ in rows[:max_cells]
                if (x, y) in locations
            ]
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
        "truncated": len(rows) > max_cells,
        "cells": [[lon, lat, value] for lon, lat, value in rows[:max_cells]],
        "points": representative_points,
        "points_note": (
            "Sample of observed detection locations; at most one per occupied grid cell. "
            "Not the full set of detections."
            if representative_points is not None
            else None
        ),
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
