"""Thin HTTP client for the NASA FIRMS API.

The MAP_KEY is only ever read from the environment (``FIRMS_MAP_KEY``) and is never
logged in clear text (NFR-08).
"""

from __future__ import annotations

import csv
import io
import logging
import time
from dataclasses import dataclass

import httpx

#: FIRMS area API source names for near-real-time products (FR-D-03).
NRT_SOURCES: dict[str, str] = {
    "MODIS_NRT": "MODIS",
    "VIIRS_SNPP_NRT": "VIIRS",
    "VIIRS_NOAA20_NRT": "VIIRS",
    "VIIRS_NOAA21_NRT": "VIIRS",
}
SP_SOURCES: dict[str, str] = {
    "MODIS_SP": "MODIS",
    "VIIRS_SNPP_SP": "VIIRS",
    "VIIRS_NOAA20_SP": "VIIRS",
    "VIIRS_NOAA21_SP": "VIIRS",
}
SOURCES = {**NRT_SOURCES, **SP_SOURCES}

#: Maximum day range accepted by the FIRMS area API.
MAX_DAY_RANGE = 5


class FirmsError(RuntimeError):
    """Raised when FIRMS returns an error or an unexpected payload."""


class FirmsAuthError(FirmsError):
    """NASA rejected the provided credential; retry only after it is corrected."""


class FirmsQuotaError(FirmsError):
    """NASA's transaction budget is exhausted; wait for the quota window."""


class _RedactKey(logging.Filter):
    def __init__(self, key: str) -> None:
        super().__init__()
        self.key = key

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = record.getMessage().replace(self.key, "[REDACTED]")
        record.args = ()
        return True


@dataclass(frozen=True)
class KeyStatus:
    transaction_limit: int
    current_transactions: int
    transaction_interval: str

    @property
    def remaining(self) -> int:
        return self.transaction_limit - self.current_transactions


def mask_key(key: str) -> str:
    """Return a log-safe representation of a MAP_KEY."""
    return f"{key[:4]}…{key[-2:]}" if len(key) > 8 else "***"


class FirmsClient:
    def __init__(
        self,
        map_key: str,
        api_base: str = "https://firms.modaps.eosdis.nasa.gov/api",
        *,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
        allow_mirror: bool = True,
    ) -> None:
        if not map_key:
            raise FirmsError("FIRMS_MAP_KEY is not set; copy .env.example to .env and fill it in.")
        self._key = map_key
        self._api_base = api_base.rstrip("/")
        # The key-status endpoint lives under /mapserver, a sibling of /api.
        self._root = self._api_base.rsplit("/api", 1)[0]
        self._http = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=min(timeout, 12.0)),
            transport=transport,
            follow_redirects=True,
            headers={"User-Agent": "FireCal/0.1 (NASA FIRMS research)"},
            limits=httpx.Limits(keepalive_expiry=120.0),
        )
        self._allow_mirror = allow_mirror
        self._preferred_host = 0
        self._redactor = _RedactKey(map_key)
        logging.getLogger("httpx").addFilter(self._redactor)
        # httpcore debug traces can contain request paths, including credentials.
        logging.getLogger("httpcore").setLevel(logging.WARNING)

    def _get(self, path: str, *, root: bool = False, params=None) -> httpx.Response:
        """Retry transient NASA failures without including credential-bearing URLs in errors."""
        bases = [self._root if root else self._api_base]
        if self._allow_mirror and "firms.modaps.eosdis.nasa.gov" in bases[0]:
            bases.append(bases[0].replace("firms.modaps.", "firms2.modaps."))
        last = "request error"
        denied = {}
        for attempt in range(6):
            host_index = (self._preferred_host + attempt) % len(bases)
            base = bases[host_index]
            try:
                response = self._http.get(base + path, params=params)
                if response.status_code in (401, 403) and len(bases) > 1:
                    denied[base] = response
                    if len(denied) == len(bases):
                        return response
                    last = "one NASA host rejected the key while the other was unavailable"
                elif response.status_code < 500:
                    if response.status_code == 200:
                        self._preferred_host = host_index
                    return response
                last = f"HTTP {response.status_code}"
            except httpx.RequestError as exc:
                last = type(exc).__name__
            if attempt < 5:
                time.sleep(min(2**attempt, 8))
        raise FirmsError(f"FIRMS request failed after retries ({last})") from None

    def _safe(self, text: str) -> str:
        return text.replace(self._key, "[REDACTED]")[:200]

    def __enter__(self) -> FirmsClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()
        logging.getLogger("httpx").removeFilter(self._redactor)

    def key_status(self) -> KeyStatus:
        """Validate the MAP_KEY and return its transaction quota."""
        response = self._get("/mapserver/mapkey_status/", root=True, params={"MAP_KEY": self._key})
        if response.status_code in (401, 403):
            raise FirmsAuthError(f"FIRMS key status rejected (HTTP {response.status_code})")
        if response.status_code != 200:
            raise FirmsError(f"FIRMS key status failed with HTTP {response.status_code}")
        try:
            payload = response.json()
            return KeyStatus(
                transaction_limit=int(payload["transaction_limit"]),
                current_transactions=int(payload["current_transactions"]),
                transaction_interval=str(payload["transaction_interval"]),
            )
        except (ValueError, KeyError) as exc:
            raise FirmsError(f"Invalid MAP_KEY: {self._safe(response.text)}") from exc

    def availability(self) -> list[dict[str, str]]:
        """Return current NASA source/date availability; never persist the credential URL."""
        response = self._get(f"/data_availability/csv/{self._key}/ALL")
        if response.status_code in (401, 403):
            raise FirmsAuthError(f"FIRMS availability rejected (HTTP {response.status_code})")
        if response.status_code != 200:
            raise FirmsError(f"FIRMS availability failed (HTTP {response.status_code})")
        if self._key in response.text:
            raise FirmsError("FIRMS availability response reflected a credential")
        reader = csv.DictReader(io.StringIO(response.text))
        if not {"data_id", "min_date", "max_date"}.issubset(reader.fieldnames or []):
            raise FirmsError(f"Unexpected availability response: {self._safe(response.text)}")
        return list(reader)

    def area_csv(
        self,
        source: str,
        bbox: tuple[float, float, float, float],
        days: int,
        date: str | None = None,
    ) -> str:
        """Download detections for ``bbox`` (west, south, east, north) as CSV text."""
        if source not in SOURCES:
            raise FirmsError(f"Unknown FIRMS source {source!r}")
        if not 1 <= days <= MAX_DAY_RANGE:
            raise FirmsError(f"days must be between 1 and {MAX_DAY_RANGE}")
        area = ",".join(f"{v:g}" for v in bbox)
        path = f"/area/csv/{self._key}/{source}/{area}/{days}"
        if date:
            path += f"/{date}"
        response = self._get(path)
        text = response.text
        if response.status_code in (401, 403) or "invalid map_key" in text.lower():
            raise FirmsAuthError(
                f"FIRMS {source} rejected the MAP_KEY (HTTP {response.status_code})"
            )
        if response.status_code == 429 or (
            "transaction" in text.lower() and "limit" in text.lower()
        ):
            raise FirmsQuotaError(f"FIRMS {source} transaction limit reached")
        if self._key in text:
            raise FirmsError("FIRMS response reflected a credential; response was not accepted")
        if response.status_code != 200 or not text.lower().startswith("latitude"):
            if text.strip() == "" and response.status_code == 200:
                return ""
            raise FirmsError(
                f"FIRMS {source} request failed (HTTP {response.status_code}): {self._safe(text)}"
            )
        return text
