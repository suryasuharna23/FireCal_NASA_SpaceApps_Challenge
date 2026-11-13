"""Build a small processed cube with the real pipeline once per test session."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from firecal.clean import clean
from firecal.grid import GridSpec, aggregate_monthly
from firecal.harmonize import HarmonizeConfig, calibrate, merge_series
from firecal.ingest import ingest
from firecal.paths import DataPaths
from firecal.schema import publish_points
from firecal.synth import SynthConfig, generate

SPEC = GridSpec(0.25)
BBOX = (100.0, -4.0, 116.0, 4.0)


def make_box(west: float, south: float, east: float, north: float) -> dict:
    ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
    return {"type": "Polygon", "coordinates": [ring]}


@pytest.fixture(scope="session")
def box():
    """GeoJSON polygon factory: box(west, south, east, north)."""
    return make_box


@pytest.fixture(scope="session")
def data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    paths = DataPaths(tmp_path_factory.mktemp("data")).ensure()
    generate(
        paths.raw / "synthetic",
        SynthConfig(bbox=BBOX, start=(2011, 1), end=(2020, 12), clusters=12, seed=7),
    )
    cfg = HarmonizeConfig((2013, 1), (2018, 12), test_years=(2016,))
    ingest(paths)
    clean(paths)
    publish_points(paths, SPEC)
    aggregate_monthly(paths, SPEC)
    calibrate(paths, SPEC, cfg)
    merge_series(paths, SPEC, cfg)
    return paths.processed


@pytest.fixture(scope="session")
def client(data_dir: Path) -> TestClient:
    mp = pytest.MonkeyPatch()
    mp.setenv("DATA_URI", str(data_dir))
    mp.setenv("REFERENCE_YEARS", "2011:2020")
    from app import db, settings

    settings.get_settings.cache_clear()
    db._datasets.clear()
    from app.main import create_app

    yield TestClient(create_app())
    mp.undo()
    settings.get_settings.cache_clear()
    db._datasets.clear()
