"""Load FIRMS archive CSVs into normalized, partitioned Parquet (T-04, T-05).

FIRMS archive downloads come either as one large ``fire_archive_*.csv`` per request or
as yearly country files (``modis_2019_Indonesia.csv``). The sensor is detected from the
CSV header, not the file name, so both layouts work. Output::

    data/interim/detections/sensor=MODIS/year=2001/data_0.parquet
"""

from __future__ import annotations

import csv
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from firecal.io import reset_dir, write_json
from firecal.paths import DataPaths

log = logging.getLogger(__name__)

SENSORS = ("MODIS",)

#: Raw FIRMS satellite codes -> canonical platform names.
SATELLITES: dict[str, dict[str, str]] = {
    "MODIS": {"T": "Terra", "TERRA": "Terra", "A": "Aqua", "AQUA": "Aqua"},
}

#: Columns that identify a sensor in a FIRMS CSV header.
SIGNATURES: dict[str, str] = {"brightness": "MODIS"}

OPTIONAL_COLUMNS = ("daynight", "frp", "instrument", "version", "type", "confidence")


def read_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return [c.strip().lower() for c in next(csv.reader(fh), [])]


def detect_sensor(columns: Iterable[str]) -> str | None:
    cols = set(columns)
    for signature, sensor in SIGNATURES.items():
        if signature in cols and sensor in SENSORS:
            return sensor
    return None


def discover(raw_dir: Path) -> dict[str, list[Path]]:
    """Group FIRMS CSVs under ``raw_dir`` by sensor (reference/ is skipped)."""
    groups: dict[str, list[Path]] = {s: [] for s in SENSORS}
    for path in sorted(raw_dir.rglob("*.csv")):
        if "reference" in path.relative_to(raw_dir).parts:
            continue
        sensor = detect_sensor(read_header(path))
        if sensor is None:
            log.warning("Skipping %s: not a recognized FIRMS CSV", path)
            continue
        groups[sensor].append(path)
    return groups


def _case_map(expr: str, mapping: dict[str, str], default: str) -> str:
    whens = " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in mapping.items())
    return f"CASE upper(trim({expr})) {whens} ELSE {default} END"


def _confidence_sql(sensor: str) -> str:
    return "trim(confidence)"


def normalize_sql(sensor: str, source_sql: str, columns: Iterable[str]) -> str:
    """SELECT statement mapping a raw FIRMS relation onto the unified point schema."""
    cols = set(columns)

    def col(name: str, expr: str | None = None, null_type: str = "VARCHAR") -> str:
        return expr if name in cols else f"CAST(NULL AS {null_type})"

    hhmm = "lpad(trim(acq_time), 4, '0')"
    acq_dt = (
        f"CAST(acq_date AS DATE) + to_hours(CAST(substr({hhmm}, 1, 2) AS INTEGER))"
        f" + to_minutes(CAST(substr({hhmm}, 3, 2) AS INTEGER))"
    )
    satellite = _case_map("satellite", SATELLITES[sensor], "trim(satellite)")
    return f"""
        SELECT
            CAST(latitude AS DOUBLE) AS latitude,
            CAST(longitude AS DOUBLE) AS longitude,
            CAST({acq_dt} AS TIMESTAMP) AS acq_datetime,
            CAST(acq_date AS DATE) AS acq_date,
            {col("daynight", "upper(trim(daynight))")} AS daynight,
            {col("confidence", _confidence_sql(sensor))} AS confidence,
            {col("frp", "TRY_CAST(frp AS DOUBLE)", "DOUBLE")} AS frp,
            '{sensor}' AS sensor,
            {satellite} AS satellite,
            {col("instrument", "upper(trim(instrument))")} AS instrument,
            {col("version", "trim(version)")} AS version,
            {col("type", "TRY_CAST(type AS INTEGER)", "INTEGER")} AS type,
            CASE WHEN upper({col("version", "version")}) LIKE '%NRT%' THEN 'NRT' ELSE 'SP' END
                AS source,
            CAST(year(CAST(acq_date AS DATE)) AS INTEGER) AS year,
            CAST(month(CAST(acq_date AS DATE)) AS INTEGER) AS month
        FROM {source_sql}
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND acq_date IS NOT NULL
    """


def dedupe_sql(select_sql: str) -> str:
    """Drop exact repeats, preferring standard (SP) over NRT rows."""
    return f"""
        SELECT * FROM ({select_sql})
        QUALIFY row_number() OVER (
            PARTITION BY latitude, longitude, acq_datetime, satellite
            ORDER BY (source = 'NRT'), version DESC NULLS LAST
        ) = 1
    """


def read_csv_sql(files: list[Path]) -> str:
    quoted = ", ".join(f"'{p.as_posix()}'" for p in files)
    return f"read_csv([{quoted}], header = true, all_varchar = true, union_by_name = true)"


@dataclass
class IngestReport:
    sensor: str
    files: list[str] = field(default_factory=list)
    source_rows: dict[int, int] = field(default_factory=dict)
    written_rows: dict[int, int] = field(default_factory=dict)
    satellites: dict[str, dict[str, str]] = field(default_factory=dict)

    @property
    def duplicates(self) -> int:
        return sum(self.source_rows.values()) - sum(self.written_rows.values())

    @property
    def years_match(self) -> bool:
        return set(self.source_rows) == set(self.written_rows)

    def as_dict(self) -> dict[str, object]:
        return {
            "sensor": self.sensor,
            "files": self.files,
            "source_rows": self.source_rows,
            "written_rows": self.written_rows,
            "duplicates_removed": self.duplicates,
            "years_match": self.years_match,
            "satellites": self.satellites,
        }


def ingest_sensor(
    con: duckdb.DuckDBPyConnection, paths: DataPaths, sensor: str, files: list[Path]
) -> IngestReport:
    report = IngestReport(sensor, files=[p.name for p in files])
    columns: set[str] = set()
    for path in files:
        columns.update(read_header(path))
    source = read_csv_sql(files)

    for year, n in con.execute(
        f"SELECT year(CAST(acq_date AS DATE)) AS y, count(*) FROM {source} GROUP BY y ORDER BY y"
    ).fetchall():
        report.source_rows[int(year)] = int(n)

    out_dir = reset_dir(paths.detections / f"sensor={sensor}")
    rel = dedupe_sql(normalize_sql(sensor, source, columns))
    con.execute(
        f"""COPY (
                SELECT * EXCLUDE (sensor) FROM ({rel})
                ORDER BY acq_datetime, latitude, longitude, satellite
            ) TO '{out_dir.as_posix()}'
            (FORMAT parquet, PARTITION_BY (year), COMPRESSION zstd, OVERWRITE_OR_IGNORE)"""
    )

    glob = (out_dir / "**" / "*.parquet").as_posix()
    for year, n in con.execute(
        f"SELECT year, count(*) FROM read_parquet('{glob}', hive_partitioning = true) "
        "GROUP BY year ORDER BY year"
    ).fetchall():
        report.written_rows[int(year)] = int(n)
    for sat, first, last in con.execute(
        f"SELECT satellite, min(acq_date), max(acq_date) FROM read_parquet('{glob}') "
        "GROUP BY satellite ORDER BY satellite"
    ).fetchall():
        report.satellites[sat] = {"first": str(first), "last": str(last)}
    return report


def ingest(paths: DataPaths, sensors: Iterable[str] = SENSORS) -> list[IngestReport]:
    """Ingest every FIRMS CSV in ``data/raw`` and write per-sensor reports."""
    paths.ensure()
    groups = discover(paths.raw)
    con = duckdb.connect()
    reports = []
    for sensor in sensors:
        files = groups.get(sensor, [])
        if not files:
            log.warning("No %s CSV files found in %s", sensor, paths.raw)
            continue
        report = ingest_sensor(con, paths, sensor, files)
        write_json(paths.reports / f"ingest_{sensor.lower()}.json", report.as_dict())
        log.info(
            "%s: %d files, %d rows written, %d duplicates removed",
            sensor,
            len(files),
            sum(report.written_rows.values()),
            report.duplicates,
        )
        reports.append(report)
    return reports
