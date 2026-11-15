import json

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
