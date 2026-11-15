"""Reproduce the real-data Indonesia pilot after downloading the annual archives.

Run from the repository root: uv run --no-sync python scripts/prepare_indonesia.py
This rebuilds derived tables, preserves raw files, and never generates sample data.
"""

import logging

import duckdb
import geopandas as gpd

from firecal.archive import fetch
from firecal.clean import clean
from firecal.config import get_settings
from firecal.grid import aggregate_monthly, build_cells
from firecal.harmonize import calibrate, merge_series
from firecal.ingest import discover, ingest
from firecal.io import read_json, write_json
from firecal.overlap import monthly_pairs, suggest_period, yearly_ratios
from firecal.provenance import audit_source_versions
from firecal.regions import regions
from firecal.schema import check_schema, publish_points
from firecal.validate import validate


def main() -> None:
    """Build the archived Indonesia dataset with the preselected hold-out years."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    paths = settings.paths.ensure()
    manifest = read_json(paths.reports / "archive_manifest.json")
    if not manifest.get("complete") or manifest.get("country") != "Indonesia":
        raise ValueError("First run firecal download-archive --country Indonesia")
    expected = {entry["path"] for entry in manifest["files"]}
    actual = {p.as_posix() for files in discover(paths.raw).values() for p in files}
    if actual != expected:
        raise ValueError("Raw CSVs differ from the verified manifest; isolate other datasets first")

    base = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson"
    country_path = fetch(
        f"{base}/ne_50m_admin_0_countries.geojson",
        paths.reference / "ne_50m_admin_0_countries.geojson",
    )
    province_path = fetch(
        f"{base}/ne_10m_admin_1_states_provinces.geojson",
        paths.reference / "ne_10m_admin_1_states_provinces.geojson",
    )
    countries = gpd.read_file(country_path)
    indonesia = countries[countries["ADMIN"] == "Indonesia"]
    if len(indonesia) != 1:
        raise ValueError("Indonesia boundary not uniquely identified")
    indonesia.to_file(paths.reference / "indonesia_boundary.geojson", driver="GeoJSON")
    cells = build_cells(settings.grid, list(indonesia.geometry))
    cells.to_parquet(paths.cells, index=False)
    region_table = regions(paths, [str(country_path), str(province_path)])
    region_table[region_table.country == "Indonesia"].to_parquet(paths.regions, index=False)

    ingest_reports = ingest(paths)
    if not all(r.years_match and not r.warnings for r in ingest_reports):
        raise ValueError("Review ingest coverage/satellite warnings before calibration")
    provenance = audit_source_versions(paths)
    clean_report = clean(paths, settings.clean_config)
    publish_points(paths, settings.grid)
    problems = check_schema(paths.clean)
    if problems:
        raise ValueError(problems)
    grid_report = aggregate_monthly(paths, settings.grid)

    # Diagnose overlap without changing the period based on held-out performance.
    ratios = yearly_ratios(monthly_pairs(paths, settings.grid))
    ratios.to_csv(paths.reports / "overlap_ratios.csv", index=False)
    try:
        choice = suggest_period(ratios)
        suggestion = choice.period
    except ValueError as exc:
        suggestion = str(exc)
    write_json(
        paths.reports / "overlap.json",
        {
            "configured_period": settings.calibration_period,
            "suggested_period": suggestion,
            "decision": (
                f"Keep preselected {settings.calibration_period}; "
                f"hold-out years {settings.test_years} remain excluded from fit."
            ),
        },
    )
    calibrate(paths, settings.grid, settings.harmonize_config)
    meta = merge_series(paths, settings.grid, settings.harmonize_config)
    validation = validate(paths, settings.grid, settings.harmonize_config)
    validation["limitations"].extend(provenance["limitations"])
    validation["source_version_audit"] = provenance
    write_json(paths.reports / "validation.json", validation)

    with duckdb.connect() as con:
        points_glob = f"{paths.points.as_posix()}/**/*.parquet"
        satellites = [
            r[0]
            for r in con.execute(
                f"SELECT DISTINCT satellite FROM read_parquet('{points_glob}') ORDER BY satellite"
            ).fetchall()
        ]
    meta["sources"] = "NASA FIRMS MODIS annual archives and VIIRS 375 m: " + ", ".join(satellites)
    meta["source_versions"] = provenance["reported_versions"]
    meta["dataset_status"] = "experimental"
    meta["coverage"] = {
        "country": "Indonesia",
        "archive_years": manifest["requested_years"],
        "satellites": satellites,
        "is_global": False,
        "includes_nrt": False,
        "region_fallback": "latitude zones (ecoregion map not supplied)",
        "limitations": manifest["limitations"] + provenance["limitations"],
    }
    write_json(paths.meta, meta)
    write_json(
        paths.reports / "indonesia_pilot.json",
        {
            "archive_rows": manifest["rows"],
            "archive_files": len(manifest["files"]),
            "clean_rows": clean_report.after_static,
            "grid": grid_report,
            "coverage": meta["coverage"],
            "data_version": meta["data_version"],
            "start_month": meta["start_month"],
            "end_month": meta["end_month"],
            "calibration_period": settings.calibration_period,
            "validation": validation,
            "overlap_suggested_period": suggestion,
            "limitations": [
                "The validation report's 'global' aggregate refers to Indonesia only.",
                "Latitude zones are coarse fallback regions, not ecological biome polygons.",
                "Natural Earth boundaries may not reflect current province divisions.",
                "Current-year and NOAA-21 observations have not been added.",
            ],
        },
    )
    print("\nIndonesia pilot complete:", meta["start_month"], "to", meta["end_month"])
    print("Hold-out result:", validation["global"])
    print("Report:", paths.reports / "indonesia_pilot.json")


if __name__ == "__main__":
    main()
