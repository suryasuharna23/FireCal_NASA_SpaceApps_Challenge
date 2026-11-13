"""AOI monthly series from the harmonized cube, with anomalies and caching."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from cachetools import TTLCache

from app.aoi import Aoi, Grid
from app.db import Dataset
from app.settings import get_settings

YM = tuple[int, int]


class RangeError(ValueError):
    """Requested date range or reference years fall outside the data (HTTP 422)."""


def parse_ym(value: str) -> YM:
    try:
        year, month = value.split("-")
        ym = int(year), int(month)
    except ValueError as exc:
        raise RangeError(f"Invalid month {value!r}; use YYYY-MM") from exc
    if not 1 <= ym[1] <= 12:
        raise RangeError(f"Invalid month {value!r}; use YYYY-MM")
    return ym


def fmt_ym(ym: YM) -> str:
    return f"{ym[0]}-{ym[1]:02d}"


@dataclass(frozen=True)
class Window:
    start: YM
    end: YM
    reference: tuple[int, int]


def resolve_window(
    meta: dict[str, Any],
    start: str | None,
    end: str | None,
    reference: tuple[int, int] | None,
) -> Window:
    """Apply defaults (2001-01 .. latest month, REFERENCE_YEARS) and validate (FR-W-05/06)."""
    data_start, data_end = parse_ym(meta["start_month"]), parse_ym(meta["end_month"])
    s = parse_ym(start) if start else max((2001, 1), data_start)
    e = parse_ym(end) if end else data_end
    available = f"{meta['start_month']} – {meta['end_month']}"
    if s > e:
        raise RangeError("Start month must not be after end month")
    if s < data_start or e > data_end:
        raise RangeError(f"Date range is outside the available data ({available})")
    ref = reference or get_settings().default_reference_years
    ref = (max(ref[0], data_start[0]), min(ref[1], data_end[0]))
    if ref[0] > ref[1]:
        raise RangeError(f"Reference years must lie within the available data ({available})")
    return Window(s, e, ref)


_cache: TTLCache = TTLCache(maxsize=256, ttl=get_settings().cache_ttl_seconds)
_lock = threading.Lock()


def aoi_monthly(
    con: duckdb.DuckDBPyConnection, ds: Dataset, aoi: Aoi, meta: dict[str, Any]
) -> pd.DataFrame:
    """Gap-free monthly AOI series over the full data range (cached per AOI + version)."""
    key = (ds.uri, meta.get("data_version"), aoi.key)
    with _lock:
        if key in _cache:
            return _cache[key]

    weights = Grid(float(meta["grid_res_deg"])).cell_weights(aoi.geometry)
    months = con.execute(
        f"SELECT year, month, source, has_nrt FROM {ds.months} ORDER BY year, month"
    ).df()
    cols = ["n_harmonized", "n_modis", "n_viirs", "ci_low", "ci_high"]
    if weights.empty:
        agg = pd.DataFrame(columns=["year", "month", *cols])
    else:
        con.register("aoi_cells", weights)
        lo, hi = int(weights.cell_id.min()), int(weights.cell_id.max())
        agg = con.execute(
            f"""SELECT h.year, h.month,
                       sum(h.n_harmonized * a.w) AS n_harmonized,
                       sum(h.n_modis * a.w) AS n_modis,
                       sum(h.n_viirs * a.w) AS n_viirs,
                       sum(h.ci_low * a.w) AS ci_low,
                       sum(h.ci_high * a.w) AS ci_high
                FROM {ds.harmonized} h JOIN aoi_cells a USING (cell_id)
                WHERE h.cell_id BETWEEN {lo} AND {hi}
                GROUP BY h.year, h.month"""
        ).df()
        con.unregister("aoi_cells")
    df = months.merge(agg, on=["year", "month"], how="left")
    df[cols] = df[cols].astype(float).fillna(0.0)
    df["raw"] = np.where(df.source == "MODIS", df.n_modis, df.n_viirs)
    df = df.rename(columns={"has_nrt": "provisional"})
    df.attrs["cells"] = len(weights)
    with _lock:
        _cache[key] = df
    return df


def with_anomaly(df: pd.DataFrame, reference: tuple[int, int]) -> pd.DataFrame:
    """Add per-month median of the reference years, % anomaly and percentile rank."""
    out = df.copy()
    ref = out[(out.year >= reference[0]) & (out.year <= reference[1])]
    groups = {m: g.n_harmonized.to_numpy() for m, g in ref.groupby("month")}
    median = out.month.map({m: float(np.median(v)) for m, v in groups.items()})
    out["median"] = median
    with np.errstate(divide="ignore", invalid="ignore"):
        pct = (out.n_harmonized - median) / median * 100
    out["anomaly_pct"] = pct.where(median > 0)
    out["percentile"] = [
        float((groups[m] <= v).mean() * 100) if m in groups else np.nan
        for m, v in zip(out.month, out.n_harmonized, strict=True)
    ]
    return out


def in_window(df: pd.DataFrame, start: YM, end: YM) -> pd.DataFrame:
    ym = df.year * 100 + df.month
    return df[(ym >= start[0] * 100 + start[1]) & (ym <= end[0] * 100 + end[1])]


def clean_number(value: float, digits: int = 2) -> float | None:
    return None if value is None or not np.isfinite(value) else round(float(value), digits)
