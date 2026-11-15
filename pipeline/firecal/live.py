"""Catch up the Indonesia release into separately published, atomic live versions."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
import geopandas as gpd
import pandas as pd
import shapely

from firecal.acquire import download_windows, plan_windows
from firecal.bundles import CATALOG, digest
from firecal.clean import CleanConfig, confidence_predicate
from firecal.country import clip_csv
from firecal.firms import NRT_SOURCES, SP_SOURCES, FirmsClient
from firecal.grid import GridSpec, aggregate_monthly
from firecal.harmonize import HarmonizeConfig, merge_series, parse_month, parse_period
from firecal.ingest import dedupe_sql, normalize_sql, read_csv_sql, read_header
from firecal.io import read_json, write_json
from firecal.paths import DataPaths
from firecal.schema import COLUMNS, cast_sql, publish_points

PLATFORMS = {
    "MODIS": ("Terra", "Aqua"),
    "VIIRS_SNPP": ("S-NPP",),
    "VIIRS_NOAA20": ("NOAA-20",),
    "VIIRS_NOAA21": ("NOAA-21",),
}


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def resolve_pointer(path: Path) -> Path:
    record = read_json(path)
    if record.get("format") != "firecal-live-v1" or not isinstance(record.get("processed"), str):
        raise ValueError("Invalid live dataset pointer")
    target = (path.parent / record["processed"]).resolve()
    if not (target / "meta.json").is_file():
        raise ValueError("Live dataset pointer has no complete metadata")
    return target


@contextmanager
def update_lock(root: Path):
    """OS locks release after crashes; no stale PID file needs manual removal."""
    root.mkdir(parents=True, exist_ok=True)
    with (root / "update.lock").open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def seed_pointer(repo: Path, live_root: Path) -> dict:
    catalog = read_json(repo / CATALOG)
    base = (repo / catalog["processed"]).resolve()
    live_root = live_root.resolve()
    if live_root == base or live_root.is_relative_to(base) or base.is_relative_to(live_root):
        raise ValueError("Live workspace overlaps the frozen snapshot")
    pointer = live_root / "current.json"
    if pointer.exists():
        target = resolve_pointer(pointer)
        if target != base and not target.is_relative_to(live_root / "runs"):
            raise ValueError("Live pointer is outside the configured data workspace")
        meta = read_json(target / "meta.json")
        origin = meta.get("live_update", {}).get("base_data_version", meta.get("data_version"))
        if origin != catalog["data_version"]:
            raise ValueError("Unverified dataset rejected; install the pinned real NASA snapshot")
        return read_json(pointer)
    if read_json(base / "meta.json").get("data_version") != catalog["data_version"]:
        raise ValueError("Install the pinned snapshot before enabling live data")
    watermarks = {}
    for source in (*SP_SOURCES, *NRT_SOURCES):
        manifest = read_json(repo / catalog["acquisition"] / "responses" / source / "manifest.json")
        if not manifest.get("complete"):
            raise ValueError("Install the source receipts before enabling updates")
        ends = []
        for receipt in manifest["records"]:
            req = receipt["request"]
            if req["source"] != source or not 1 <= req["days"] <= 5:
                raise ValueError("Invalid baseline request receipt")
            ends.append(date.fromisoformat(req["start"]) + timedelta(days=req["days"] - 1))
        if not ends:
            raise ValueError("Baseline source has no request coverage")
        watermarks[source] = max(ends).isoformat()
    record = {
        "format": "firecal-live-v1",
        "processed": os.path.relpath(base, live_root),
        "base_data_version": catalog["data_version"],
        "watermarks": watermarks,
        "checked_at": None,
    }
    atomic_json(pointer, record)
    return record


def catchup_plan(watermarks: dict, availability: list[dict], target: date, overlap_days=2) -> dict:
    """Use successful request coverage, not last fire detection, as the cursor."""
    if not 1 <= overlap_days <= 5:
        raise ValueError("Overlap must be between one and five days")
    by_source = {row["data_id"]: row for row in availability}
    if len(by_source) != len(availability):
        raise ValueError("Ambiguous NASA availability")
    windows, new_watermarks, lagging, gaps = [], dict(watermarks), [], []
    for source in (*SP_SOURCES, *NRT_SOURCES):
        if source not in by_source or source not in watermarks:
            raise ValueError("NASA availability or a source cursor is missing")
        row = by_source[source]
        first, latest = date.fromisoformat(row["min_date"]), date.fromisoformat(row["max_date"])
        before = date.fromisoformat(watermarks[source])
        end = min(target, latest)
        needed = before + timedelta(days=1)
        start = needed
        if source in NRT_SOURCES:
            sp = source.replace("_NRT", "_SP")
            standard_end = date.fromisoformat(new_watermarks[sp])
            needed = max(needed, standard_end + timedelta(days=1))
            start = max(before - timedelta(days=overlap_days - 1), standard_end + timedelta(days=1))
            if latest < target:
                lagging.append({"source": source, "available_through": latest.isoformat()})
            # Do not repeatedly download a platform whose availability is paused.
            if end <= before and latest < target:
                continue
        if needed <= end and first > needed:
            gaps.append(
                {
                    "source": source,
                    "start": needed.isoformat(),
                    "end": (first - timedelta(days=1)).isoformat(),
                }
            )
        start = max(start, first)
        if start <= end:
            jobs = plan_windows(source, start.isoformat(), end.isoformat(), availability)
            windows.extend(jobs)
            new_watermarks[source] = max(before, end).isoformat()
    return {
        "windows": windows,
        "watermarks": new_watermarks,
        "lagging_sources": lagging,
        "unavailable_gaps": gaps,
        "requested_through": target.isoformat(),
    }


def _sql(path: Path) -> str:
    return path.as_posix().replace("'", "''")


def build_live_version(
    base: Path,
    paths: DataPaths,
    updates: list[dict],
    watermarks: dict,
    boundary: Path,
    target: date,
) -> dict:
    """Rebuild derived products from clean baseline points plus checked updates; never refit."""
    base_meta = read_json(base / "meta.json")
    grid = GridSpec(float(base_meta["grid_res_deg"]))
    profile = CleanConfig()  # pinned snapshot's filters: 30, nominal/high, 0.02 deg
    country = shapely.union_all(gpd.read_file(boundary).geometry)
    boundary_sha = digest(boundary)
    parts, covered, filtered = [], [], []
    for item in updates:
        job, raw = item["window"], item["path"]
        selected = paths.raw / "updates" / job.source / raw.name
        info = clip_csv(raw, selected, country, boundary_sha)
        filtered.append({"source": job.source, **info})
        for satellite in PLATFORMS[job.source.rsplit("_", 1)[0]]:
            covered.append(
                {
                    "satellite": satellite,
                    "mode": job.source.rsplit("_", 1)[1],
                    "start": job.start,
                    "end": (
                        date.fromisoformat(job.start) + timedelta(days=job.days - 1)
                    ).isoformat(),
                }
            )
        if info["rows"]:
            sensor = "MODIS" if job.source.startswith("MODIS") else "VIIRS"
            parts.append(
                (
                    normalize_sql(sensor, read_csv_sql([selected]), read_header(selected)),
                    job.source.rsplit("_", 1)[1],
                )
            )
    columns = ", ".join(c[0] for c in COLUMNS)
    with duckdb.connect() as con:
        con.execute("SET threads TO 4")
        con.register("covered", pd.DataFrame(covered))
        con.execute(
            f"CREATE TEMP VIEW old AS SELECT {columns} FROM "
            f"read_parquet('{_sql(base / 'points/**/*.parquet')}',hive_partitioning=true)"
        )
        for query, mode in parts:
            bad = con.execute(
                f"SELECT count(*) FROM ({query}) WHERE source <> ?", [mode]
            ).fetchone()[0]
            if bad:
                raise ValueError("Provider processing mode does not match the requested source")
        new = (
            " UNION ALL BY NAME ".join(query for query, _ in parts)
            if parts
            else "SELECT * FROM old WHERE false"
        )
        con.execute(f"CREATE TEMP VIEW new AS {new}")
        # Replacing successful query intervals also removes revised-to-zero rows.
        retained = """SELECT o.* FROM old o WHERE NOT EXISTS (
            SELECT 1 FROM covered c WHERE o.satellite=c.satellite
            AND o.acq_date BETWEEN cast(c.start AS DATE) AND cast(c.end AS DATE)
            AND (c.mode='SP' OR o.source='NRT'))"""
        merged = dedupe_sql(retained + " UNION ALL BY NAME SELECT * FROM new")
        con.execute(f"CREATE TEMP VIEW combined AS {merged}")
        cutoffs = []
        for source in SP_SOURCES:
            for satellite in PLATFORMS[source.rsplit("_", 1)[0]]:
                cutoffs.append({"satellite": satellite, "through": watermarks[source]})
        con.register("cutoffs", pd.DataFrame(cutoffs))
        mask = GridSpec(profile.static_mask_deg)
        con.execute(
            "CREATE TEMP TABLE static_mask AS SELECT bin FROM "
            f"read_parquet('{_sql(base / 'static_mask.parquet')}') "
            f"UNION SELECT DISTINCT {mask.cell_sql()} AS bin FROM new WHERE type IN (1,2,3)"
        )
        clean_sql = f"""SELECT d.* FROM combined d JOIN cutoffs c USING(satellite)
            WHERE (d.source='SP' OR d.acq_date>cast(c.through AS DATE))
            AND {confidence_predicate(profile)}
            AND (d.type=0 OR (d.type IS NULL AND {mask.cell_sql("d.longitude", "d.latitude")}
                NOT IN (SELECT bin FROM static_mask)))"""
        con.execute(
            f"COPY ({cast_sql(clean_sql)}) TO '{_sql(paths.clean)}' "
            "(FORMAT parquet,PARTITION_BY(year),COMPRESSION zstd)"
        )
        con.execute(
            f"COPY (SELECT bin,0.02 AS res FROM static_mask) TO '{_sql(paths.static_mask)}' "
            "(FORMAT parquet)"
        )
    for name in ("cells.parquet", "regions.parquet", "coefficients.parquet"):
        shutil.copy2(base / name, paths.processed / name)
    for name in ("calibration.json", "validation.json"):
        shutil.copy2(base / "reports" / name, paths.reports / name)
    publish_points(paths, grid)
    aggregate_monthly(paths, grid)
    start, end = parse_period(base_meta["calibration_period"])
    cfg = HarmonizeConfig(
        start,
        end,
        tuple(base_meta["test_years"]),
        transition=parse_month(base_meta["transition_month"]),
    )
    meta = merge_series(paths, grid, cfg)
    if digest(paths.coefficients) != digest(base / "coefficients.parquet"):
        raise ValueError("Live refresh changed the frozen conversion coefficients")
    # Zero returned detections still advance successful request coverage. Include
    # those months without pretending that the absence of fires proves exposure.
    through = min(target, max(date.fromisoformat(v) for v in watermarks.values()))
    index = pd.read_parquet(paths.processed / "months.parquet")
    periods = pd.period_range(meta["end_month"], through.strftime("%Y-%m"), freq="M")[1:]
    if len(periods):
        extra = pd.DataFrame(
            {
                "year": periods.year,
                "month": periods.month,
                "n_viirs_sats": 0,
                "has_nrt": True,
                "total": 0.0,
                "source": "VIIRS",
            }
        )
        index = pd.concat([index, extra], ignore_index=True)
        index.to_parquet(paths.processed / "months.parquet", index=False)
        meta["end_month"], meta["months"] = through.strftime("%Y-%m"), len(index)
    with duckdb.connect() as con:
        versions = con.execute(
            "SELECT DISTINCT sensor,version FROM "
            f"read_parquet('{_sql(paths.points / '**/*.parquet')}',"
            "hive_partitioning=true) WHERE version IS NOT NULL ORDER BY sensor,version"
        ).fetchall()
    source_versions = {}
    for sensor, version in versions:
        source_versions.setdefault(sensor, []).append(version)
    meta.update(
        {
            "dataset_status": "experimental",
            "sources": base_meta.get("sources"),
            "source_versions": source_versions,
            "coverage": {**base_meta.get("coverage", {}), "snapshot_end": target.isoformat()},
            "live_update": {
                "base_data_version": base_meta.get("live_update", {}).get(
                    "base_data_version", base_meta["data_version"]
                ),
                "coefficients_refitted": False,
                "checked_through": watermarks,
                "note": "New provisional observations inherit the baseline's accuracy limitations.",
            },
        }
    )
    write_json(paths.meta, meta)
    write_json(paths.reports / "country_filter_update.json", {"files": filtered})
    write_json(
        paths.reports / "nrt.json",
        {"ok": True, "run_at": datetime.now(UTC).isoformat(), "errors": {}},
    )
    validation = read_json(paths.reports / "validation.json")
    validation["live_update_scope"] = (
        "Inherited frozen-baseline diagnostics; newer observations not independently validated."
    )
    write_json(paths.reports / "validation.json", validation)
    return meta


def refresh(
    repo: Path,
    client: FirmsClient,
    *,
    live_root: Path | None = None,
    today: date | None = None,
    plan_only=False,
) -> dict:
    repo = repo.resolve()
    live_root = (live_root or repo / "data/live").resolve()
    target = today or datetime.now(UTC).date()
    catalog = read_json(repo / CATALOG)
    frozen = (repo / catalog["processed"]).resolve()
    if live_root == frozen or live_root.is_relative_to(frozen) or frozen.is_relative_to(live_root):
        raise ValueError("Live workspace overlaps the frozen snapshot")
    with update_lock(live_root):
        current = seed_pointer(repo, live_root)
        base = resolve_pointer(live_root / "current.json")
        # These paths are never mutable live outputs.
        try:
            availability = client.availability()
            plan = catchup_plan(current["watermarks"], availability, target)
            if plan["unavailable_gaps"]:
                raise ValueError(
                    "Missing dates are unavailable from NASA; no incomplete dataset published"
                )
            if plan_only:
                return {
                    "status": "plan",
                    "requests": len(plan["windows"]),
                    "lagging_sources": plan["lagging_sources"],
                    "requested_through": target.isoformat(),
                }
            now = datetime.now(UTC).isoformat()
            if not plan["windows"]:
                result = {
                    "status": "up_to_date",
                    "checked_at": now,
                    "requested_through": target.isoformat(),
                    "lagging_sources": plan["lagging_sources"],
                }
                atomic_json(live_root / "status.json", result)
                return result
            paths = DataPaths(
                live_root
                / "runs"
                / (datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + uuid.uuid4().hex[:8])
            ).ensure()
            atomic_json(live_root / "status.json", {"status": "updating", "checked_at": now})
            write_json(paths.reports / "availability.json", {"sources": availability})
            updates = []
            for source in (*SP_SOURCES, *NRT_SOURCES):
                jobs = [w for w in plan["windows"] if w.source == source]
                if not jobs:
                    continue
                folder = paths.interim / "downloads" / source
                receipt = download_windows(client, jobs, tuple(catalog["bbox"]), folder)
                for job, record in zip(jobs, receipt["records"], strict=True):
                    raw = folder / job.source / job.filename
                    if digest(raw) != record["sha256"]:
                        raise ValueError("Live response checksum changed")
                    updates.append({"window": job, "path": raw})
            boundary = repo / catalog["acquisition"] / "reference/indonesia_10m.geojson"
            meta = build_live_version(base, paths, updates, plan["watermarks"], boundary, target)
            record = {
                **current,
                "processed": os.path.relpath(paths.processed, live_root),
                "watermarks": plan["watermarks"],
                "checked_at": datetime.now(UTC).isoformat(),
            }
            atomic_json(live_root / "current.json", record)
            result = {
                "status": "updated",
                "checked_at": record["checked_at"],
                "requested_through": target.isoformat(),
                "data_version": meta["data_version"],
                "last_acq_date": meta["last_acq_date"],
                "requests": len(updates),
                "lagging_sources": plan["lagging_sources"],
                "checked_through": plan["watermarks"],
            }
            atomic_json(live_root / "status.json", result)
            return result
        except Exception as exc:
            # Fixed messages only: never persist raw provider errors or key-bearing URLs.
            atomic_json(
                live_root / "status.json",
                {
                    "status": "failed",
                    "checked_at": datetime.now(UTC).isoformat(),
                    "error": type(exc).__name__,
                    "detail": "NASA refresh failed; previous complete data retained.",
                },
            )
            raise
