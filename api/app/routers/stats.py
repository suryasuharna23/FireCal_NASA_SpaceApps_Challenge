from fastapi import APIRouter, Depends

from app.aoi import Aoi
from app.db import Dataset, get_connection, get_dataset
from app.models import SeriesRequest, StatsResponse
from app.series import aoi_monthly, fmt_ym, resolve_window, with_anomaly
from app.settings import get_settings
from app.stats import compute_stats

router = APIRouter(tags=["stats"])


@router.post("/stats", response_model=StatsResponse)
def post_stats(
    req: SeriesRequest,
    con=Depends(get_connection),
    ds: Dataset = Depends(get_dataset),
) -> StatsResponse:
    """Monthly climatology (median, P25-P75), summary card values, annual totals with
    rank and critical months for the AOI (FR-W-06, FR-W-11, FR-W-12, FR-W-13, FR-W-14).

    The climatology and anomalies use ``reference_years`` (default
    ``REFERENCE_YEARS``); the "current" year/month is the last month of the range.
    """
    meta = ds.meta(con)
    aoi = Aoi.from_geojson(req.aoi, get_settings().max_aoi_km2)
    window = resolve_window(meta, req.start, req.end, req.reference_years)
    series = with_anomaly(aoi_monthly(con, ds, aoi, meta), window.reference)
    return StatsResponse(
        aoi={"area_km2": round(aoi.area_km2, 1), "cells": series.attrs.get("cells", 0)},
        start=fmt_ym(window.start),
        end=fmt_ym(window.end),
        reference_years=window.reference,
        data_version=meta["data_version"],
        **compute_stats(series, window),
    )
