import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_meta_includes_firms_attribution() -> None:
    response = client.get("/meta")
    assert response.status_code == 200
    assert "NASA FIRMS" in response.json()["attribution"]


@pytest.mark.parametrize("path", ["/calendar", "/stats", "/points", "/export", "/globe"])
def test_planned_endpoints_return_501(path: str) -> None:
    assert client.get(path).status_code == 501
