"""MODIS-VIIRS overlap analysis and calibration-period selection (T-10, FR-D-09).

The calibration period must be a stretch of the overlap where the VIIRS/MODIS
relationship is stable. Two known effects make some years unsuitable:

* **S-NPP ramp-up** — VIIRS 375 m data start in January 2012; the first year is
  incomplete and processing was still settling, so calibration starts with the
  first full year after the VIIRS start year.
* **Terra/Aqua orbit drift** — Terra (from 2020) and Aqua (from 2021-2022) stopped
  inclination-control manoeuvres, and their equator crossing times drift later,
  which changes the diurnal sampling of fires. Years after ``drift_year`` are
  therefore excluded by default.

Within those bounds :func:`suggest_period` keeps the longest contiguous run of
years whose global VIIRS-per-satellite / MODIS ratio stays within ``tolerance`` of
the median, so a single anomalous year cannot bias the coefficients.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb
import numpy as np
import pandas as pd

from firecal.grid import GridSpec, latitude_zone
from firecal.paths import DataPaths


def monthly_pairs(paths: DataPaths, grid: GridSpec) -> pd.DataFrame:
    """Per region and month: MODIS count and VIIRS count per active satellite.

    Regions are biome classes from ``cells.parquet`` when available, otherwise
    latitude zones. Only months with VIIRS data are returned.
    """
    con = duckdb.connect()
    df = con.execute(
        f"""SELECT cell_id, year, month, n_modis,
                   n_viirs / n_viirs_sats::DOUBLE AS v_norm
            FROM read_parquet('{paths.grid_monthly.as_posix()}')
            WHERE n_viirs_sats > 0"""
    ).df()
    df["region"] = region_of(paths, grid, df["cell_id"].to_numpy())
    return (
        df.groupby(["region", "year", "month"], as_index=False)[["n_modis", "v_norm"]]
        .sum()
        .sort_values(["region", "year", "month"], ignore_index=True)
    )


def region_of(paths: DataPaths, grid: GridSpec, cell_ids: np.ndarray) -> np.ndarray:
    _, lat = grid.centers(cell_ids)
    region = latitude_zone(lat).astype(object)
    if paths.cells.exists():
        cells = pd.read_parquet(paths.cells, columns=["cell_id", "biome"]).set_index("cell_id")
        known = pd.Series(cell_ids).map(cells["biome"])
        region = np.where(known.notna(), known, region)
    return region


def yearly_ratios(pairs: pd.DataFrame) -> pd.DataFrame:
    """Ratio MODIS / (VIIRS per satellite) per region and year, plus a global row."""
    glob = pairs.groupby(["year", "month"], as_index=False)[["n_modis", "v_norm"]].sum()
    glob["region"] = "global"
    allp = pd.concat([pairs, glob], ignore_index=True)
    out = allp.groupby(["region", "year"]).agg(
        months=("month", "nunique"), n_modis=("n_modis", "sum"), v_norm=("v_norm", "sum")
    )
    out["ratio"] = out["n_modis"] / out["v_norm"].where(out["v_norm"] > 0)
    return out.reset_index()


@dataclass(frozen=True)
class PeriodChoice:
    start: str
    end: str
    median_ratio: float
    table: pd.DataFrame

    @property
    def period(self) -> str:
        return f"{self.start}:{self.end}"


def suggest_period(
    ratios: pd.DataFrame, tolerance: float = 0.15, drift_year: int = 2021
) -> PeriodChoice:
    """Longest contiguous run of stable full years in the overlap (see module doc)."""
    table = ratios[ratios.region == "global"].set_index("year").sort_index().copy()
    # The first VIIRS year (2012) is a ramp-up year even when all 12 months exist.
    eligible = (
        (table.months == 12) & (table.index > table.index.min()) & (table.index <= drift_year)
    )
    full = table[eligible]
    if full.empty:
        raise ValueError("No full year of MODIS-VIIRS overlap before the drift year")
    median = float(full["ratio"].median())
    table["eligible"] = eligible
    table["deviation"] = table["ratio"] / median - 1
    table["stable"] = table["eligible"] & (table["deviation"].abs() <= tolerance)

    best: tuple[int, int] | None = None
    run_start = None
    years = list(table.index)
    for i, year in enumerate(years):
        if table.at[year, "stable"]:
            run_start = year if run_start is None else run_start
            is_last = i == len(years) - 1 or not table.at[years[i + 1], "stable"]
            if is_last and (best is None or year - run_start > best[1] - best[0]):
                best = (run_start, year)
        else:
            run_start = None
    if best is None:
        raise ValueError("No stable year within tolerance; widen the tolerance")
    return PeriodChoice(f"{best[0]}-01", f"{best[1]}-12", median, table.reset_index())
