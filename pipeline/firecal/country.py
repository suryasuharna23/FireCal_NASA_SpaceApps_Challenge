"""Country-filter FIRMS CSVs while preserving original files and provenance."""

import csv
import hashlib
from pathlib import Path

import pandas as pd
import shapely

from firecal.io import read_json, write_json


def file_sha(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def clip_csv(source: Path, target: Path, boundary, boundary_sha: str) -> dict:
    """Filter pixel centres with a fixed country polygon; cache only verified derivatives.

    Original coordinate/attribute strings are retained. This is geographic
    selection, not a claim that every excluded coastal pixel is a false detection.
    """
    source_sha = file_sha(source)
    sidecar = target.with_suffix(".json")
    old = read_json(sidecar)
    if target.exists():
        if (
            old.get("source_sha256") != source_sha
            or old.get("boundary_sha256") != boundary_sha
            or old.get("sha256") != file_sha(target)
        ):
            raise ValueError(f"Country-filter cache changed; preserve and inspect {target.name}")
        return old
    if source.stat().st_size == 0:
        return {
            "source": source.as_posix(),
            "source_sha256": source_sha,
            "rows": 0,
            "input_rows": 0,
            "path": None,
            "boundary_sha256": boundary_sha,
        }
    with source.open(newline="", encoding="utf-8-sig") as handle:
        fields = next(csv.reader(handle))
    if not {"latitude", "longitude", "acq_date"}.issubset(fields):
        raise ValueError(f"Not a FIRMS CSV: {source.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".part")
    total, kept = 0, 0
    first, last = None, None
    shapely.prepare(boundary)
    with temporary.open("w", newline="", encoding="utf-8") as out:
        csv.writer(out).writerow(fields)
        for frame in pd.read_csv(source, dtype=str, keep_default_na=False, chunksize=200_000):
            mask = shapely.intersects_xy(
                boundary, frame.longitude.to_numpy(float), frame.latitude.to_numpy(float)
            )
            selected = frame.loc[mask]
            total += len(frame)
            kept += len(selected)
            if len(selected):
                start, end = selected.acq_date.min(), selected.acq_date.max()
                first = min(first, start) if first else start
                last = max(last, end) if last else end
                selected.to_csv(out, header=False, index=False)
    temporary.replace(target)
    record = {
        "source": source.as_posix(),
        "source_sha256": source_sha,
        "boundary_sha256": boundary_sha,
        "sha256": file_sha(target),
        "path": target.as_posix(),
        "input_rows": total,
        "rows": kept,
        "excluded_by_country_polygon": total - kept,
        "first_detection": first,
        "last_detection": last,
    }
    write_json(sidecar, record)
    return record
