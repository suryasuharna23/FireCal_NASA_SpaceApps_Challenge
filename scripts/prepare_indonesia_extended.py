"""Build a separate country-filtered, experimental Indonesia dataset through 2026.

Original archives, API responses, and the existing serving dataset are retained.
The fixed baseline estimator is used; this does not promote a new model.
"""

import argparse
import logging
import shutil
from pathlib import Path

import duckdb
import geopandas as gpd
import shapely

from firecal.acquire import plan_windows, verify_receipts
from firecal.clean import clean
from firecal.config import get_settings
from firecal.country import clip_csv, file_sha
from firecal.grid import aggregate_monthly, build_cells
from firecal.harmonize import calibrate, merge_series
from firecal.ingest import ingest
from firecal.io import read_json, write_json
from firecal.nrt import NrtReport
from firecal.nrt import merge as merge_nrt
from firecal.paths import DataPaths
from firecal.provenance import audit_source_versions
from firecal.schema import publish_points
from firecal.validate import validate

EXPECTED_SOURCES = {
    "MODIS_SP",
    "VIIRS_SNPP_SP",
    "VIIRS_NOAA20_SP",
    "VIIRS_NOAA21_SP",
    "MODIS_NRT",
    "VIIRS_SNPP_NRT",
    "VIIRS_NOAA20_NRT",
    "VIIRS_NOAA21_NRT",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-archives-only", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    baseline = settings.paths
    acquisition = baseline.interim / "api-acquisition"
    plan = read_json(acquisition / "plan.json")
    by_source = {item["source"]: item for item in plan.get("sources", [])}
    if set(by_source) != EXPECTED_SOURCES:
        raise ValueError("The full eight-source acquisition plan is required")
    snapshot_dates = {item["requested_end"] for item in by_source.values()}
    if len(snapshot_dates) != 1:
        raise ValueError("The source plans must use the same snapshot end date")
    snapshot_end = snapshot_dates.pop()
    root = baseline.interim / f"indonesia-extended-{snapshot_end.replace('-', '')}"
    if (
        not root.resolve().is_relative_to(baseline.interim.resolve())
        or root.resolve() == baseline.interim.resolve()
    ):
        raise ValueError("Extended dataset must stay under the intended interim directory")
    paths = DataPaths(root).ensure()
    boundary_path = acquisition / "reference" / "indonesia_10m.geojson"
    boundary_record = read_json(acquisition / "reference" / "boundary.json")
    if not boundary_record:
        raise ValueError("Download and record the Natural Earth 10m Indonesia boundary first")
    boundary = shapely.union_all(gpd.read_file(boundary_path).geometry)
    if not boundary.is_valid:
        boundary = shapely.make_valid(boundary)
    boundary_sha = file_sha(boundary_path)
    records = []
    archive = read_json(baseline.reports / "archive_manifest.json")
    if not archive.get("complete") or archive.get("country") != "Indonesia":
        raise ValueError("The verified Indonesia annual archive is required")
    for entry in archive["files"]:
        source = Path(entry["path"])
        if file_sha(source) != entry["sha256"]:
            raise ValueError(f"Original archive changed: {source.name}")
        record = clip_csv(source, paths.raw / "archive" / source.name, boundary, boundary_sha)
        records.append({"kind": "annual_archive", **record})
        logging.info("Staged archive %s: %s country detections", source.name, record["rows"])
    write_json(
        paths.reports / "country_filter.json", {"files": records, "boundary": boundary_record}
    )
    if args.stage_archives_only:
        print("Historical archives country-filtered; API acquisition is still separate.")
        return
    summaries = []
    nrt_files = []
    nrt_fetched = {}
    latest_download = ""
    available = read_json(acquisition / "availability.json")["sources"]
    for source_name in sorted(EXPECTED_SOURCES):
        manifest = read_json(acquisition / "responses" / source_name / "manifest.json")
        item = by_source[source_name]
        expected = plan_windows(source_name, item["requested_start"], snapshot_end, available)
        verify_receipts(manifest, expected, settings.bbox)
        summaries.append({"source": source_name, "windows": len(manifest["records"])})
        for receipt in manifest["records"]:
            latest_download = max(latest_download, receipt.get("downloaded_at", ""))
            source = Path(receipt["path"])
            if file_sha(source) != receipt["sha256"]:
                raise ValueError(f"API response changed: {source.name}")
            target = (
                paths.interim / "nrt" / "raw" / source_name / source.name
                if source_name.endswith("_NRT")
                else paths.raw / "api" / source_name / source.name
            )
            record = clip_csv(
                source,
                target,
                boundary,
                boundary_sha,
            )
            records.append({"kind": source_name, **record})
            if source_name.endswith("_NRT"):
                nrt_fetched[source_name] = nrt_fetched.get(source_name, 0) + record["rows"]
                if record["path"]:
                    nrt_files.append(target)
    write_json(
        paths.reports / "country_filter.json",
        {
            "files": records,
            "boundary": boundary_record,
            "acquisition": summaries,
            "input_rows": sum(r["input_rows"] for r in records),
            "rows": sum(r["rows"] for r in records),
        },
    )
    table = build_cells(settings.grid, [boundary])
    table.to_parquet(paths.cells, index=False)
    shutil.copy2(baseline.regions, paths.regions)
    reports = ingest(paths)
    if not all(report.years_match and not report.warnings for report in reports):
        raise ValueError("Ingest reported a source-year/satellite problem")
    provenance = audit_source_versions(paths)
    nrt_report = NrtReport(run_at=latest_download, fetched=nrt_fetched)
    merge_nrt(paths, nrt_files, nrt_report)
    write_json(paths.reports / "nrt.json", {**nrt_report.as_dict(), "mode": "manual_api_snapshot"})
    cleaned = clean(paths, settings.clean_config)
    publish_points(paths, settings.grid)
    grid = aggregate_monthly(paths, settings.grid)
    calibrate(paths, settings.grid, settings.harmonize_config)
    meta = merge_series(paths, settings.grid, settings.harmonize_config)
    validation = validate(paths, settings.grid, settings.harmonize_config)
    limitations = provenance["limitations"] + [
        "Experimental extension: 2026 and NOAA-21 transfer have not established regional accuracy.",
        (
            "All sources use a Natural Earth 10m pixel-centre country mask; "
            "coastal selection differs from the old pilot."
        ),
        (
            "S-NPP availability ends on 2026-11-02. The monthly satellite-count divisor "
            "does not correct its partial November exposure."
        ),
        (
            "November 2026 is incomplete and provisional; comparison with a full historical "
            "month is not like-for-like."
        ),
        "Partial satellite outages are not corrected by the current exposure approximation.",
    ]
    validation["limitations"] = list(dict.fromkeys(validation["limitations"] + limitations))
    validation["scope"] = (
        "Indonesia experimental extension; known hold-outs, not a new independent test"
    )
    write_json(paths.reports / "validation.json", validation)
    with duckdb.connect() as con:
        points_glob = f"{paths.points.as_posix()}/**/*.parquet"
        satellites = [
            r[0]
            for r in con.execute(
                f"SELECT DISTINCT satellite FROM read_parquet('{points_glob}') ORDER BY satellite"
            ).fetchall()
        ]
        version_rows = con.execute(
            f"SELECT DISTINCT sensor, version FROM read_parquet('{points_glob}') "
            "WHERE version IS NOT NULL ORDER BY sensor, version"
        ).fetchall()
    actual_versions = {}
    for sensor, version in version_rows:
        actual_versions.setdefault(sensor, []).append(version)
    meta.update(
        {
            "sources": "NASA FIRMS annual MODIS/VIIRS archives and SP/NRT API responses",
            "source_versions": actual_versions,
            "dataset_status": "experimental",
            "coverage": {
                "country": "Indonesia",
                "is_global": False,
                "includes_nrt": True,
                "satellites": satellites,
                "region_fallback": "latitude zones",
                "country_mask": "Natural Earth 10m pixel-centre intersection for every source",
                "limitations": limitations,
                "snapshot_end": snapshot_end,
                "snpp_availability_end": "2026-11-02",
            },
        }
    )
    write_json(paths.meta, meta)
    write_json(
        paths.reports / "extended_summary.json",
        {
            "root": root.as_posix(),
            "baseline_preserved": True,
            "staged_rows": sum(r["rows"] for r in records),
            "clean_rows": cleaned.after_static,
            "grid": grid,
            "meta": meta,
            "validation": validation,
            "acquisition": summaries,
        },
    )
    print("Experimental extended dataset:", paths.processed)
    print("Data range:", meta["start_month"], meta["end_month"], "version:", meta["data_version"])
    print("Known hold-out result:", validation["global"])


if __name__ == "__main__":
    main()
