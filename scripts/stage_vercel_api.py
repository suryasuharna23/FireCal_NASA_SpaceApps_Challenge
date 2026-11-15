"""Stage the local, read-only FireCal snapshot for a Vercel Python deployment.

The generated directory is under data/interim (gitignored). It contains a copy
of the processed observations and must be deployed with Vercel CLI from there.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
POINTER = ROOT / "data/live/current.json"


def main() -> None:
    record = json.loads(POINTER.read_text())
    source = (POINTER.parent / record["processed"]).resolve()
    if not (source / "meta.json").is_file():
        raise SystemExit(f"Processed snapshot missing: {source}")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = ROOT / "data/interim" / f"vercel-api-stage-{stamp}"
    target.mkdir(parents=True)
    shutil.copytree(ROOT / "api/app", target / "app")
    shutil.copytree(source, target / "data/processed")
    # Vercel Hobby limits CLI source uploads to 100 MB. Recompress the point
    # partitions without dropping observations or changing their schema.
    con = duckdb.connect()
    con.execute("SET threads TO 4")
    for partition in sorted((target / "data/processed/points").glob("year=*/data_0.parquet")):
        optimized = partition.with_name("optimized.parquet")
        con.execute(
            "COPY (SELECT * FROM read_parquet(?)) TO ? "
            "(FORMAT PARQUET, COMPRESSION ZSTD, COMPRESSION_LEVEL 19, ROW_GROUP_SIZE 100000)",
            [str(partition), str(optimized)],
        )
        before = con.execute("SELECT count(*) FROM read_parquet(?)", [str(partition)]).fetchone()[0]
        after = con.execute("SELECT count(*) FROM read_parquet(?)", [str(optimized)]).fetchone()[0]
        if before != after:
            raise RuntimeError(f"Point count changed while optimizing {partition.name}")
        optimized.replace(partition)
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
    print(target)


if __name__ == "__main__":
    main()
