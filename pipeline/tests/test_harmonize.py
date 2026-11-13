import json

import duckdb
import pandas as pd
import pytest

from firecal.clean import clean
from firecal.grid import GridSpec, aggregate_monthly
from firecal.harmonize import HarmonizeConfig, calibrate, parse_period
from firecal.ingest import ingest
from firecal.schema import publish_points
from firecal.synth import ZONE_RATIO

SPEC = GridSpec(0.25)
CFG = HarmonizeConfig(calibration_start=(2013, 1), calibration_end=(2018, 12), test_years=(2016,))


@pytest.fixture
def gridded(paths):
    ingest(paths)
    clean(paths)
    publish_points(paths, SPEC)
    aggregate_monthly(paths, SPEC)
    return paths


def test_parse_period() -> None:
    assert parse_period("2013-01:2021-12") == ((2013, 1), (2021, 12))


def test_every_cell_gets_a_coefficient(gridded) -> None:
    coef = calibrate(gridded, SPEC, CFG)
    cells = duckdb.sql(
        f"SELECT DISTINCT cell_id FROM read_parquet('{gridded.grid_monthly.as_posix()}')"
    ).df()
    assert set(coef.cell_id) == set(cells.cell_id)
    assert coef.k.gt(0).all() and coef.sigma_log.gt(0).all()
    assert pd.read_parquet(gridded.coefficients).equals(coef)


def test_sparse_cells_fall_back_to_region(gridded) -> None:
    coef = calibrate(gridded, SPEC, CFG)
    sparse = coef[coef.n_cal_viirs < CFG.min_cell_viirs]
    dense = coef[coef.n_cal_viirs >= CFG.min_cell_viirs]
    assert len(sparse) and len(dense)
    assert set(sparse.method) <= {"region", "global"}
    assert (sparse.k == sparse.k_region).all()
    assert set(dense.method) == {"cell"}


def test_coefficients_recover_synthetic_ratio(gridded) -> None:
    coef = calibrate(gridded, SPEC, CFG)
    report = json.loads((gridded.reports / "calibration.json").read_text())
    truth = 1 / ZONE_RATIO["tropical"]
    assert report["k_global"] == pytest.approx(truth, rel=0.15)
    assert report["test_years_excluded"] == [2016]
    dense = coef[coef.method == "cell"]
    assert dense.k.median() == pytest.approx(truth, rel=0.2)


def test_calibration_period_without_overlap_fails(gridded) -> None:
    with pytest.raises(ValueError):
        calibrate(gridded, SPEC, HarmonizeConfig((2003, 1), (2008, 12), ()))


def test_merged_series_switches_source_at_transition(gridded) -> None:
    from firecal.harmonize import merge_series

    calibrate(gridded, SPEC, CFG)
    meta = merge_series(gridded, SPEC, CFG)
    h = pd.read_parquet(gridded.harmonized)
    coef = pd.read_parquet(gridded.coefficients).set_index("cell_id")

    assert {"n_harmonized", "ci_low", "ci_high", "source"} <= set(h.columns)
    ym = h.year * 100 + h.month
    before, after = h[ym <= 201812], h[ym > 201812]
    assert set(before.source) == {"MODIS"} and set(after.source) == {"VIIRS"}
    assert (before.n_harmonized == before.n_modis).all()
    assert (before.ci_low == before.ci_high).all()

    row = after[after.n_viirs > 0].iloc[0]
    k = coef.at[row.cell_id, "k"]
    assert row.n_harmonized == pytest.approx(k * row.n_viirs / row.n_viirs_sats)
    assert row.ci_low < row.n_harmonized < row.ci_high

    months = pd.read_parquet(gridded.processed / "months.parquet")
    assert len(months) == meta["months"] == 120  # no gap months
    assert meta["start_month"] == "2011-01" and meta["end_month"] == "2020-12"
    assert meta["transition_month"] == "2018-12"
    assert json.loads(gridded.meta.read_text())["data_version"] == meta["data_version"]


def test_harmonized_total_is_continuous_across_transition(gridded) -> None:
    """The synthetic truth has no jump at the switch; the merged series must not either."""
    from firecal.harmonize import merge_series

    calibrate(gridded, SPEC, CFG)
    merge_series(gridded, SPEC, CFG)
    h = pd.read_parquet(gridded.harmonized)
    yearly = h.groupby("year")[["n_harmonized", "n_viirs", "n_modis"]].sum()
    before = yearly.loc[2017:2018, "n_harmonized"].mean()
    after = yearly.loc[2019:2020, "n_harmonized"].mean()
    raw_after = yearly.loc[2019:2020, "n_viirs"].mean()
    assert abs(after / before - 1) < abs(raw_after / before - 1)


def test_viirs_point_weights_sum_to_harmonized(gridded) -> None:
    from firecal.harmonize import merge_series
    from firecal.schema import read_sql

    calibrate(gridded, SPEC, CFG)
    merge_series(gridded, SPEC, CFG)
    con = duckdb.connect()
    pts = con.sql(f"SELECT * FROM {read_sql(gridded.points)}").df()
    assert pts.weight.notna().all()
    assert (pts.loc[pts.sensor == "MODIS", "weight"] == 1).all()

    viirs = pts[pts.sensor == "VIIRS"]
    sums = viirs[viirs.in_series].groupby(["cell_id", "year", "month"]).weight.sum()
    h = pd.read_parquet(gridded.harmonized).set_index(["cell_id", "year", "month"])
    joined = h.loc[sums.index, "n_harmonized"]
    assert len(sums) > 100
    assert (sums - joined).abs().max() < 1e-9

    # every point: in-series weights reproduce the merged series per cell-month
    total = pts[pts.in_series].groupby(["cell_id", "year", "month"]).weight.sum()
    assert (total - h.loc[total.index, "n_harmonized"]).abs().max() < 1e-9
