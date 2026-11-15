import json

import pytest

from firecal.live import atomic_json


def test_api_switches_complete_versions_through_atomic_pointer(tmp_path, monkeypatch):
    from app import db, settings

    pointer = tmp_path / "current.json"
    for name in ("one", "two"):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "meta.json").write_text(json.dumps({"data_version": name}))
    monkeypatch.setenv("DATA_URI", str(pointer))
    settings.get_settings.cache_clear()
    db._datasets.clear()
    try:
        atomic_json(pointer, {"format": "firecal-live-v1", "processed": "one"})
        assert db.get_dataset().meta()["data_version"] == "one"
        atomic_json(pointer, {"format": "firecal-live-v1", "processed": "two"})
        assert db.get_dataset().meta()["data_version"] == "two"
    finally:
        settings.get_settings.cache_clear()
        db._datasets.clear()


def test_missing_key_is_a_visible_status_without_network_or_secret_values(tmp_path):
    from app.live_refresh import refresh_once
    from app.settings import ApiSettings

    refresh_once(ApiSettings(firms_map_key="", live_repo_root=str(tmp_path)))
    report = json.loads((tmp_path / "data/live/status.json").read_text())
    assert report["status"] == "missing_key"
    assert "FIRMS_MAP_KEY" in report["detail"]


def test_live_api_rejects_synthetic_data_even_after_pointer_changes(tmp_path, monkeypatch):
    from app import db, settings
    from firecal.bundles import CATALOG
    from firecal.io import write_json

    write_json(tmp_path / CATALOG, {"data_version": "known-real"})
    write_json(tmp_path / "fake/meta.json", {"data_version": "synthetic"})
    atomic_json(tmp_path / "current.json", {"format": "firecal-live-v1", "processed": "fake"})
    with monkeypatch.context() as scope:
        scope.setenv("DATA_URI", str(tmp_path / "current.json"))
        scope.setenv("LIVE_AUTO_REFRESH", "true")
        scope.setenv("LIVE_REPO_ROOT", str(tmp_path))
        settings.get_settings.cache_clear()
        with pytest.raises(db.DataUnavailableError, match="Unverified dataset rejected"):
            db.get_dataset()
    settings.get_settings.cache_clear()


def test_unexpected_refresh_failure_is_persisted_and_logged_without_credentials(
    tmp_path, monkeypatch, caplog
):
    import logging

    from app.live_refresh import refresh_once
    from app.settings import ApiSettings

    def fail(*args, **kwargs):
        raise RuntimeError("must-not-leak-this-secret")

    monkeypatch.setattr("app.live_refresh.refresh", fail)
    with caplog.at_level(logging.ERROR):
        refresh_once(ApiSettings(firms_map_key="test-only", live_repo_root=str(tmp_path)))
    text = (tmp_path / "data/live/status.json").read_text()
    assert json.loads(text)["status"] == "failed"
    assert "FAILED" in caplog.text
    assert "must-not-leak-this-secret" not in text + caplog.text
