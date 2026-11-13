"""VIIRS -> MODIS-equivalent calibration (T-11) and merged series (T-12).

Model (FR-D-09). For every cell, over the calibration months (excluding the
hold-out test years used by T-13)::

    v_norm = n_viirs / n_viirs_sats          # VIIRS count per active satellite
    k_region = sum(n_modis) / sum(v_norm)    # per biome region (global fallback)
    k_cell = (sum(n_modis) + a * k_region) / (sum(v_norm) + a)

``k_cell`` is a ratio estimator shrunk towards its region with pseudo-count ``a``
(empirical-Bayes style), so sparse cells borrow strength from their biome. Cells
with fewer than ``min_cell_viirs`` calibration detections use ``k_region``
directly; regions with too little data use the global ratio. Converted values are
``n_harmonized = k * v_norm``.

Uncertainty: ``sigma_log`` is the standard deviation of monthly log residuals
``log((m + 1) / (k * v + 1))`` within the region; the 90 % interval of a converted
value is ``n * exp(+/- 1.645 * sigma_log)`` (FR-D-11).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import duckdb
import numpy as np
import pandas as pd

from firecal.grid import GridSpec
from firecal.io import write_json
from firecal.overlap import region_of
from firecal.paths import DataPaths

log = logging.getLogger(__name__)

Z90 = 1.6448536269514722


def parse_month(value: str) -> tuple[int, int]:
    year, month = value.strip().split("-")
    return int(year), int(month)


def parse_period(value: str) -> tuple[tuple[int, int], tuple[int, int]]:
    start, end = value.split(":")
    return parse_month(start), parse_month(end)


@dataclass(frozen=True)
class HarmonizeConfig:
    calibration_start: tuple[int, int] = (2013, 1)
    calibration_end: tuple[int, int] = (2021, 12)
    test_years: tuple[int, ...] = (2016, 2019)
    min_cell_viirs: float = 50.0
    min_region_viirs: float = 500.0
    shrinkage: float = 100.0
    transition: tuple[int, int] | None = None

    @property
    def transition_month(self) -> tuple[int, int]:
        """Last month served by MODIS in the merged series (default: calibration end)."""
        return self.transition or self.calibration_end


def _ym(year: pd.Series, month: pd.Series) -> pd.Series:
    return year * 100 + month


def calibration_rows(paths: DataPaths, cfg: HarmonizeConfig) -> pd.DataFrame:
    start = cfg.calibration_start[0] * 100 + cfg.calibration_start[1]
    end = cfg.calibration_end[0] * 100 + cfg.calibration_end[1]
    tests = ", ".join(map(str, cfg.test_years)) or "NULL"
    return (
        duckdb.connect()
        .execute(
            f"""SELECT cell_id, year, month, n_modis,
                   n_viirs / n_viirs_sats::DOUBLE AS v_norm
            FROM read_parquet('{paths.grid_monthly.as_posix()}')
            WHERE n_viirs_sats > 0
              AND year * 100 + month BETWEEN {start} AND {end}
              AND year NOT IN ({tests})"""
        )
        .df()
    )


def _loglog(group: pd.DataFrame) -> dict[str, float]:
    """Diagnostic log-log OLS fit of monthly regional totals."""
    import statsmodels.api as sm

    monthly = group.groupby(["year", "month"])[["n_modis", "v_norm"]].sum()
    if len(monthly) < 6:
        return {}
    x = sm.add_constant(np.log1p(monthly["v_norm"].to_numpy()))
    fit = sm.OLS(np.log1p(monthly["n_modis"].to_numpy()), x).fit()
    return {
        "loglog_intercept": float(fit.params[0]),
        "loglog_slope": float(fit.params[1]),
        "loglog_r2": float(fit.rsquared),
    }


def calibrate(paths: DataPaths, grid: GridSpec, cfg: HarmonizeConfig) -> pd.DataFrame:
    """Fit per-cell coefficients and write ``coefficients.parquet``."""
    cal = calibration_rows(paths, cfg)
    if cal.empty:
        raise ValueError("No MODIS-VIIRS overlap months inside the calibration period")
    cal["region"] = region_of(paths, grid, cal["cell_id"].to_numpy())

    k_global = cal["n_modis"].sum() / cal["v_norm"].sum()
    regions = cal.groupby("region").agg(s_m=("n_modis", "sum"), s_v=("v_norm", "sum"))
    regions["k_region"] = np.where(
        regions.s_v >= cfg.min_region_viirs, regions.s_m / regions.s_v, k_global
    )
    regions["region_method"] = np.where(regions.s_v >= cfg.min_region_viirs, "region", "global")

    cells = cal.groupby("cell_id").agg(
        region=("region", "first"),
        n_cal_modis=("n_modis", "sum"),
        n_cal_viirs=("v_norm", "sum"),
        cal_months=("month", "size"),
    )
    # Every cell that ever had a detection gets a coefficient.
    all_ids = (
        duckdb.connect()
        .execute(
            f"SELECT DISTINCT cell_id FROM read_parquet('{paths.grid_monthly.as_posix()}') "
            "ORDER BY cell_id"
        )
        .df()["cell_id"]
        .to_numpy()
    )
    coef = pd.DataFrame({"cell_id": all_ids}).merge(cells.reset_index(), on="cell_id", how="left")
    missing = coef["region"].isna()
    coef.loc[missing, "region"] = region_of(paths, grid, coef.loc[missing, "cell_id"].to_numpy())
    coef[["n_cal_modis", "n_cal_viirs", "cal_months"]] = coef[
        ["n_cal_modis", "n_cal_viirs", "cal_months"]
    ].fillna(0)

    coef = coef.merge(regions[["k_region", "region_method"]], left_on="region",
                      right_index=True, how="left")  # fmt: skip
    coef["k_region"] = coef["k_region"].fillna(k_global)
    coef["region_method"] = coef["region_method"].fillna("global")
    enough = coef["n_cal_viirs"] >= cfg.min_cell_viirs
    shrunk = (coef["n_cal_modis"] + cfg.shrinkage * coef["k_region"]) / (
        coef["n_cal_viirs"] + cfg.shrinkage
    )
    coef["k"] = np.where(enough, shrunk, coef["k_region"])
    coef["method"] = np.where(enough, "cell", coef["region_method"])

    # Regional log-residual spread for uncertainty intervals.
    resid = cal.merge(coef[["cell_id", "k"]], on="cell_id")
    resid["r"] = np.log((resid["n_modis"] + 1) / (resid["k"] * resid["v_norm"] + 1))
    sigma_global = float(resid["r"].std(ddof=1))
    sigma = resid.groupby("region")["r"].agg(lambda r: r.std(ddof=1) if len(r) >= 30 else np.nan)
    coef["sigma_log"] = coef["region"].map(sigma).fillna(sigma_global)

    coef = coef[
        ["cell_id", "region", "k", "k_region", "sigma_log", "method",
         "n_cal_modis", "n_cal_viirs", "cal_months"]
    ].sort_values("cell_id", ignore_index=True)  # fmt: skip
    coef["cal_months"] = coef["cal_months"].astype("int32")
    coef.to_parquet(paths.coefficients, index=False)

    report = {
        "calibration_period": f"{cfg.calibration_start[0]}-{cfg.calibration_start[1]:02d}:"
        f"{cfg.calibration_end[0]}-{cfg.calibration_end[1]:02d}",
        "test_years_excluded": list(cfg.test_years),
        "k_global": float(k_global),
        "sigma_log_global": sigma_global,
        "cells": int(len(coef)),
        "methods": coef["method"].value_counts().to_dict(),
        "regions": {
            name: {
                "k_region": float(row.k_region),
                "method": row.region_method,
                "modis": float(row.s_m),
                "viirs_per_sat": float(row.s_v),
                "sigma_log": float(sigma.get(name, sigma_global)),
                **_loglog(cal[cal.region == name]),
            }
            for name, row in regions.iterrows()
        },
    }
    write_json(paths.reports / "calibration.json", report)
    log.info("Calibrated %d cells: %s", len(coef), report["methods"])
    return coef


def _months_between(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    out, (y, m) = [], start
    while (y, m) <= end:
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def merge_series(paths: DataPaths, grid: GridSpec, cfg: HarmonizeConfig) -> dict[str, object]:
    """Build the harmonized cube and the month index (T-12, FR-D-10/11/13).

    ``harmonized.parquet`` (sparse, sorted by cell)::

        cell_id, year, month, n_modis, n_viirs, n_viirs_sats,
        n_harmonized, ci_low, ci_high, source, has_nrt

    Months up to the transition (and every month before VIIRS existed) take the
    observed MODIS count; later months take ``k * v_norm`` with a 90 % interval.
    ``months.parquet`` lists every month between the first and last data month
    (no gaps) with its source and NRT flag, so consumers can zero-fill.
    """
    import hashlib
    from datetime import UTC, datetime

    from firecal.io import read_json

    if not paths.coefficients.exists():
        raise FileNotFoundError("coefficients.parquet missing; run calibration first")
    k_global = read_json(paths.reports / "calibration.json").get("k_global")
    con = duckdb.connect()
    con.execute(
        f"CREATE TEMP VIEW coef AS SELECT * FROM read_parquet('{paths.coefficients.as_posix()}')"
    )
    if k_global is None:
        k_global = con.execute("SELECT median(k) FROM coef").fetchone()[0]
    sigma_global = con.execute("SELECT median(sigma_log) FROM coef").fetchone()[0]
    ty, tm = cfg.transition_month
    transition = ty * 100 + tm
    con.execute(
        f"""COPY (
            WITH g AS (
                SELECT g.*, coalesce(c.k, {k_global}) AS k,
                       coalesce(c.sigma_log, {sigma_global}) AS sigma_log,
                       (g.year * 100 + g.month <= {transition} OR g.n_viirs_sats = 0)
                           AS use_modis
                FROM read_parquet('{paths.grid_monthly.as_posix()}') g
                LEFT JOIN coef c USING (cell_id)
            ), h AS (
                SELECT *, CASE WHEN use_modis THEN n_modis::DOUBLE
                               ELSE k * n_viirs / n_viirs_sats END AS n_h
                FROM g
            )
            SELECT cell_id, year, month, n_modis, n_viirs, n_viirs_sats,
                   n_h AS n_harmonized,
                   CASE WHEN use_modis THEN n_h ELSE n_h * exp(-{Z90} * sigma_log) END AS ci_low,
                   CASE WHEN use_modis THEN n_h ELSE n_h * exp({Z90} * sigma_log) END AS ci_high,
                   CASE WHEN use_modis THEN 'MODIS' ELSE 'VIIRS' END AS source,
                   has_nrt
            FROM h
            ORDER BY cell_id, year, month
        ) TO '{paths.harmonized.as_posix()}' (FORMAT parquet, COMPRESSION zstd,
                                              ROW_GROUP_SIZE 122880)"""
    )

    monthly = con.execute(
        f"""SELECT year, month, max(n_viirs_sats) AS n_viirs_sats, bool_or(has_nrt) AS has_nrt,
                   sum(n_harmonized) AS total
            FROM read_parquet('{paths.harmonized.as_posix()}') GROUP BY year, month"""
    ).df()
    first = (int(monthly.year.min()), int(monthly.month[monthly.year == monthly.year.min()].min()))
    last_year = int(monthly.year.max())
    last = (last_year, int(monthly.month[monthly.year == last_year].max()))
    index = pd.DataFrame(_months_between(first, last), columns=["year", "month"])
    index = index.merge(monthly, on=["year", "month"], how="left")
    index["n_viirs_sats"] = index["n_viirs_sats"].fillna(0).astype("int8")
    index["has_nrt"] = index["has_nrt"].astype("boolean").fillna(False).astype(bool)
    index["total"] = index["total"].fillna(0.0)
    ym = index.year * 100 + index.month
    index["source"] = np.where((ym <= transition) | (index.n_viirs_sats == 0), "MODIS", "VIIRS")
    index.to_parquet(paths.processed / "months.parquet", index=False)

    pts = paths.points / "**" / "*.parquet"
    last_acq, nrt_since = con.execute(
        f"""SELECT max(acq_date), min(acq_date) FILTER (WHERE source = 'NRT')
            FROM read_parquet('{pts.as_posix()}', hive_partitioning = true)"""
    ).fetchone()
    digest = hashlib.sha256()
    for path in (paths.coefficients, paths.grid_monthly):
        digest.update(path.read_bytes())
    meta = {
        "data_version": digest.hexdigest()[:12],
        "processed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "grid_res_deg": grid.res,
        "calibration_period": read_json(paths.reports / "calibration.json").get(
            "calibration_period"
        ),
        "test_years": list(cfg.test_years),
        "transition_month": f"{ty}-{tm:02d}",
        "start_month": f"{first[0]}-{first[1]:02d}",
        "end_month": f"{last[0]}-{last[1]:02d}",
        "months": len(index),
        "last_acq_date": str(last_acq) if last_acq else None,
        "nrt_since": str(nrt_since) if nrt_since else None,
        "k_global": float(k_global),
        "sources": "NASA FIRMS MODIS C6.1 (Terra, Aqua) and VIIRS 375 m (S-NPP, NOAA-20, NOAA-21)",
    }
    write_json(paths.meta, meta)
    log.info("Harmonized %s .. %s (%d months), version %s",
             meta["start_month"], meta["end_month"], len(index), meta["data_version"])  # fmt: skip
    return meta
