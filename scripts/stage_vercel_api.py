"""Stage the local, read-only FireCal snapshot for a Vercel Python deployment.

The generated directory is under data/interim (gitignored). It contains a copy
of the processed observations and must be deployed with Vercel CLI from there.
"""

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
POINTER = ROOT / "data/live/current.json"
GLOBAL_POINTER = ROOT / "data/global/current.json"
GLOBAL_CATALOG = ROOT / "datasets/global/recent/dataset.json"

POINT_COLUMNS = (
    "latitude, longitude, acq_datetime, daynight, confidence, frp, sensor, "
    "satellite, source, weight, cell_id, month, in_series"
)


def compact_parquet(con, source: Path, target: Path, columns: str, order: str) -> None:
    con.execute(
        f"COPY (SELECT {columns} FROM read_parquet(?) ORDER BY {order}) TO ? "
        "(FORMAT PARQUET, COMPRESSION ZSTD, COMPRESSION_LEVEL 19, ROW_GROUP_SIZE 100000)",
        [str(source), str(target)],
    )
    before = con.execute("SELECT count(*) FROM read_parquet(?)", [str(source)]).fetchone()[0]
    after = con.execute("SELECT count(*) FROM read_parquet(?)", [str(target)]).fetchone()[0]
    if before != after:
        raise RuntimeError(f"Row count changed while compacting {source.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--global-globe",
        action="store_true",
        help="Include worldwide globe grid and region boundaries without raw point detail",
    )
    args = parser.parse_args()
    record = json.loads(POINTER.read_text())
    source = (POINTER.parent / record["processed"]).resolve()
    if not (source / "meta.json").is_file():
        raise SystemExit(f"Processed snapshot missing: {source}")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = ROOT / "data/interim" / f"vercel-api-stage-{stamp}"
    target.mkdir(parents=True)
    shutil.copytree(ROOT / "api/app", target / "app")
    shutil.copytree(source, target / "data/processed")
    # Keep every point and every field used by the API. The source Parquet files
    # also contain acquisition fields never read by the deployed API.
    con = duckdb.connect()
    con.execute("SET threads TO 4")
    for partition in sorted((target / "data/processed/points").glob("year=*/data_0.parquet")):
        optimized = partition.with_name("optimized.parquet")
        compact_parquet(con, partition, optimized, POINT_COLUMNS, "month, cell_id, acq_datetime")
        optimized.replace(partition)
    if args.global_globe:
        if not GLOBAL_POINTER.is_file() or not GLOBAL_CATALOG.is_file():
            raise SystemExit("Worldwide data is missing; run 'firecal bootstrap --processed-only'")
        global_record = json.loads(GLOBAL_POINTER.read_text())
        catalog = json.loads(GLOBAL_CATALOG.read_text())
        if global_record.get("base_data_version") != catalog["data_version"]:
            raise SystemExit("Worldwide pointer does not match the pinned repository dataset")
        global_source = (GLOBAL_POINTER.parent / global_record["processed"]).resolve()
        global_target = target / "data/global/snapshot"
        global_target.mkdir(parents=True)
        shutil.copy2(global_source / "meta.json", global_target / "meta.json")
        compact_parquet(
            con,
            global_source / "globe.parquet",
            global_target / "globe.parquet",
            "*",
            "year, month, acq_date, hour, lat, lon",
        )
        compact_parquet(
            con,
            global_source / "regions.parquet",
            global_target / "regions.parquet",
            "*",
            "id",
        )
        (target / "data/global/current.json").write_text(
            json.dumps({**global_record, "processed": "snapshot"}, indent=2) + "\n"
        )
        catalog_target = target / "datasets/global/recent/dataset.json"
        catalog_target.parent.mkdir(parents=True)
        shutil.copy2(GLOBAL_CATALOG, catalog_target)
    (target / "server.py").write_text("from app.main import app\n")
    (target / ".python-version").write_text("3.12\n")
    (target / "requirements.txt").write_text(
        "fastapi>=0.115\n"
        "pydantic-settings>=2.7\n"
        "duckdb>=2.0\n"
        "cachetools>=5.5\n"
        "numpy>=2.0\n"
        "pandas>=2.2\n"
        "shapely>=2.0\n"
        "pyproj>=3.6\n"
    )
    (target / "vercel.json").write_text(
        json.dumps(
            {"$schema": "https://openapi.vercel.sh/vercel.json", "framework": "fastapi"}, indent=2
        )
        + "\n"
    )
    size = sum(path.stat().st_size for path in target.rglob("*") if path.is_file())
    print(f"{target} ({size:,} source bytes)")
    if size >= 100_000_000:
        raise SystemExit("Vercel source exceeds 100 MB; compact or host observations separately")


if __name__ == "__main__":
    main()
