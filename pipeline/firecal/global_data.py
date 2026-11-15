"""Real worldwide FIRMS observations, kept separate from Indonesia calibration."""

from __future__ import annotations

import calendar
import hashlib
import json
import os
import zipfile
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb

from firecal.acquire import download_windows, plan_windows, verify_receipts
from firecal.bundles import digest, download_asset, install_archive
from firecal.firms import FirmsClient
from firecal.grid import GridSpec
from firecal.ingest import normalize_sql, read_csv_sql
from firecal.io import write_json
from firecal.schema import cast_sql

WORLD = (-180.0, -90.0, 180.0, 90.0)
PLATFORMS = ("MODIS", "VIIRS_SNPP", "VIIRS_NOAA20", "VIIRS_NOAA21")
CATALOG = Path("datasets/global/recent/dataset.json")


def three_months_before(target: date) -> date:
    month = target.year * 12 + target.month - 1 - 3
    year, offset = divmod(month, 12)
    return date(year, offset + 1, min(target.day, calendar.monthrange(year, offset + 1)[1]))


def global_plan(start: date, end: date, availability: list[dict]) -> dict:
    """Prefer SP per platform, then NRT with no overlapping date coverage."""
    if start > end:
        raise ValueError("Start must not exceed end")
    by_source = {row["data_id"]: row for row in availability}
    if len(by_source) != len(availability):
        raise ValueError("Ambiguous NASA source availability")
    windows, lagging = [], []
    for platform in PLATFORMS:
        cursor = start
        for suffix in ("SP", "NRT"):
            source = f"{platform}_{suffix}"
            row = by_source[source]
            first = max(cursor, date.fromisoformat(row["min_date"]))
            last = min(end, date.fromisoformat(row["max_date"]))
            if first > last:
                continue
            if first > cursor:
                raise ValueError(f"NASA cannot supply {platform} from {cursor} to {first}")
            windows.extend(plan_windows(source, first.isoformat(), last.isoformat(), availability))
            cursor = last + timedelta(days=1)
        if cursor <= start:
            raise ValueError(f"No real NASA observations available for {platform}")
        if cursor <= end:
            lagging.append(
                {"source": platform + "_NRT", "available_through": str(cursor - timedelta(days=1))}
            )
    return {
        "start_date": str(start),
        "requested_through": str(end),
        "bbox": list(WORLD),
        "windows": windows,
        "lagging_sources": lagging,
    }


def acquire_global(client: FirmsClient, root: Path, start: date, end: date) -> dict:
    availability = client.availability()
    plan = global_plan(start, end, availability)
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "availability.json", availability)
    write_json(root / "plan.json", {**plan, "windows": [asdict(w) for w in plan["windows"]]})
    manifest = download_windows(client, plan["windows"], WORLD, root / "responses")
    verify_receipts(manifest, plan["windows"], WORLD)
    return plan


def build_global(acquisition: Path, output: Path) -> dict:
    """Build uncalibrated points and hourly cells from a complete, verified plan."""
    from firecal.acquire import RequestWindow

    plan = json.loads((acquisition / "plan.json").read_text())
    manifest = json.loads((acquisition / "responses/manifest.json").read_text())
    windows = [RequestWindow(**w) for w in plan["windows"]]
    verify_receipts(manifest, windows, WORLD)
    fingerprint = json.dumps(
        {"plan": plan, "hashes": [r["sha256"] for r in manifest["records"]]}, sort_keys=True
    )
    version = hashlib.sha256(fingerprint.encode()).hexdigest()[:12]
    if output.exists():
        raise FileExistsError("Global output exists; preserve it before building")
    output.mkdir(parents=True)
    grid = GridSpec(0.5)
    receipts = []
    with duckdb.connect() as con:
        con.execute("SET threads TO 4")
        for receipt, window in zip(manifest["records"], windows, strict=True):
            raw = acquisition / "responses" / window.source / window.filename
            if raw.stat().st_size != receipt["bytes"] or digest(raw) != receipt["sha256"]:
                raise ValueError("Global NASA response checksum changed")
            public = {k: v for k, v in receipt.items() if k != "path"}
            public["input_file"] = f"{window.source}/{window.filename}"
            receipts.append(public)
            if not receipt["rows"]:
                continue
            sensor = "MODIS" if window.source.startswith("MODIS") else "VIIRS"
            query = cast_sql(normalize_sql(sensor, read_csv_sql([raw]), receipt["columns"]))
            mode = window.source.rsplit("_", 1)[1]
            mismatch = con.execute(
                f"SELECT count(*) FROM ({query}) WHERE source <> ?", [mode]
            ).fetchone()[0]
            if mismatch:
                raise ValueError("NASA processing version does not match the requested product")
            folder = output / "points" / f"year={window.start[:4]}"
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / (raw.stem + ".parquet")
            con.execute(
                f"COPY (SELECT *, {grid.cell_sql()} AS cell_id, NULL::DOUBLE AS weight "
                f"FROM ({query}) ORDER BY month,cell_id,acq_datetime) "
                f"TO '{target.as_posix()}' (FORMAT parquet,COMPRESSION zstd)"
            )
            count = con.execute("SELECT count(*) FROM read_parquet(?)", [str(target)]).fetchone()[0]
            if count != receipt["rows"]:
                raise ValueError("Global normalization lost NASA detections")
        points = (output / "points/**/*.parquet").as_posix()
        con.execute(
            f"CREATE VIEW points AS SELECT * FROM read_parquet('{points}',hive_partitioning=true)"
        )
        summary = global_products(con, output)
        if summary["rows"] != sum(r["rows"] for r in receipts):
            raise ValueError("Global point count does not match source receipts")
    meta = {
        "format": "firecal-global-v1",
        "data_version": version,
        "scope": "global",
        "start_date": plan["start_date"],
        "requested_through": plan["requested_through"],
        "start_month": plan["start_date"][:7],
        "end_month": plan["requested_through"][:7],
        **summary,
        "processed_at": datetime.now(UTC).isoformat(),
        "grid_res_deg": 0.5,
        "lagging_sources": plan["lagging_sources"],
        "bbox": list(WORLD),
        "mode": "raw",
        "harmonized_available": False,
        "limitations": [
            "Detections are not unique fires; a fire may be seen by multiple satellites.",
            "Raw global counts have no globally validated harmonization "
            "or historical anomaly baseline.",
            "The first and current calendar months are partial; the window spans "
            "three calendar months back from the requested date.",
            "Successful requests do not establish continuous satellite observation coverage.",
            "All returned detections are retained without the Indonesia "
            "confidence or duplicate filters.",
        ],
    }
    write_json(output / "meta.json", meta)
    write_json(
        output / "provenance.json",
        {
            "complete": True,
            "plan": plan,
            "records": receipts,
            "availability": json.loads((acquisition / "availability.json").read_text()),
        },
    )
    return meta


def global_products(con, output: Path) -> dict:
    """Summarize the connection's points view and reconcile the hourly grid."""
    count, first, last, provisional = con.execute(
        "SELECT count(*),min(acq_date),max(acq_date),bool_or(source='NRT') FROM points"
    ).fetchone()
    if not count:
        raise ValueError("No real global detections available to publish")
    globe = output / "globe.parquet"
    con.execute(
        f"""COPY (
            SELECT year,month,acq_date,hour(acq_datetime)::TINYINT AS hour,cell_id,
                   (-180+(cell_id%720+0.5)*0.5)::FLOAT AS lon,
                   (90-(floor(cell_id/720)+0.5)*0.5)::FLOAT AS lat,
                   count(*)::INTEGER AS raw,
                   count(*) FILTER(WHERE sensor='MODIS')::INTEGER AS n_modis,
                   count(*) FILTER(WHERE sensor='VIIRS')::INTEGER AS n_viirs,
                   bool_or(source='NRT') AS provisional
            FROM points GROUP BY ALL ORDER BY year,month,acq_date,hour,cell_id
        ) TO '{globe.as_posix()}' (FORMAT parquet,COMPRESSION zstd)"""
    )
    if con.execute("SELECT sum(raw) FROM read_parquet(?)", [str(globe)]).fetchone()[0] != count:
        raise ValueError("Global grid lost detections")
    versions = {
        s: [
            v
            for (v,) in con.execute(
                "SELECT DISTINCT version FROM points WHERE sensor=? ORDER BY version", [s]
            ).fetchall()
        ]
        for s in ("MODIS", "VIIRS")
    }
    platforms = [
        {"satellite": s, "rows": n, "first_detection": str(a), "last_detection": str(b)}
        for s, n, a, b in con.execute(
            "SELECT satellite,count(*),min(acq_date),max(acq_date) "
            "FROM points GROUP BY satellite ORDER BY satellite"
        ).fetchall()
    ]
    return {
        "rows": count,
        "first_acq_date": str(first),
        "last_acq_date": str(last),
        "provisional": bool(provisional),
        "source_versions": versions,
        "platforms": platforms,
    }


def package_global(repo: Path, processed: Path) -> dict:
    """Include the processed observations and receipts as pinned normal-Git pieces."""
    meta = json.loads((processed / "meta.json").read_text())
    version = meta["data_version"]
    folder = repo / "datasets/global/recent"
    folder.mkdir(parents=True, exist_ok=True)
    if (repo / CATALOG).exists():
        raise FileExistsError("Preserve the existing pinned global catalog before replacing it")
    destination = Path("data/global/snapshots") / version
    entries = [
        (destination / p.relative_to(processed), p)
        for p in sorted(processed.rglob("*"))
        if p.is_file()
    ]
    manifest = {
        "data_version": version,
        "kind": "global",
        "files": [
            {"path": name.as_posix(), "bytes": p.stat().st_size, "sha256": digest(p)}
            for name, p in entries
        ],
    }
    archive = repo / "data/interim/share" / f"firecal-global-{version}.zip"
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        for name, path in entries:
            z.write(path, name.as_posix())
        z.writestr(f"SNAPSHOT-MANIFEST-global-{version}.json", json.dumps(manifest, indent=2))
    pieces = []
    with archive.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            p = folder / f"{archive.name}.{len(pieces):04d}.chunk"
            p.write_bytes(block)
            pieces.append(
                {"path": p.relative_to(repo).as_posix(), "bytes": len(block), "sha256": digest(p)}
            )
    asset = {
        "kind": "global",
        "file": archive.name,
        "bytes": archive.stat().st_size,
        "sha256": digest(archive),
        "pieces": pieces,
    }
    catalog = {
        "format": "firecal-global-v1",
        "data_version": version,
        "processed": destination.as_posix(),
        "start_date": meta["start_date"],
        "requested_through": meta["requested_through"],
        "rows": meta["rows"],
        "assets": [asset],
    }
    write_json(repo / CATALOG, catalog)
    return catalog


def install_global(repo: Path) -> dict:
    """Verify included pieces and install the pinned worldwide snapshot."""
    from firecal.live import atomic_json

    catalog_path = repo / CATALOG
    if not catalog_path.is_file():
        raise ValueError("Global dataset catalog is missing; sync the complete repository")
    catalog = json.loads(catalog_path.read_text())
    for asset in catalog["assets"]:
        archive = download_asset(asset, repo / "data/interim/share", repo)
        install_archive(archive, repo, catalog["data_version"])
    root = repo / "data/global"
    pointer = root / "current.json"
    if pointer.exists():
        from firecal.live import resolve_pointer

        record = json.loads(pointer.read_text())
        target = resolve_pointer(pointer)
        if record.get("base_data_version") != catalog["data_version"] or (
            target != (repo / catalog["processed"]).resolve()
            and not target.is_relative_to((root / "runs").resolve())
        ):
            raise ValueError("Existing global pointer is outside the pinned real-data workspace")
    else:
        atomic_json(
            pointer,
            {
                "format": "firecal-live-v1",
                "processed": os.path.relpath(repo / catalog["processed"], root),
                "base_data_version": catalog["data_version"],
            },
        )
    return catalog
