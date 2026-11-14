"""Package or verify the local Indonesia snapshot without credentials or caches."""

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = Path("data/interim/indonesia-extended-20261114/processed")
VERSION = "593ae2d95fdf"


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def verify(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        manifests = [n for n in names if n.startswith("SNAPSHOT-MANIFEST-")]
        if len(manifests) != 1 or len(names) != len(set(names)):
            raise ValueError("Expected unique entries and one manifest")
        manifest = json.loads(archive.read(manifests[0]))
        if manifest["data_version"] != VERSION:
            raise ValueError("Unexpected dataset version")
        expected = {row["path"] for row in manifest["files"]}
        if set(names) != expected | {manifests[0]}:
            raise ValueError("Archive content does not match manifest")
        for row in manifest["files"]:
            name = PurePosixPath(row["path"])
            if name.is_absolute() or ".." in name.parts or "\\" in str(name):
                raise ValueError("Unsafe archive path")
            with archive.open(str(name)) as handle:
                actual = hashlib.file_digest(handle, "sha256").hexdigest()
            if actual != row["sha256"] or archive.getinfo(str(name)).file_size != row["bytes"]:
                raise ValueError(f"Checksum/size mismatch: {name}")
    print(f"Verified {len(expected)} files: {path.name}", flush=True)


def build(kind):
    processed = ROOT / SNAPSHOT
    meta = json.loads((processed / "meta.json").read_text())
    if meta["data_version"] != VERSION:
        raise ValueError("Unexpected dataset version")
    with duckdb.connect() as con:
        points = (processed / "points/**/*.parquet").as_posix()
        count = con.execute(f"SELECT count(*) FROM read_parquet('{points}')").fetchone()[0]
    if count != 7_716_551:
        raise ValueError(f"Unexpected retained point count: {count}")
    if kind == "processed":
        files = sorted(processed.rglob("*"))
    else:
        files = sorted((ROOT / "data/raw/Indonesia").rglob("*"))
        acquisition = ROOT / "data/interim/api-acquisition"
        for directory in ["responses", "reference"]:
            files += sorted((acquisition / directory).rglob("*"))
        files += [acquisition / n for n in ["plan.json", "availability.json", "progress.json"]]
        files += [
            ROOT / "data/processed/reports/archive_manifest.json",
            ROOT / "data/processed/regions.parquet",
            ROOT / "data/interim/regional-audit/selection_lock.json",
        ]
    files = sorted({p for p in files if p.is_file()})
    if any(p.suffix not in {".csv", ".json", ".parquet", ".png", ".geojson"} for p in files):
        raise ValueError("Unexpected file type in snapshot allowlist")
    manifest = {
        "data_version": VERSION,
        "kind": kind,
        "code_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "point_rows_in_processed_snapshot": count,
        "status": "experimental",
        "files": [
            {"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size, "sha256": digest(p)}
            for p in files
        ],
    }
    out = ROOT / "data/interim/share"
    out.mkdir(exist_ok=True)
    target = out / f"firecal-indonesia-{VERSION}-{kind}.zip"
    if target.exists():
        raise FileExistsError(f"Preserve existing package first: {target.name}")
    temporary = target.with_suffix(".zip.part")
    print(
        f"Packaging {len(files)} files ({sum(p.stat().st_size for p in files):,} bytes)", flush=True
    )
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
        archive.writestr(f"SNAPSHOT-MANIFEST-{kind}.json", json.dumps(manifest, indent=2))
    verify(temporary)
    temporary.replace(target)
    sha = digest(target)
    target.with_suffix(".zip.sha256").write_text(f"{sha}  {target.name}\n", encoding="utf-8")
    print(f"Ready: {target}\nBytes: {target.stat().st_size:,}\nSHA256: {sha}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--build", choices=["processed", "sources"])
    group.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        verify(args.verify)
    else:
        build(args.build)


if __name__ == "__main__":
    main()
