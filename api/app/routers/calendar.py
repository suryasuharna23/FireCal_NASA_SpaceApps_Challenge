from fastapi import APIRouter, Depends

from app.aoi import Aoi
from app.db import Dataset, get_connection, get_dataset
from app.models import CalendarResponse, SeriesRequest
from app.series import aoi_monthly, clean_number, fmt_ym, in_window, resolve_window, with_anomaly
from app.settings import get_settings

router = APIRouter(tags=["calendar"])


@router.post("/calendar", response_model=CalendarResponse)
def post_calendar(
    req: SeriesRequest,
    con=Depends(get_connection),
    ds: Dataset = Depends(get_dataset),
) -> CalendarResponse:
    """Year x month matrix of harmonized hotspot counts in the AOI (FR-W-07, NFR-01).

    Grid cells crossing the AOI boundary are weighted by the share of their area
    inside it. Every month of the range is returned (zero-filled), with the
    per-sensor counts, 90 % interval, source sensor and anomaly vs the median of
    the reference years.
    """
    meta = ds.meta(con)
    aoi = Aoi.from_geojson(req.aoi, get_settings().max_aoi_km2)
    window = resolve_window(meta, req.start, req.end, req.reference_years)
    series = with_anomaly(aoi_monthly(con, ds, aoi, meta), window.reference)
    view = in_window(series, window.start, window.end)
    months = [
        {
            "year": int(r.year),
            "month": int(r.month),
            "value": clean_number(r.n_harmonized),
            "raw": clean_number(r.raw),
            "n_modis": clean_number(r.n_modis),
            "n_viirs": clean_number(r.n_viirs),
            "ci_low": clean_number(r.ci_low),
            "ci_high": clean_number(r.ci_high),
            "source": r.source,
            "provisional": bool(r.provisional),
            "median": clean_number(r.median),
            "anomaly_pct": clean_number(r.anomaly_pct, 1),
            "percentile": clean_number(r.percentile, 1),
        }
        for r in view.itertuples()
    ]
    return CalendarResponse(
        aoi={"area_km2": round(aoi.area_km2, 1), "cells": series.attrs.get("cells", 0)},
        start=fmt_ym(window.start),
        end=fmt_ym(window.end),
        reference_years=window.reference,
        transition_month=meta["transition_month"],
        data_version=meta["data_version"],
        max_value=clean_number(float(view.n_harmonized.max()) if len(view) else 0.0),
        months=months,
    )
