from typing import Any

from fastapi import APIRouter, Depends

from app import __version__
from app.db import Dataset, DataUnavailableError, get_connection, get_dataset
from app.settings import get_settings

router = APIRouter(tags=["meta"])

ATTRIBUTION = (
    "NASA FIRMS (Fire Information for Resource Management System), "
    "MODIS and VIIRS 375 m — https://firms.modaps.eosdis.nasa.gov"
)


@router.get("/meta")
def get_meta(con=Depends(get_connection), ds: Dataset = Depends(get_dataset)) -> dict[str, Any]:
    """Data version, last update, data range and NRT status (FR-D-07, FR-W-22, NFR-07).

    ``nrt.provisional`` is true when the latest months still contain near-real-time
    detections that will be replaced by standard data. ``nrt.ok`` is false when the
    last FIRMS update failed; the API then keeps serving the previous data and the
    web app shows a warning. Without processed data ``status`` is ``no_data``.
    """
    settings = get_settings()
    base: dict[str, Any] = {
        "api_version": __version__,
        "attribution": ATTRIBUTION,
        "max_aoi_km2": settings.max_aoi_km2,
        "default_reference_years": list(settings.default_reference_years),
    }
    try:
        meta = ds.meta(con)
    except DataUnavailableError as exc:
        return {**base, "status": "no_data", "detail": str(exc), "data_version": None}

    provisional_months = (
        con.execute(
            f"SELECT year, month FROM {ds.months} WHERE has_nrt ORDER BY year, month"
        ).fetchall()
        if ds.exists("months.parquet")
        else []
    )
    nrt_report = ds.report("nrt.json", con) or {}
    validation = ds.report("validation.json", con) or {}
    glob = (validation.get("global") or {}).get("after") or {}
    return {
        **base,
        "status": "ok",
        "data_version": meta.get("data_version"),
        "last_updated": meta.get("processed_at"),
        "last_acq_date": meta.get("last_acq_date"),
        "start_month": meta.get("start_month"),
        "end_month": meta.get("end_month"),
        "transition_month": meta.get("transition_month"),
        "calibration_period": meta.get("calibration_period"),
        "grid_res_deg": meta.get("grid_res_deg"),
        "coverage": meta.get("coverage"),
        "source_versions": meta.get("source_versions"),
        "dataset_status": meta.get("dataset_status"),
        "nrt": {
            "provisional": bool(provisional_months),
            "since": meta.get("nrt_since"),
            "provisional_months": [f"{y}-{m:02d}" for y, m in provisional_months],
            "last_run": nrt_report.get("run_at"),
            "ok": nrt_report.get("ok", True),
            "errors": nrt_report.get("errors", {}),
        },
        "validation": {
            "test_years": validation.get("test_years"),
            "r": glob.get("r"),
            "bias": glob.get("bias"),
            "mae": glob.get("mae"),
            "meets_target": validation.get("meets_target_global"),
            "limitations": validation.get("limitations", []),
        },
    }
