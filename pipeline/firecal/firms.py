"""Thin HTTP client for the NASA FIRMS API.

The MAP_KEY is only ever read from the environment (``FIRMS_MAP_KEY``) and is never
logged in clear text (NFR-08).
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

#: FIRMS area API source names for near-real-time products (FR-D-03).
NRT_SOURCES: dict[str, str] = {
    "MODIS_NRT": "MODIS",
    "VIIRS_SNPP_NRT": "VIIRS",
    "VIIRS_NOAA20_NRT": "VIIRS",
    "VIIRS_NOAA21_NRT": "VIIRS",
}

#: Maximum day range accepted by the FIRMS area API.
MAX_DAY_RANGE = 5


class FirmsError(RuntimeError):
    """Raised when FIRMS returns an error or an unexpected payload."""


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
    ) -> None:
        if not map_key:
            raise FirmsError("FIRMS_MAP_KEY is not set; copy .env.example to .env and fill it in.")
        self._key = map_key
        self._api_base = api_base.rstrip("/")
        # The key-status endpoint lives under /mapserver, a sibling of /api.
        self._root = self._api_base.rsplit("/api", 1)[0]
        self._http = httpx.Client(timeout=timeout, transport=transport, follow_redirects=True)

    def __enter__(self) -> FirmsClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def key_status(self) -> KeyStatus:
        """Validate the MAP_KEY and return its transaction quota."""
        url = f"{self._root}/mapserver/mapkey_status/"
        response = self._http.get(url, params={"MAP_KEY": self._key})
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
            raise FirmsError(
                f"Invalid MAP_KEY {mask_key(self._key)}: {response.text[:200]}"
            ) from exc

    def area_csv(
        self,
        source: str,
        bbox: tuple[float, float, float, float],
        days: int,
        date: str | None = None,
    ) -> str:
        """Download detections for ``bbox`` (west, south, east, north) as CSV text."""
        if source not in NRT_SOURCES:
            raise FirmsError(f"Unknown FIRMS source {source!r}")
        if not 1 <= days <= MAX_DAY_RANGE:
            raise FirmsError(f"days must be between 1 and {MAX_DAY_RANGE}")
        area = ",".join(f"{v:g}" for v in bbox)
        url = f"{self._api_base}/area/csv/{self._key}/{source}/{area}/{days}"
        if date:
            url += f"/{date}"
        response = self._http.get(url)
        text = response.text
        if response.status_code != 200 or not text.lower().startswith("latitude"):
            if text.strip() == "" and response.status_code == 200:
                return ""
            raise FirmsError(
                f"FIRMS {source} request failed (HTTP {response.status_code}): {text[:200]}"
            )
        return text
