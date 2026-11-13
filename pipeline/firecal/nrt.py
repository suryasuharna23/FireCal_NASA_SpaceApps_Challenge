"""Daily near-real-time (NRT) update from the FIRMS API (T-08, FR-D-03, FR-D-14).

Each run:

1. downloads the last ``days`` of MODIS and VIIRS NRT detections for the coverage
   bbox and keeps the raw CSVs under ``interim/nrt/raw/`` for auditing;
2. merges them with earlier NRT rows into ``interim/nrt/nrt.parquet``, dropping
   duplicates, so rerunning the same day changes nothing (idempotent);
3. drops NRT rows on or before the last standard (SP) archive date of the same
   satellite, so archive data always replaces NRT once it is published.

A failing source is logged and recorded in ``reports/nrt.json``; existing data is
left untouched so the API keeps serving the last good state (NFR-07).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from firecal.firms import NRT_SOURCES, FirmsClient, FirmsError
from firecal.ingest import dedupe_sql, normalize_sql, read_csv_sql, read_header
from firecal.io import read_json, write_json
from firecal.paths import DataPaths
from firecal.schema import cast_sql, read_sql

log = logging.getLogger(__name__)


@dataclass
class NrtReport:
    run_at: str
    fetched: dict[str, int] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    rows_before: int = 0
    rows_after: int = 0
    replaced_by_sp: int = 0
    first_date: str | None = None
    last_date: str | None = None

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "ok": self.ok}


def raw_dir(paths: DataPaths) -> Path:
    return paths.nrt.parent / "raw"


def fetch(
    client: FirmsClient,
    paths: DataPaths,
    bbox: tuple[float, float, float, float],
    days: int,
    report: NrtReport,
    sources: Iterable[str] = NRT_SOURCES,
) -> list[Path]:
    """Download NRT CSVs; returns the files written (failed sources are skipped)."""
    out = raw_dir(paths)
    out.mkdir(parents=True, exist_ok=True)
    stamp = report.run_at.replace(":", "").replace("-", "")[:15]
    files = []
    for source in sources:
        try:
            text = client.area_csv(source, bbox, days)
        except FirmsError as exc:
            log.warning("NRT %s failed: %s", source, exc)
            report.errors[source] = str(exc)
            continue
        rows = max(text.count("\n") - 1, 0) if text else 0
        report.fetched[source] = rows
        if rows:
            path = out / f"{source}_{stamp}.csv"
            path.write_text(text)
            files.append(path)
    return files


def merge(paths: DataPaths, files: list[Path], report: NrtReport) -> None:
    """Merge new NRT CSVs into ``nrt.parquet``; idempotent and SP-aware."""
    con = duckdb.connect()
    parts = []
    if paths.nrt.exists():
        parts.append(f"SELECT * FROM read_parquet('{paths.nrt.as_posix()}')")
        report.rows_before = con.execute(
            f"SELECT count(*) FROM read_parquet('{paths.nrt.as_posix()}')"
        ).fetchone()[0]
    for sensor, signature in (("MODIS", "brightness"), ("VIIRS", "bright_ti4")):
        group = [f for f in files if signature in read_header(f)]
        if group:
            columns = set().union(*(read_header(f) for f in group))
            parts.append(normalize_sql(sensor, read_csv_sql(group), columns))
    if not parts:
        return

    merged = dedupe_sql(" UNION ALL BY NAME ".join(parts))
    sp_cut = "SELECT NULL::VARCHAR AS satellite, NULL::DATE AS last_sp WHERE false"
    if any(paths.detections.rglob("*.parquet")):
        sp_cut = (
            f"SELECT satellite, max(acq_date) AS last_sp FROM {read_sql(paths.detections)} "
            "WHERE source = 'SP' GROUP BY satellite"
        )
    con.execute(f"CREATE TEMP TABLE merged AS {cast_sql(merged)}")
    con.execute(f"CREATE TEMP TABLE sp AS {sp_cut}")
    report.replaced_by_sp = con.execute(
        "SELECT count(*) FROM merged m JOIN sp USING (satellite) WHERE m.acq_date <= sp.last_sp"
    ).fetchone()[0]

    paths.nrt.parent.mkdir(parents=True, exist_ok=True)
    tmp = paths.nrt.with_suffix(".tmp.parquet")
    con.execute(
        f"""COPY (
                SELECT m.* FROM merged m LEFT JOIN sp USING (satellite)
                WHERE sp.last_sp IS NULL OR m.acq_date > sp.last_sp
                ORDER BY acq_datetime, latitude, longitude, satellite
            ) TO '{tmp.as_posix()}' (FORMAT parquet, COMPRESSION zstd)"""
    )
    tmp.replace(paths.nrt)
    report.rows_after, first, last = con.execute(
        f"SELECT count(*), min(acq_date), max(acq_date) FROM read_parquet('{paths.nrt.as_posix()}')"
    ).fetchone()
    report.first_date = str(first) if first else None
    report.last_date = str(last) if last else None


def update(
    client: FirmsClient,
    paths: DataPaths,
    bbox: tuple[float, float, float, float],
    days: int,
) -> NrtReport:
    report = NrtReport(run_at=datetime.now(UTC).isoformat(timespec="seconds"))
    files = fetch(client, paths, bbox, days, report)
    merge(paths, files, report)
    history = read_json(paths.reports / "nrt.json").get("history", [])[-29:]
    write_json(
        paths.reports / "nrt.json",
        {**report.as_dict(), "history": [*history, report.as_dict()]},
    )
    log.info(
        "NRT: %d -> %d rows (%d replaced by SP), errors: %s",
        report.rows_before,
        report.rows_after,
        report.replaced_by_sp,
        list(report.errors) or "none",
    )
    return report
