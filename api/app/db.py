"""Read-only access to the processed Parquet cube through DuckDB.

``DATA_URI`` is either a local folder (``./data/processed``) or an S3/R2 prefix
(``s3://firecal-data/processed``); in the latter case DuckDB reads through
``httpfs`` with the configured credentials.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import duckdb

from app.settings import ApiSettings, get_settings


class DataUnavailableError(RuntimeError):
    """The processed cube has not been built or cannot be reached."""


class Dataset:
    """Locations of the processed tables plus a cached ``meta.json``."""

    META_TTL = 60.0

    def __init__(self, uri: str) -> None:
        self.uri = uri.rstrip("/")
        self.remote = "://" in self.uri
        self._meta: tuple[float, dict[str, Any]] | None = None
        self._lock = threading.Lock()

    def path(self, name: str) -> str:
        return f"{self.uri}/{name}"

    @property
    def harmonized(self) -> str:
        return f"read_parquet('{self.path('harmonized.parquet')}')"

    @property
    def months(self) -> str:
        return f"read_parquet('{self.path('months.parquet')}')"

    @property
    def points(self) -> str:
        glob = self.path("points/**/*.parquet")
        return f"read_parquet('{glob}', hive_partitioning = true)"

    def points_year(self, year: int) -> str:
        return f"read_parquet('{self.path(f'points/year={year}/*.parquet')}')"

    def exists(self, name: str) -> bool:
        return self.remote or Path(self.path(name)).exists()

    def meta(self, con: duckdb.DuckDBPyConnection | None = None) -> dict[str, Any]:
        with self._lock:
            if self._meta and time.monotonic() - self._meta[0] < self.META_TTL:
                return self._meta[1]
            try:
                if self.remote:
                    text = (
                        (con or connect())
                        .execute("SELECT content FROM read_text(?)", [self.path("meta.json")])
                        .fetchone()[0]
                    )
                else:
                    text = Path(self.path("meta.json")).read_text()
            except (OSError, duckdb.Error, TypeError) as exc:
                raise DataUnavailableError(
                    "Processed data not found; run the pipeline (make data)"
                ) from exc
            meta = json.loads(text)
            self._meta = (time.monotonic(), meta)
            return meta

    def report(
        self, name: str, con: duckdb.DuckDBPyConnection | None = None
    ) -> dict[str, Any] | None:
        """A JSON report written by the pipeline (processed/reports/<name>), if any."""
        location = self.path(f"reports/{name}")
        try:
            if self.remote:
                row = (
                    (con or connect())
                    .execute("SELECT content FROM read_text(?)", [location])
                    .fetchone()
                )
                return json.loads(row[0]) if row else None
            path = Path(location)
            return json.loads(path.read_text()) if path.exists() else None
        except (OSError, duckdb.Error, ValueError):
            return None


_datasets: dict[str, Dataset] = {}


def get_dataset() -> Dataset:
    uri = get_settings().data_uri
    if uri not in _datasets:
        _datasets[uri] = Dataset(uri)
    return _datasets[uri]


def connect(settings: ApiSettings | None = None) -> duckdb.DuckDBPyConnection:
    settings = settings or get_settings()
    con = duckdb.connect()
    con.execute("SET threads TO 4")
    if settings.data_uri.startswith("s3://"):
        con.execute("INSTALL httpfs; LOAD httpfs;")
        endpoint = settings.s3_endpoint.removeprefix("https://").removeprefix("http://")
        con.execute(
            "CREATE SECRET (TYPE s3, KEY_ID ?, SECRET ?, ENDPOINT ?, URL_STYLE 'path', "
            "REGION 'auto')",
            [
                settings.s3_access_key_id,
                settings.s3_secret_access_key.get_secret_value(),
                endpoint,
            ],
        )
    return con


def get_connection() -> Iterator[duckdb.DuckDBPyConnection]:
    """FastAPI dependency yielding a short-lived DuckDB connection."""
    con = connect()
    try:
        yield con
    finally:
        con.close()
