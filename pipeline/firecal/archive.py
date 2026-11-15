"""Download NASA FIRMS annual country archives with a verifiable manifest.

The public catalog supplies file names and byte sizes; no MAP_KEY is needed.
Only catalog entries are downloaded. Unpublished products/years remain explicit
gaps rather than being replaced with synthetic or near-real-time observations.
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.request import Request, urlopen

from firecal.io import write_json
from firecal.paths import DataPaths

log = logging.getLogger(__name__)
BASE = "https://firms.modaps.eosdis.nasa.gov/data/country"
CATALOG_URL = f"{BASE}/yearly_summary_files.txt"
PRODUCTS = {"modis": 2000, "viirs-snpp": 2012, "viirs-jpss1": 2018}
REQUIRED = {"latitude", "longitude", "acq_date", "acq_time", "satellite", "confidence"}


def select_files(catalog: str, country: str, start: int, end: int) -> list[dict]:
    """Select catalog entries and reject missing expected product-years."""
    if not re.fullmatch(r"[A-Za-z][A-Za-z_ -]*", country) or start > end:
        raise ValueError("Invalid country name or year range")
    selected = []
    for row in csv.DictReader(io.StringIO(catalog)):
        match = re.fullmatch(r"(modis|viirs-snpp|viirs-jpss1)_(\d{4})_(.+)\.csv", row["filename"])
        if not match:
            continue
        product, year, name = match.groups()
        if name == country and start <= int(year) <= end:
            selected.append(
                {**row, "product": product, "year": int(year), "size": int(row["size"])}
            )
    available = {(r["product"], r["year"]) for r in selected}
    missing = [
        f"{p}/{y}"
        for p, first in PRODUCTS.items()
        for y in range(max(start, first), end + 1)
        if (p, y) not in available
    ]
    if missing:
        raise ValueError(f"Country catalog is incomplete for {country}: {', '.join(missing)}")
    return sorted(selected, key=lambda r: (r["product"], r["year"]))


def fetch(url: str, target: Path, expected_size: int | None = None) -> Path:
    """Cache a complete download, retry transient failures, and publish atomically."""
    if target.exists() and target.stat().st_size > 0:
        if expected_size is None or target.stat().st_size == expected_size:
            return target
        raise ValueError(f"Cached {target.name} differs from the catalog; preserve and inspect it")
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(target.suffix + ".part")
    for attempt in range(8):
        try:
            request = Request(url, headers={"User-Agent": "FireCal/0.1 (NASA FIRMS research)"})
            with urlopen(request, timeout=30) as response, part.open("wb") as out:
                while chunk := response.read(1024 * 1024):
                    out.write(chunk)
            if expected_size is not None and part.stat().st_size != expected_size:
                raise ValueError(f"Incomplete {target.name}: expected {expected_size} bytes")
            part.replace(target)
            return target
        except (OSError, ValueError) as exc:
            if attempt == 7:
                raise RuntimeError(f"Download failed for {target.name}: {exc}") from exc
            log.warning("Retry %d for %s (%s)", attempt + 1, target.name, type(exc).__name__)
            time.sleep(min(2**attempt, 8))
    raise AssertionError("unreachable")


def inspect_csv(path: Path, expected_year: int) -> dict:
    """Validate archive structure/date coverage and record provenance statistics."""
    with path.open("rb") as raw:
        digest = hashlib.file_digest(raw, "sha256").hexdigest()
    count, first, last = 0, "9999", ""
    satellites: dict[str, int] = {}
    versions: dict[str, int] = {}
    months: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not REQUIRED.issubset(reader.fieldnames or []):
            raise ValueError(f"Unexpected CSV header in {path.name}")
        if "type" not in reader.fieldnames:
            raise ValueError(f"Annual standard archive has no type field: {path.name}")
        for row in reader:
            acquisition_date = date.fromisoformat(row["acq_date"])
            if acquisition_date.year != expected_year:
                raise ValueError(f"Date outside requested year in {path.name}: {acquisition_date}")
            date_text = acquisition_date.isoformat()
            lat, lon = float(row["latitude"]), float(row["longitude"])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError(f"Invalid coordinates in {path.name}")
            if "NRT" in row.get("version", "").upper():
                raise ValueError(f"NRT observation in standard archive {path.name}")
            first, last = min(first, date_text), max(last, date_text)
            count += 1
            months.add(date_text[:7])
            sat = row["satellite"]
            satellites[sat] = satellites.get(sat, 0) + 1
            version = row.get("version", "unknown")
            versions[version] = versions.get(version, 0) + 1
    return {
        "sha256": digest,
        "rows": count,
        "first_detection": first if count else None,
        "last_detection": last or None,
        "months_with_detections": sorted(months),
        "satellites": satellites,
        "reported_versions": versions,
    }


def download_archive(
    paths: DataPaths,
    country: str = "Indonesia",
    start: int = 2000,
    end: int = 2025,
    workers: int = 4,
    reuse_catalog: bool = False,
) -> dict:
    """Download complete published country-years and write a source manifest."""
    paths.ensure()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    cached_catalogs = sorted(paths.reference.glob("firms_catalog_*.txt"))
    catalog = (
        cached_catalogs[-1]
        if reuse_catalog and cached_catalogs
        else fetch(CATALOG_URL, paths.reference / f"firms_catalog_{stamp}.txt")
    )
    entries = select_files(catalog.read_text(encoding="utf-8"), country, start, end)
    log.info("Downloading %d files (%.1f MB)", len(entries), sum(e["size"] for e in entries) / 1e6)

    def one(entry: dict) -> dict:
        url = f"{BASE}/{entry['product']}/{entry['year']}/{entry['filename']}"
        target = paths.raw / country / entry["product"] / entry["filename"]
        fetch(url, target, entry["size"])
        result = {
            **entry,
            "url": url,
            "path": target.as_posix(),
            **inspect_csv(target, entry["year"]),
        }
        log.info("Verified %s: %s rows", target.name, f"{result['rows']:,}")
        return result

    files, errors = [], {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {pool.submit(one, entry): entry for entry in entries}
        for future in as_completed(pending):
            entry = pending[future]
            try:
                files.append(future.result())
            except (RuntimeError, ValueError) as exc:
                errors[entry["filename"]] = str(exc)
                log.error("Could not verify %s; continuing other files", entry["filename"])
    files.sort(key=lambda entry: (entry["product"], entry["year"]))
    manifest = {
        "country": country,
        "requested_years": [start, end],
        "downloaded_at": stamp,
        "catalog_url": CATALOG_URL,
        "catalog_path": catalog.as_posix(),
        "catalog_sha256": hashlib.sha256(catalog.read_bytes()).hexdigest(),
        "source": "NASA FIRMS annual country standard-processing CSV archives",
        "files": files,
        "rows": sum(f["rows"] for f in files),
        "bytes": sum(f["size"] for f in files),
        "complete": not errors,
        "errors": errors,
        "limitations": [
            "Coverage ends at the last downloaded annual archive; later dates are unavailable.",
            "NOAA-21 is absent from this public annual product catalog.",
            "Months without detections do not independently establish observation coverage.",
        ],
    }
    write_json(paths.reports / "archive_manifest.json", manifest)
    if errors:
        raise RuntimeError(f"{len(errors)} archive files failed; rerun to retry cached downloads")
    return manifest
