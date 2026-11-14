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


def test_standard_processing_sources_are_supported():
    with _client(lambda r: httpx.Response(200, text="latitude,longitude\n1,2\n")) as client:
        assert client.area_csv("MODIS_SP", (95, -11, 141, 6), 5, "2015-09-01")


def test_availability_is_parsed_without_returning_credential_urls():
    def handler(request):
        assert request.url.path.endswith(f"/{KEY}/ALL")
        return httpx.Response(
            200, text="data_id,min_date,max_date\nMODIS_SP,2000-11-01,2026-06-30\n"
        )

    with _client(handler) as client:
        rows = client.availability()
    assert rows == [{"data_id": "MODIS_SP", "min_date": "2000-11-01", "max_date": "2026-06-30"}]
    assert KEY not in str(rows)


def test_http_request_logs_redact_credentials(caplog):
    import logging

    with (
        _client(lambda r: httpx.Response(200, text="latitude,longitude\n")) as client,
        caplog.at_level(logging.INFO, logger="httpx"),
    ):
        client.area_csv("MODIS_SP", (95, -11, 141, 6), 1)
    assert KEY not in caplog.text
    assert "[REDACTED]" in caplog.text


def test_provider_error_cannot_echo_credentials():
    with (
        _client(lambda r: httpx.Response(403, text=f"Denied key {KEY}")) as client,
        pytest.raises(FirmsError) as exc,
    ):
        client.area_csv("MODIS_SP", (95, -11, 141, 6), 1)
    assert KEY not in str(exc.value)


def test_connection_errors_do_not_expose_url_or_key(monkeypatch):
    import firecal.firms as module

    monkeypatch.setattr(module.time, "sleep", lambda _: None)

    def handler(request):
        raise httpx.ConnectTimeout(f"failed {request.url}", request=request)

    with _client(handler) as client, pytest.raises(FirmsError) as exc:
        client.key_status()
    assert KEY not in str(exc.value)
    assert "after retries" in str(exc.value)


def test_mirror_rejection_does_not_override_a_valid_primary_key(monkeypatch):
    import firecal.firms as module

    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    primary_calls = 0

    def handler(request):
        nonlocal primary_calls
        if request.url.host == "firms2.modaps.eosdis.nasa.gov":
            return httpx.Response(401, text="Invalid MAP_KEY")
        primary_calls += 1
        if primary_calls == 1:
            raise httpx.ConnectTimeout("transient", request=request)
        return httpx.Response(
            200,
            json={
                "transaction_limit": 5000,
                "current_transactions": 0,
                "transaction_interval": "10 minutes",
            },
        )

    with _client(handler) as client:
        assert client.key_status().remaining == 5000
