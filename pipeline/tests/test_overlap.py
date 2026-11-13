import pandas as pd
import pytest

from firecal.clean import clean
from firecal.grid import GridSpec, aggregate_monthly
from firecal.ingest import ingest
from firecal.overlap import monthly_pairs, suggest_period, yearly_ratios
from firecal.schema import publish_points
from firecal.synth import ZONE_RATIO


def _ratios(years: dict[int, float], months: int = 12) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"region": "global", "year": y, "months": months if y > 2012 else 11, "ratio": r}
            for y, r in years.items()
        ]
    )


def test_suggest_period_skips_ramp_up_drift_and_outliers() -> None:
    ratios = _ratios(
        {
            2012: 0.5,
            2013: 0.31,
            2014: 0.30,
            2015: 0.45,
            2016: 0.31,
            2017: 0.30,
            2018: 0.29,
            2019: 0.31,
            2020: 0.30,
            2021: 0.31,
            2022: 0.20,
        }  # fmt: skip
    )
    choice = suggest_period(ratios, tolerance=0.15, drift_year=2021)
    assert choice.period == "2016-01:2021-12"
    table = choice.table.set_index("year")
    assert not table.at[2012, "eligible"]  # incomplete first year
    assert not table.at[2022, "eligible"]  # orbit drift
    assert not table.at[2015, "stable"]  # outlier


def test_suggest_period_requires_overlap() -> None:
    with pytest.raises(ValueError):
        suggest_period(_ratios({2012: 0.3}), drift_year=2021)


def test_ratios_recover_synthetic_truth(paths) -> None:
    spec = GridSpec(0.25)
    ingest(paths)
    clean(paths)
    publish_points(paths, spec)
    aggregate_monthly(paths, spec)
    ratios = yearly_ratios(monthly_pairs(paths, spec))
    glob = ratios[(ratios.region == "global") & (ratios.months == 12)]
    # synthetic clusters are tropical: VIIRS/sat = 3.2 x MODIS, so MODIS/VIIRS ~ 0.31
    assert glob.ratio.median() == pytest.approx(1 / ZONE_RATIO["tropical"], rel=0.2)
    choice = suggest_period(ratios, tolerance=0.25, drift_year=2020)
    assert choice.start >= "2013-01"
    assert choice.end <= "2020-12"
