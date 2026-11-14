"""Audit reported FIRMS product versions without assuming collection homogeneity."""

import duckdb

from firecal.io import write_json
from firecal.paths import DataPaths


def audit_source_versions(paths: DataPaths) -> dict:
    """Record version/year counts and flag MODIS codes outside the 61.* family.

    Report original codes verbatim. A version-code audit does not verify the
    upstream processing history, observation exposure, or VIIRS type revisions.
    """
    glob = (paths.detections / "**" / "*.parquet").as_posix()
    with duckdb.connect() as con:
        table = con.execute(
            f"SELECT sensor, year, version, count(*) AS rows "
            f"FROM read_parquet('{glob}', hive_partitioning=true) "
            "GROUP BY ALL ORDER BY sensor, year, version"
        ).df()
    codes = {
        sensor: sorted(group.version.dropna().astype(str).unique().tolist())
        for sensor, group in table.groupby("sensor")
    }
    modis = codes.get("MODIS", [])
    c61_codes_only = bool(modis) and all(code.startswith("61.") for code in modis)
    limitations = []
    if not c61_codes_only:
        limitations.append(
            f"MODIS source versions are {', '.join(modis) or 'unknown'}; "
            "a homogeneous Collection 6.1 historical record has not been verified."
        )
    report = {
        "reported_versions": codes,
        "modis_61_codes_only": c61_codes_only,
        "yearly_counts": table.to_dict(orient="records"),
        "limitations": limitations,
        "note": "Version codes do not establish upstream reprocessing or observation coverage.",
    }
    write_json(paths.reports / "source_versions.json", report)
    return report
