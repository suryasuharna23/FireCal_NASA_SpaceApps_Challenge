"""Join saved public NASA gap evidence to the frozen snapshot, without exposure correction."""

import argparse
import hashlib
import json
from pathlib import Path

import duckdb

from firecal.exposure_audit import daily_inventory, parse_missing_days


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--processed", type=Path, default=Path("data/interim/indonesia-extended-20261114/processed")
    )
    parser.add_argument("--acquisition", type=Path, default=Path("data/interim/api-acquisition"))
    parser.add_argument(
        "--response",
        type=Path,
        default=Path("data/interim/exposure-evidence-20261114/nasa-missing-data-response.json"),
    )
    parser.add_argument(
        "--retrieval",
        type=Path,
        default=Path("data/interim/exposure-evidence-20261114/retrieval.json"),
    )
    parser.add_argument(
        "--out", type=Path, default=Path("data/interim/bias-audit-exposure-20261114")
    )
    args = parser.parse_args()
    processed, acquisition, out = (
        args.processed.resolve(),
        args.acquisition.resolve(),
        args.out.resolve(),
    )
    for root in (
        processed,
        acquisition,
        args.response.parent.resolve(),
        args.retrieval.parent.resolve(),
    ):
        if out == root or out.is_relative_to(root) or root.is_relative_to(out):
            raise ValueError("Exposure output must be separate from input trees")
    if out.exists():
        raise ValueError("Preserve the previous exposure run; choose a new output directory")
    meta = json.loads((processed / "meta.json").read_text())
    if meta.get("data_version") != "593ae2d95fdf":
        raise ValueError("Unexpected snapshot")
    retrieval = json.loads(args.retrieval.read_text())
    if retrieval.get("http_status") != 200 or digest(args.response) != retrieval.get("sha256"):
        raise ValueError("NASA response does not match its retrieval receipt")
    gaps = parse_missing_days(json.loads(args.response.read_text()))
    availability = json.loads((acquisition / "availability.json").read_text())["sources"]
    inputs = [
        processed / "meta.json",
        acquisition / "availability.json",
        args.response,
        args.retrieval,
    ]
    inputs += sorted((processed / "points").rglob("*.parquet"))
    inputs += [
        Path(__file__),
        Path(__file__).resolve().parents[1] / "pipeline/firecal/exposure_audit.py",
    ]
    hashes = {str(path.resolve()): digest(path) for path in inputs}
    out.mkdir(parents=True, exist_ok=False)
    (out / "input_manifest.json").write_text(json.dumps(hashes, indent=2) + "\n")
    with duckdb.connect() as con:
        glob = (processed / "points/**/*.parquet").as_posix().replace("'", "''")
        daily = con.execute(
            "SELECT cast(acq_date AS DATE) AS date,satellite,source,count(*) AS n "
            f"FROM read_parquet('{glob}',hive_partitioning=true) WHERE year=2026 GROUP BY ALL"
        ).df()
    daily["date"] = daily.date.astype(str)
    inventory = daily_inventory(
        daily, gaps, availability, "2026-01-01", meta["coverage"]["snapshot_end"]
    )
    if any(digest(path) != value for path, value in hashes.items()):
        raise ValueError("Exposure input changed during the analysis")
    monthly = (
        inventory.assign(month=inventory.date.str[:7])
        .groupby(["satellite", "month"])
        .agg(
            calendar_days=("date", "size"),
            missing_day_flags=("nasa_missing_data_day", "sum"),
            retained_detections=("retained_detections", "sum"),
        )
        .reset_index()
    )
    collisions = inventory[inventory.nasa_missing_data_day & inventory.retained_in_saved_mode.gt(0)]
    report = {
        "data_version": meta["data_version"],
        "retrieval": retrieval,
        "nasa_table_records": len(gaps),
        "inventory_rows": len(inventory),
        "snapshot_2026_missing_day_flags": int(inventory.nasa_missing_data_day.sum()),
        "flags_with_retained_detections": len(collisions),
        "detections_on_flagged_days": int(collisions.retained_in_saved_mode.sum()),
        "exposure_fraction_estimated": False,
        "model_or_serving_changed": False,
        "limitations": [
            "Database missing-day flags do not distinguish partial granules from complete outages.",
            "No flag does not establish full observation coverage; source-mode scope matters.",
            "Retained counts and request successes do not measure valid observation opportunities.",
            "The retrieved table is current evidence, not a historical snapshot of gap knowledge.",
        ],
    }
    gaps.to_csv(out / "nasa_missing_days.csv", index=False)
    inventory.to_csv(out / "daily_evidence_inventory.csv", index=False)
    monthly.to_csv(out / "monthly_gap_flags.csv", index=False)
    (out / "exposure.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
