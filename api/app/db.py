"""DuckDB connection over the processed Parquet cube."""

from collections.abc import Iterator

import duckdb

from app.settings import get_settings


def get_connection() -> Iterator[duckdb.DuckDBPyConnection]:
    """FastAPI dependency yielding a short-lived in-memory DuckDB connection.

    Parquet files under ``DATA_URI`` are queried directly; when ``DATA_URI`` points
    to S3/R2 the ``httpfs`` extension is loaded with the configured credentials.
    """
    settings = get_settings()
    con = duckdb.connect()
    try:
        if settings.data_uri.startswith("s3://"):
            con.execute("INSTALL httpfs; LOAD httpfs;")
            con.execute(
                "CREATE SECRET (TYPE s3, KEY_ID ?, SECRET ?, ENDPOINT ?)",
                [
                    settings.s3_access_key_id,
                    settings.s3_secret_access_key.get_secret_value(),
                    settings.s3_endpoint,
                ],
            )
        yield con
    finally:
        con.close()
