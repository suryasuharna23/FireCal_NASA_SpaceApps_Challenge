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
