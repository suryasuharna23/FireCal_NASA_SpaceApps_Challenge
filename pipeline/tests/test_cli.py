from typer.testing import CliRunner

from firecal import __version__
from firecal.cli import app
from firecal.config import PipelineSettings

runner = CliRunner()


def test_version_command_prints_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_settings_parse_bbox_and_confidence() -> None:
    settings = PipelineSettings(coverage_bbox="95,-11,141,6", viirs_confidence="nominal, high")
    assert settings.bbox == (95.0, -11.0, 141.0, 6.0)
    assert settings.viirs_confidence_levels == ["nominal", "high"]


def test_full_pipeline_via_cli(paths, monkeypatch) -> None:
    import json

    from firecal.config import get_settings

    monkeypatch.setenv("DATA_ROOT", str(paths.root))
    monkeypatch.setenv("CALIBRATION_PERIOD", "2013-01:2020-12")
    monkeypatch.setenv("TEST_YEARS", "2016,2019")
    get_settings.cache_clear()
    try:
        result = runner.invoke(app, ["run"])
    finally:
        get_settings.cache_clear()
    assert result.exit_code == 0, result.output
    assert "global" in result.stdout
    meta = json.loads(paths.meta.read_text())
    assert meta["end_month"] == "2020-12"
    assert (paths.reports / "validation.png").exists()
