"""Unified hotspot point schema for MODIS and VIIRS (T-07, FR-D-06).

One schema serves both sensors through every stage::

    interim/detections/  normalized archive rows   (POINT_SCHEMA, partitioned)
    interim/points/      clean rows                (POINT_SCHEMA, partitioned by year)
    processed/points/    published rows for the API (PUBLISHED_SCHEMA = + cell_id, weight)

Every Parquet file can be queried directly with DuckDB, e.g.::

    SELECT sensor, count(*) FROM read_parquet('data/processed/points/**/*.parquet',
                                              hive_partitioning = true) GROUP BY sensor
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.dataset as ds

from firecal.grid import GridSpec
from firecal.io import reset_dir
from firecal.paths import DataPaths

#: (column, DuckDB type, Arrow type, description) — FR-D-06 attributes first.
COLUMNS: list[tuple[str, str, pa.DataType, str]] = [
    ("latitude", "DOUBLE", pa.float64(), "Pixel centre latitude (WGS84)"),
    ("longitude", "DOUBLE", pa.float64(), "Pixel centre longitude (WGS84)"),
    ("acq_datetime", "TIMESTAMP", pa.timestamp("us"), "Acquisition time (UTC)"),
    ("acq_date", "DATE", pa.date32(), "Acquisition date (UTC)"),
    ("daynight", "VARCHAR", pa.string(), "D = day, N = night"),
    ("confidence", "VARCHAR", pa.string(), "MODIS 0-100 or VIIRS low/nominal/high"),
    ("frp", "DOUBLE", pa.float64(), "Fire radiative power (MW)"),
    ("sensor", "VARCHAR", pa.string(), "MODIS or VIIRS"),
    ("satellite", "VARCHAR", pa.string(), "Terra, Aqua, S-NPP, NOAA-20, NOAA-21"),
    ("instrument", "VARCHAR", pa.string(), "Instrument name from FIRMS"),
    ("version", "VARCHAR", pa.string(), "FIRMS collection/version, e.g. 6.1 or 2.0NRT"),
    ("type", "INTEGER", pa.int32(), "FIRMS type (0 vegetation fire); NULL for NRT"),
    ("source", "VARCHAR", pa.string(), "SP (standard) or NRT"),
    ("year", "INTEGER", pa.int32(), "Acquisition year"),
    ("month", "INTEGER", pa.int32(), "Acquisition month"),
]
PUBLISHED_EXTRA: list[tuple[str, str, pa.DataType, str]] = [
    ("cell_id", "BIGINT", pa.int64(), "Grid cell id (see firecal.grid)"),
    ("weight", "DOUBLE", pa.float64(), "MODIS-equivalent weight (MODIS 1, VIIRS k / n_sats)"),
    ("in_series", "BOOLEAN", pa.bool_(), "Sensor is the merged-series source that month"),
]

POINT_SCHEMA = pa.schema([(name, arrow) for name, _, arrow, _ in COLUMNS])
PUBLISHED_SCHEMA = pa.schema([(name, arrow) for name, _, arrow, _ in COLUMNS + PUBLISHED_EXTRA])

#: Columns exported in the raw-points CSV (FR-W-17).
EXPORT_COLUMNS = [
    "latitude", "longitude", "acq_datetime", "daynight", "confidence", "frp",
    "sensor", "satellite", "source", "weight",
]  # fmt: skip


def cast_sql(relation: str, extra: list[tuple[str, str, pa.DataType, str]] = ()) -> str:
    """SELECT casting ``relation`` onto the schema column order and types."""
    cols = ", ".join(f"CAST({name} AS {duck}) AS {name}" for name, duck, _, _ in [*COLUMNS, *extra])
    return f"SELECT {cols} FROM ({relation})"


def read_sql(path: Path) -> str:
    """DuckDB relation over a hive-partitioned point folder or a single file."""
    if path.is_dir():
        glob = (path / "**" / "*.parquet").as_posix()
        return f"read_parquet('{glob}', hive_partitioning = true, union_by_name = true)"
    return f"read_parquet('{path.as_posix()}')"


def dataset_schema(path: Path) -> pa.Schema:
    """Arrow schema of a hive-partitioned point folder (partition columns included)."""
    return ds.dataset(path, format="parquet", partitioning="hive").schema


def check_schema(path: Path, expected: pa.Schema = POINT_SCHEMA) -> list[str]:
    """Return a list of schema problems (missing columns or wrong types)."""
    actual = dataset_schema(path)
    problems = []
    for f in expected:
        if f.name not in actual.names:
            problems.append(f"missing column {f.name}")
            continue
        got = actual.field(f.name).type
        # hive partition columns come back as int32/int64 or dictionary strings
        if got != f.type and not (pa.types.is_integer(got) and pa.types.is_integer(f.type)):
            problems.append(f"{f.name}: expected {f.type}, got {got}")
    return problems


def publish_points(paths: DataPaths, grid: GridSpec) -> int:
    """Write clean points with their grid cell id to ``processed/points/year=YYYY``."""
    con = duckdb.connect()
    out = reset_dir(paths.points)
    relation = (
        f"SELECT *, {grid.cell_sql()} AS cell_id, NULL AS weight, NULL AS in_series "
        f"FROM {read_sql(paths.clean)}"
    )
    con.execute(
        f"""COPY ({cast_sql(relation, PUBLISHED_EXTRA)} ORDER BY cell_id, acq_datetime)
            TO '{out.as_posix()}'
            (FORMAT parquet, PARTITION_BY (year), COMPRESSION zstd, OVERWRITE_OR_IGNORE,
             ROW_GROUP_SIZE 100000)"""
    )
    return con.execute(f"SELECT count(*) FROM {read_sql(out)}").fetchone()[0]


def connect(paths: DataPaths) -> duckdb.DuckDBPyConnection:
    """DuckDB connection with views over every available pipeline table."""
    con = duckdb.connect()
    views = {
        "detections": paths.detections,
        "points": paths.points,
        "clean_points": paths.clean,
        "cells": paths.cells,
        "grid_monthly": paths.grid_monthly,
        "coefficients": paths.coefficients,
        "harmonized": paths.harmonized,
    }
    for name, path in views.items():
        if path.exists() and (path.is_file() or any(path.rglob("*.parquet"))):
            con.execute(f"CREATE VIEW {name} AS SELECT * FROM {read_sql(path)}")
    return con
