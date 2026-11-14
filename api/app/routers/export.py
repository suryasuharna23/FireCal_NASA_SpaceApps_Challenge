import io
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Literal

import shapely
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.aoi import Aoi
from app.db import Dataset, connect, get_connection, get_dataset
from app.models import SeriesRequest
from app.series import aoi_monthly, fmt_ym, in_window, resolve_window, with_anomaly
from app.settings import get_settings

router = APIRouter(tags=["export"])

MONTHLY_COLUMNS = [
    "year", "month", "n_harmonized", "n_modis", "n_viirs", "ci_low", "ci_high",
    "median", "anomaly_pct", "percentile", "source", "provisional",
]  # fmt: skip
POINT_COLUMNS = [
    "latitude", "longitude", "acq_datetime", "daynight", "confidence", "frp",
    "sensor", "satellite", "source", "weight",
]  # fmt: skip
BATCH_ROWS = 100_000


class ExportRequest(SeriesRequest):
    kind: Literal["monthly", "points"] = "monthly"


def header(kind: str, aoi: Aoi, start: str, end: str, meta: dict, ref=None) -> str:
    lines = [
        f"# FireCal export: {kind}, {start} to {end}, AOI {aoi.area_km2:,.0f} km2",
        "# Data: NASA FIRMS (Fire Information for Resource Management System), MODIS C6.1 "
        "and VIIRS 375 m; https://firms.modaps.eosdis.nasa.gov",
        f"# Harmonized to MODIS-equivalent scale; data version {meta['data_version']}, "
        f"MODIS until {meta['transition_month']}",
        f"# Generated {datetime.now(UTC).isoformat(timespec='seconds')}",
    ]
    if ref:
        lines.insert(3, f"# Median/anomaly reference years: {ref[0]}-{ref[1]}")
    if kind == "points":
        lines.insert(3, "# weight = MODIS-equivalent contribution of each detection")
    return "\n".join(lines) + "\n"


def stream_points(ds: Dataset, aoi: Aoi, start, end) -> Iterator[str]:
    """Yield CSV chunks year by year; memory stays bounded (NFR-02)."""
    con = connect()
    try:
        minx, miny, maxx, maxy = aoi.geometry.bounds
        shapely.prepare(aoi.geometry)
        first = True
        for year in range(start[0], end[0] + 1):
            m0 = start[1] if year == start[0] else 1
            m1 = end[1] if year == end[0] else 12
            try:
                reader = con.sql(
                    f"""SELECT {", ".join(POINT_COLUMNS)} FROM {ds.points_year(year)}
                        WHERE month BETWEEN ? AND ?
                          AND longitude BETWEEN ? AND ? AND latitude BETWEEN ? AND ?
                        ORDER BY acq_datetime""",
                    params=[m0, m1, minx, maxx, miny, maxy],
                ).to_arrow_reader(BATCH_ROWS)
            except Exception as exc:
                if "No files found" in str(exc):
                    continue
                raise
            for batch in reader:
                df = batch.to_pandas()
                df = df[shapely.contains_xy(aoi.geometry, df.longitude, df.latitude)]
                if df.empty:
                    continue
                buf = io.StringIO()
                df.to_csv(buf, index=False, header=first, date_format="%Y-%m-%dT%H:%MZ")
                first = False
                yield buf.getvalue()
        if first:
            yield ",".join(POINT_COLUMNS) + "\n"
    finally:
        con.close()


@router.post("/export")
def post_export(
    req: ExportRequest,
    con=Depends(get_connection),
    ds: Dataset = Depends(get_dataset),
) -> StreamingResponse:
    """Download CSV for the AOI and range (FR-W-16, FR-W-17, NFR-02).

    * ``kind=monthly``: one row per month with harmonized and per-sensor counts,
      90 % interval, median/anomaly and source.
    * ``kind=points``: every clean detection (FR-D-06 attributes + harmonization
      weight), streamed in batches.

    The first lines start with ``#`` and carry the NASA FIRMS attribution.
    """
    meta = ds.meta(con)
    aoi = Aoi.from_geojson(req.aoi, get_settings().max_aoi_km2)
    window = resolve_window(meta, req.start, req.end, req.reference_years)
    start, end = fmt_ym(window.start), fmt_ym(window.end)
    filename = f"firecal_{req.kind}_{start}_{end}.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    if req.kind == "monthly":
        series = with_anomaly(aoi_monthly(con, ds, aoi, meta), window.reference)
        view = in_window(series, window.start, window.end)[MONTHLY_COLUMNS]
        body = header("monthly", aoi, start, end, meta, window.reference) + view.round(
            {
                "n_harmonized": 2,
                "n_modis": 2,
                "n_viirs": 2,
                "ci_low": 2,
                "ci_high": 2,
                "median": 2,
                "anomaly_pct": 1,
                "percentile": 1,
            }  # fmt: skip
        ).to_csv(index=False)
        headers["X-Row-Count"] = str(len(view))
        return StreamingResponse(iter([body]), media_type="text/csv", headers=headers)

    def generate() -> Iterator[str]:
        yield header("points", aoi, start, end, meta)
        yield from stream_points(ds, aoi, window.start, window.end)

    return StreamingResponse(generate(), media_type="text/csv", headers=headers)
