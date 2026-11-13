"""Confidence filtering and static heat-source removal (T-06, FR-D-04, FR-D-05).

Rules:

* MODIS detections need ``confidence >= MODIS_MIN_CONFIDENCE`` (default 30);
  VIIRS detections need a class in ``VIIRS_CONFIDENCE`` (default nominal, high).
* Archive (SP) rows carry the FIRMS ``type`` column; only ``type = 0``
  (presumed vegetation fire) is kept.
* NRT rows have no ``type``. They are dropped when they fall inside the static
  source mask: small bins (``STATIC_MASK_DEG``, ~2 km) where the archive ever
  flagged a volcano (1), other static land source (2) or offshore source (3).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import duckdb

from firecal.grid import GridSpec
from firecal.io import reset_dir, write_json
from firecal.paths import DataPaths
from firecal.schema import cast_sql

log = logging.getLogger(__name__)

STATIC_TYPES = (1, 2, 3)


@dataclass(frozen=True)
class CleanConfig:
    modis_min_confidence: int = 30
    viirs_confidence: tuple[str, ...] = ("nominal", "high")
    static_mask_deg: float = 0.02


@dataclass
class CleanReport:
    before: dict[str, int] = field(default_factory=dict)
    after_confidence: dict[str, int] = field(default_factory=dict)
    after_static: dict[str, int] = field(default_factory=dict)
    static_bins: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "before": self.before,
            "after_confidence": self.after_confidence,
            "after_static": self.after_static,
            "removed_low_confidence": {
                s: self.before[s] - self.after_confidence.get(s, 0) for s in self.before
            },
            "removed_static": {
                s: self.after_confidence.get(s, 0) - self.after_static.get(s, 0)
                for s in self.before
            },
            "static_mask_bins": self.static_bins,
        }


def detections_sql(paths: DataPaths) -> str:
    """Union of archive detections and (if present) merged NRT detections."""
    glob = (paths.detections / "**" / "*.parquet").as_posix()
    parts = [
        f"SELECT * FROM read_parquet('{glob}', hive_partitioning = true, union_by_name = true)"
    ]
    if paths.nrt.exists():
        parts.append(f"SELECT * FROM read_parquet('{paths.nrt.as_posix()}')")
    return " UNION ALL BY NAME ".join(parts)


def confidence_predicate(cfg: CleanConfig) -> str:
    levels = ", ".join(f"'{c}'" for c in cfg.viirs_confidence)
    return (
        f"((sensor = 'MODIS' AND TRY_CAST(confidence AS INTEGER) >= {cfg.modis_min_confidence})"
        f" OR (sensor = 'VIIRS' AND confidence IN ({levels})))"
    )


def _counts(con: duckdb.DuckDBPyConnection, sql: str) -> dict[str, int]:
    rows = con.execute(f"SELECT sensor, count(*) FROM ({sql}) GROUP BY sensor").fetchall()
    return {str(s): int(n) for s, n in sorted(rows)}


def clean(paths: DataPaths, cfg: CleanConfig = CleanConfig()) -> CleanReport:
    con = duckdb.connect()
    mask_grid = GridSpec(cfg.static_mask_deg)
    con.execute(f"CREATE TEMP VIEW det AS {detections_sql(paths)}")

    types = ", ".join(map(str, STATIC_TYPES))
    con.execute(
        f"""CREATE TEMP TABLE static_mask AS
            SELECT DISTINCT {mask_grid.cell_sql()} AS bin FROM det WHERE type IN ({types})
            ORDER BY bin"""
    )

    conf_sql = f"SELECT * FROM det WHERE {confidence_predicate(cfg)}"
    clean_sql = f"""
        SELECT * FROM ({conf_sql}) d
        WHERE d.type = 0
           OR (d.type IS NULL
               AND {mask_grid.cell_sql("d.longitude", "d.latitude")}
                   NOT IN (SELECT bin FROM static_mask))
    """

    report = CleanReport(
        before=_counts(con, "SELECT * FROM det"),
        after_confidence=_counts(con, conf_sql),
        after_static=_counts(con, clean_sql),
        static_bins=con.execute("SELECT count(*) FROM static_mask").fetchone()[0],
    )

    out = reset_dir(paths.clean)
    con.execute(
        f"""COPY (
                {cast_sql(clean_sql)}
                ORDER BY acq_datetime, latitude, longitude, satellite
            ) TO '{out.as_posix()}'
            (FORMAT parquet, PARTITION_BY (year), COMPRESSION zstd, OVERWRITE_OR_IGNORE)"""
    )
    paths.processed.mkdir(parents=True, exist_ok=True)
    con.execute(
        f"COPY (SELECT bin, {cfg.static_mask_deg} AS res FROM static_mask) "
        f"TO '{paths.static_mask.as_posix()}' (FORMAT parquet)"
    )
    write_json(paths.reports / "clean.json", report.as_dict())
    for sensor in report.before:
        log.info(
            "%s: %d -> %d after confidence -> %d after static sources",
            sensor,
            report.before[sensor],
            report.after_confidence.get(sensor, 0),
            report.after_static.get(sensor, 0),
        )
    return report
