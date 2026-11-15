"""Incrementally update the worldwide window and publish complete versions atomically."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
import pandas as pd

from firecal.acquire import download_windows, verify_receipts
from firecal.bundles import digest
from firecal.global_data import CATALOG, WORLD, global_products, three_months_before
from firecal.grid import GridSpec
from firecal.ingest import normalize_sql, read_csv_sql
from firecal.io import write_json
from firecal.live import PLATFORMS, atomic_json, catchup_plan, resolve_pointer, update_lock
from firecal.schema import cast_sql


def _refresh_global(repo: Path, client, *, target: date | None = None) -> dict:
    target = target or datetime.now(UTC).date()
    root = repo / "data/global"
    with update_lock(root):
        pointer = root / "current.json"
        current = resolve_pointer(pointer)
        catalog = json.loads((repo / CATALOG).read_text())
        before = json.loads(pointer.read_text())
        if before.get("base_data_version") != catalog["data_version"]:
            raise ValueError("Global dataset does not originate from the pinned NASA snapshot")
        watermarks = before.get("watermarks")
        if watermarks is None:
            provenance = json.loads((current / "provenance.json").read_text())
            end = provenance["plan"]["requested_through"]
            watermarks = {
                r["data_id"]: min(end, r["max_date"])
                for r in provenance["availability"]
                if r["data_id"].endswith(("_SP", "_NRT"))
                and r["data_id"].startswith(("MODIS", "VIIRS"))
            }
        old_meta = json.loads((current / "meta.json").read_text())
        if str(target) < old_meta["requested_through"]:
            raise ValueError("Cannot update a global snapshot backwards in time")
        checked = datetime.now(UTC).isoformat()
        atomic_json(root / "status.json", {"status": "updating", "checked_at": checked})
        plan = catchup_plan(watermarks, client.availability(), target)
        if plan["unavailable_gaps"]:
            raise ValueError("NASA cannot fill every missing global source date")
        run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
        run_root = root / "runs" / run_id
        # NRT responses can change within a UTC day. A new refresh must re-fetch
        # its overlap even when its source/date filenames match the previous run.
        manifest = download_windows(client, plan["windows"], WORLD, run_root / "responses")
        verify_receipts(manifest, plan["windows"], WORLD)
        covered, queries = [], []
        for receipt, window in zip(manifest["records"], plan["windows"], strict=True):
            path = Path(receipt["path"])
            if digest(path) != receipt["sha256"]:
                raise ValueError("Global update response checksum changed")
            platform, mode = window.source.rsplit("_", 1)
            for satellite in PLATFORMS[platform]:
                covered.append(
                    {
                        "satellite": satellite,
                        "mode": mode,
                        "start": window.start,
                        "end": str(
                            date.fromisoformat(window.start) + timedelta(days=window.days - 1)
                        ),
                    }
                )
            if receipt["rows"]:
                sensor = "MODIS" if platform == "MODIS" else "VIIRS"
                query = cast_sql(normalize_sql(sensor, read_csv_sql([path]), receipt["columns"]))
                queries.append((query, mode))
        start = max(str(three_months_before(target)), old_meta["start_date"])
        version = hashlib.sha256(
            json.dumps(
                {
                    "previous": old_meta["data_version"],
                    "start": start,
                    "target": str(target),
                    "hashes": [r["sha256"] for r in manifest["records"]],
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()[:12]
        output = run_root / "processed"
        output.mkdir(parents=True)
        with duckdb.connect() as con:
            con.execute("SET threads TO 4")
            old_points = (current / "points/**/*.parquet").as_posix()
            con.execute(
                "CREATE VIEW old AS SELECT * FROM "
                f"read_parquet('{old_points}',hive_partitioning=true)"
            )
            for query, mode in queries:
                if con.execute(
                    f"SELECT count(*) FROM ({query}) WHERE source <> ?", [mode]
                ).fetchall()[0][0]:
                    raise ValueError(
                        "NASA update processing version does not match requested source"
                    )
            if covered:
                con.register("covered", pd.DataFrame(covered))
                old = """SELECT * FROM old o WHERE NOT EXISTS (
                    SELECT 1 FROM covered c WHERE c.satellite=o.satellite
                    AND o.acq_date BETWEEN CAST(c.start AS DATE) AND CAST(c.end AS DATE)
                    AND (o.source='NRT' OR c.mode='SP'))"""
            else:
                old = "SELECT * FROM old"
            grid = GridSpec(0.5)
            union = " UNION ALL BY NAME ".join(
                [old]
                + [
                    f"SELECT *,{grid.cell_sql()} AS cell_id,NULL::DOUBLE AS weight FROM ({q})"
                    for q, _ in queries
                ]
            )
            con.execute(
                f"CREATE VIEW points AS SELECT * FROM ({union}) "
                f"WHERE acq_date BETWEEN DATE '{start}' AND DATE '{target}'"
            )
            summary = global_products(con, output)
            points = (output / "points").as_posix()
            con.execute(
                f"COPY (SELECT * FROM points ORDER BY year,cell_id,acq_datetime) TO '{points}' "
                "(FORMAT parquet,COMPRESSION zstd,PARTITION_BY(year),ROW_GROUP_SIZE 100000)"
            )
        meta = {
            **old_meta,
            **summary,
            "data_version": version,
            "start_date": start,
            "start_month": start[:7],
            "requested_through": str(target),
            "end_month": str(target)[:7],
            "processed_at": datetime.now(UTC).isoformat(),
            "lagging_sources": plan["lagging_sources"],
        }
        write_json(output / "meta.json", meta)
        write_json(
            output / "provenance.json",
            {
                "base_data_version": catalog["data_version"],
                "previous_data_version": old_meta["data_version"],
                "updates": manifest,
            },
        )
        atomic_json(
            pointer,
            {
                "format": "firecal-live-v1",
                "processed": os.path.relpath(output, root),
                "base_data_version": catalog["data_version"],
                "watermarks": plan["watermarks"],
            },
        )
        status = {
            "status": "updated",
            "checked_at": checked,
            "requested_through": str(target),
            "data_version": version,
            "lagging_sources": plan["lagging_sources"],
        }
        atomic_json(root / "status.json", status)
        return status


def refresh_global(repo: Path, client, *, target: date | None = None) -> dict:
    try:
        return _refresh_global(repo, client, target=target)
    except Exception as exc:
        atomic_json(
            repo / "data/global/status.json",
            {
                "status": "failed",
                "checked_at": datetime.now(UTC).isoformat(),
                "error": type(exc).__name__,
                "detail": "Worldwide NASA update failed; freshness is unverified.",
            },
        )
        raise
