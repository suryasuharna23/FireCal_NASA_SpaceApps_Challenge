import httpx
import pytest
from typer.testing import CliRunner

from firecal.cli import app
from firecal.firms import FirmsClient, FirmsError, mask_key

KEY = "abcdef0123456789abcdef0123456789"


def _client(handler) -> FirmsClient:
    return FirmsClient(KEY, transport=httpx.MockTransport(handler))


def test_key_status_parses_quota() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/mapserver/mapkey_status/"
        assert request.url.params["MAP_KEY"] == KEY
        return httpx.Response(
            200,
            json={
                "transaction_limit": 5000,
                "current_transactions": 12,
                "transaction_interval": "10 minutes",
            },
        )

    status = _client(handler).key_status()
    assert status.remaining == 4988


def test_invalid_key_raises_without_leaking_key() -> None:
    client = _client(lambda r: httpx.Response(200, text="Invalid MAP_KEY."))
    with pytest.raises(FirmsError) as exc:
        client.key_status()
    assert KEY not in str(exc.value)


def test_missing_key_is_rejected() -> None:
    with pytest.raises(FirmsError):
        FirmsClient("")


def test_area_csv_builds_url_and_validates_range() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, text="latitude,longitude\n1,2\n")

    client = _client(handler)
    assert client.area_csv("VIIRS_SNPP_NRT", (95, -11, 141, 6), 2).startswith("latitude")
    assert seen == [f"/api/area/csv/{KEY}/VIIRS_SNPP_NRT/95,-11,141,6/2"]
    with pytest.raises(FirmsError):
        client.area_csv("VIIRS_SNPP_NRT", (95, -11, 141, 6), 6)


def test_mask_key() -> None:
    assert mask_key(KEY) == "abcd…89"
    assert mask_key("short") == "***"


def test_check_key_command_fails_without_key(monkeypatch) -> None:
    monkeypatch.setenv("FIRMS_MAP_KEY", "")
    from firecal.config import get_settings

    get_settings.cache_clear()
    result = CliRunner().invoke(app, ["check-key"])
    assert result.exit_code == 1
    get_settings.cache_clear()
