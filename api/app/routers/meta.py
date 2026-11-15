from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from app import __version__
from app.db import Dataset, DataUnavailableError, get_connection, get_dataset, get_global_dataset
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
    try:
        global_ds = get_global_dataset()
        global_meta = {
            **global_ds.meta(con),
            "status": "ok",
            "points_available": global_ds.exists("points"),
        }
        global_status = Path(settings.live_repo_root) / "data/global/status.json"
        if settings.live_auto_refresh and global_status.is_file():
            import json

            global_meta["live"] = json.loads(global_status.read_text())
    except DataUnavailableError as exc:
        global_meta = {"status": "unavailable", "detail": str(exc)}
    live_status = None
    if settings.live_auto_refresh:
        import json

        try:
            live_status = json.loads(
                (Path(settings.live_repo_root) / "data/live/status.json").read_text()
            )
        except (OSError, ValueError):
            live_status = {"status": "waiting"}
    base: dict[str, Any] = {
        "api_version": __version__,
        "attribution": ATTRIBUTION,
        "max_aoi_km2": settings.max_aoi_km2,
        "default_reference_years": list(settings.default_reference_years),
        "live": live_status,
        "global": global_meta,
        "freshness_status": (
            "error"
            if live_status and live_status.get("status") in {"failed", "missing_key"}
            else "checking"
            if live_status and live_status.get("status") == "updating"
            else "checked"
            if live_status and live_status.get("status") in {"updated", "up_to_date"}
            else "unknown"
            if live_status
            else "snapshot_only"
        ),
    }
    meta = ds.meta(con)

    provisional_months = (
        con.execute(
            f"SELECT year, month FROM {ds.months} WHERE has_nrt ORDER BY year, month"
        ).fetchall()
        if ds.exists("months.parquet")
        else []
    )
    nrt_report = ds.report("nrt.json", con) or {}
    if live_status and live_status.get("status") in {"failed", "missing_key"}:
        nrt_report = {
            **nrt_report,
            "ok": False,
            "errors": {
                **nrt_report.get("errors", {}),
                "live_update": live_status.get("detail", "NASA update failed"),
            },
        }
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
