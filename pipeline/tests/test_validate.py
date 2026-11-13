import json

import pytest

from firecal.clean import clean
from firecal.grid import GridSpec, aggregate_monthly
from firecal.harmonize import HarmonizeConfig, calibrate
from firecal.ingest import ingest
from firecal.schema import publish_points
from firecal.validate import validate

SPEC = GridSpec(0.25)
CFG = HarmonizeConfig((2013, 1), (2020, 12), test_years=(2016, 2019))


@pytest.fixture
def calibrated(paths):
    ingest(paths)
    clean(paths)
    publish_points(paths, SPEC)
    aggregate_monthly(paths, SPEC)
    calibrate(paths, SPEC, CFG)
    return paths


def test_validation_report_meets_targets_on_synthetic_data(calibrated) -> None:
    report = validate(calibrated, SPEC, CFG)
    glob = report["global"]
    assert glob["after"]["months"] == 24
    assert glob["after"]["r"] >= 0.9
    assert abs(glob["after"]["bias"]) <= 0.10
    # raw VIIRS overcounts ~3x; harmonization removes that bias
    assert glob["before"]["bias"] > 1.0
    assert glob["after"]["mae"] < glob["before"]["mae"]
    assert report["meets_target_global"] is True

    saved = json.loads((calibrated.reports / "validation.json").read_text())
    assert saved["test_years"] == [2016, 2019]
    assert (calibrated.reports / "validation.png").stat().st_size > 10_000


def test_missing_targets_are_recorded_as_limitations(calibrated) -> None:
    import firecal.validate as v

    original = v.TARGET_R
    v.TARGET_R = 1.01  # impossible target
    try:
        report = validate(calibrated, SPEC, CFG)
    finally:
        v.TARGET_R = original
    assert report["meets_target_global"] is False
    assert any(item.startswith("global") for item in report["limitations"])


def test_validation_needs_test_years(calibrated) -> None:
    with pytest.raises(ValueError):
        validate(calibrated, SPEC, HarmonizeConfig((2013, 1), (2020, 12), test_years=()))
