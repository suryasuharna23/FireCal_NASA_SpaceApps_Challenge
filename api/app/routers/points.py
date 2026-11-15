from datetime import date
from typing import Any, Literal

import numpy as np
import pandas as pd
import shapely
from fastapi import APIRouter, Depends
from pydantic import Field

from app.aoi import Aoi, Grid
from app.db import Dataset, DataUnavailableError, get_connection, get_dataset, get_global_dataset
from app.models import AoiRequest
from app.series import RangeError, parse_ym
from app.settings import get_settings

router = APIRouter(tags=["points"])

POINT_COLUMNS = (
    "latitude, longitude, acq_datetime, daynight, confidence, frp, sensor, satellite, "
    "source, weight, cell_id"
)


class PointsRequest(AoiRequest):
    scope: Literal["indonesia", "global"] = "indonesia"
    year: int
    month: int = Field(..., ge=1, le=12)
    period: Literal["month", "day", "hour"] = "month"
    day: int | None = Field(None, ge=1, le=31)
    hour: int | None = Field(None, ge=0, le=23)
    limit: int | None = Field(
        None, ge=1, description="Max points before switching to a grid (default MAX_POINTS)"
    )


def aoi_points(
    con,
    ds: Dataset,
    aoi: Aoi,
    year: int,
    month: int,
    columns: str = POINT_COLUMNS,
    day: int | None = None,
    hour: int | None = None,
) -> pd.DataFrame:
    """Raw points of one month inside the AOI polygon."""
    minx, miny, maxx, maxy = aoi.geometry.bounds
    filters = " AND day(acq_datetime) = ?" if day is not None else ""
    filters += " AND hour(acq_datetime) = ?" if hour is not None else ""
    args = [month, minx, maxx, miny, maxy]
    if day is not None:
        args.append(day)
    if hour is not None:
        args.append(hour)
    try:
        df = con.execute(
            f"""SELECT {columns} FROM {ds.points_year(year)}
                WHERE month = ? AND longitude BETWEEN ? AND ?
                  AND latitude BETWEEN ? AND ? {filters}""",
            args,
        ).df()
    except Exception as exc:  # missing partition -> no detections that year
        if "No files found" in str(exc):
            if ds.meta(con).get("format") == "firecal-global-v1":
                raise DataUnavailableError(
                    "Global observation files are missing; reinstall the data"
                ) from exc
            return pd.DataFrame(columns=[c.strip() for c in columns.split(",")])
        raise
    shapely.prepare(aoi.geometry)
    inside = shapely.contains_xy(aoi.geometry, df.longitude.to_numpy(), df.latitude.to_numpy())
    return df[inside].reset_index(drop=True)


def _feature(lon: float, lat: float, props: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [round(lon, 4), round(lat, 4)]},
        "properties": props,
    }


@router.post("/points")
def post_points(
    req: PointsRequest,
    con=Depends(get_connection),
    ds: Dataset = Depends(get_dataset),
) -> dict[str, Any]:
    """Raw hotspots of one month inside the AOI as GeoJSON (FR-W-15).

    Above ``limit`` points (default ``MAX_POINTS`` = 50,000) the response switches to
    grid cells (``aggregated: true``) with per-sensor counts and summed FRP.
    """
    settings = get_settings()
    if req.scope == "global":
        from app.global_view import validate_global_period

        ds = get_global_dataset()
        if not ds.exists("points"):
            raise DataUnavailableError("Global point detail is unavailable in this deployment")
        validate_global_period(ds.meta(con), req.year, req.month, req.period, req.day, req.hour)
    meta = ds.meta(con)
    aoi = Aoi.from_geojson(req.aoi, settings.max_aoi_km2)
    if not parse_ym(meta["start_month"]) <= (req.year, req.month) <= parse_ym(meta["end_month"]):
        raise RangeError(
            f"Month is outside the available data ({meta['start_month']} – {meta['end_month']})"
        )
    if req.period in ("day", "hour"):
        if req.day is None:
            raise RangeError("Day is required for daily and hourly views")
        try:
            chosen_date = date(req.year, req.month, req.day)
        except ValueError as exc:
            raise RangeError("Invalid date") from exc
        if meta.get("last_acq_date") and chosen_date > date.fromisoformat(meta["last_acq_date"]):
            raise RangeError("Date is after the latest acquisition")
        if req.period == "hour" and req.hour is None:
            raise RangeError("Hour is required for hourly view")
    limit = min(req.limit or settings.max_points, settings.max_points)
    df = aoi_points(
        con,
        ds,
        aoi,
        req.year,
        req.month,
        day=req.day if req.period != "month" else None,
        hour=req.hour if req.period == "hour" else None,
    )
    base = {
        "type": "FeatureCollection",
        "year": req.year,
        "month": req.month,
        "period": req.period,
        "day": req.day if req.period != "month" else None,
        "hour": req.hour if req.period == "hour" else None,
        "count": len(df),
        "attribution": "NASA FIRMS",
        "scope": req.scope,
        "data_version": meta["data_version"],
    }
    if len(df) <= limit:
        features = [
            _feature(
                r.longitude,
                r.latitude,
                {
                    "sensor": r.sensor,
                    "satellite": r.satellite,
                    "frp": None if pd.isna(r.frp) else round(float(r.frp), 2),
                    "time": pd.Timestamp(r.acq_datetime).strftime("%Y-%m-%dT%H:%MZ"),
                    "confidence": r.confidence,
                    "daynight": r.daynight,
                    "source": r.source,
                    "weight": None if pd.isna(r.weight) else round(float(r.weight), 4),
                },
            )
            for r in df.itertuples()
        ]
        return {**base, "aggregated": False, "features": features}

    res = float(meta["grid_res_deg"])
    cells = df.groupby("cell_id").agg(
        count=("sensor", "size"),
        modis=("sensor", lambda s: int((s == "MODIS").sum())),
        viirs=("sensor", lambda s: int((s == "VIIRS").sum())),
        frp=("frp", "sum"),
    )
    grid = Grid(res)
    row, col = np.divmod(cells.index.to_numpy(), grid.ncols)
    lon = -180 + (col + 0.5) * res
    lat = 90 - (row + 0.5) * res
    features = [
        _feature(
            x,
            y,
            {
                "count": int(c.count),
                "modis": c.modis,
                "viirs": c.viirs,
                "frp": round(float(c.frp), 1),
            },
        )  # fmt: skip
        for x, y, c in zip(lon, lat, cells.itertuples(), strict=True)
    ]
    return {**base, "aggregated": True, "cell_size_deg": res, "features": features}
