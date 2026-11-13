from pathlib import Path

import pytest

from firecal.paths import DataPaths
from firecal.synth import SynthConfig, generate

SMALL = SynthConfig(
    bbox=(100.0, -4.0, 116.0, 4.0),
    start=(2011, 1),
    end=(2020, 12),
    clusters=12,
    mean_rate=8.0,
    seed=7,
)


@pytest.fixture(scope="session")
def synthetic_raw(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A small synthetic FIRMS archive shared by all pipeline tests (read-only)."""
    raw = tmp_path_factory.mktemp("raw")
    generate(raw / "synthetic", SMALL)
    return raw


@pytest.fixture
def paths(tmp_path: Path, synthetic_raw: Path) -> DataPaths:
    """Fresh data/ tree whose raw/ folder points at the shared synthetic archive."""
    root = tmp_path / "data"
    root.mkdir()
    (root / "raw").symlink_to(synthetic_raw, target_is_directory=True)
    return DataPaths(root).ensure()
