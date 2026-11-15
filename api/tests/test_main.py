import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def empty_client(tmp_path, monkeypatch):
    """App pointed at a folder without processed data."""
    from app import db, settings
    from app.main import create_app

    monkeypatch.setenv("DATA_URI", str(tmp_path))
    settings.get_settings.cache_clear()
    db._datasets.clear()
    yield TestClient(create_app())
    settings.get_settings.cache_clear()
    db._datasets.clear()


def test_health(empty_client) -> None:
    response = empty_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_meta_without_real_data_fails_loudly(empty_client) -> None:
    response = empty_client.get("/meta")
    assert response.status_code == 503
    assert "Processed data not found" in response.json()["detail"]


def test_data_endpoints_without_data_return_503(empty_client) -> None:
    aoi = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
    assert empty_client.post("/calendar", json={"aoi": aoi}).status_code == 503
