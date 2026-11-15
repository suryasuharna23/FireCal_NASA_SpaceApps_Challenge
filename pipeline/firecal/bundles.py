"""Install checksum-pinned repository data pieces without replacing existing work."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import zipfile
from pathlib import Path, PurePosixPath

log = logging.getLogger(__name__)
CATALOG = Path("datasets/indonesia/593ae2d95fdf/dataset.json")


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def verified_entries(archive: zipfile.ZipFile, version: str) -> list[str]:
    names = archive.namelist()
    manifests = [n for n in names if n.startswith("SNAPSHOT-MANIFEST-")]
    if len(manifests) != 1 or len(names) != len(set(names)):
        raise ValueError("Snapshot requires unique files and one manifest")
    manifest = json.loads(archive.read(manifests[0]))
    if manifest.get("data_version") != version:
        raise ValueError("Snapshot version does not match the catalog")
    records = {row["path"]: row for row in manifest["files"]}
    if len(records) != len(manifest["files"]) or set(names) != set(records) | {manifests[0]}:
        raise ValueError("Snapshot contents differ from the manifest")
    for name in names:
        path = PurePosixPath(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in name
            or ":" in name
            or (name not in manifests and (not path.parts or path.parts[0] != "data"))
        ):
            raise ValueError("Unsafe snapshot path")
        info = archive.getinfo(name)
        if info.is_dir() or (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError("Snapshot must contain regular files")
        if name in records:
            with archive.open(name) as stream:
                sha = hashlib.file_digest(stream, "sha256").hexdigest()
            if sha != records[name]["sha256"] or info.file_size != records[name]["bytes"]:
                raise ValueError("Snapshot file checksum/size mismatch")
    return names


def install_archive(path: Path, root: Path, version: str) -> int:
    """Verify everything and detect conflicts before extracting any file."""
    root = root.resolve()
    with zipfile.ZipFile(path) as archive:
        names = verified_entries(archive, version)
        pending = []
        for name in names:
            target = (root / name).resolve()
            if not target.is_relative_to(root):
                raise ValueError("Snapshot destination escapes repository")
            if target.exists():
                with archive.open(name) as stream:
                    sha = hashlib.file_digest(stream, "sha256").hexdigest()
                if not target.is_file() or digest(target) != sha:
                    raise ValueError("Existing dataset differs; preserve it before installing")
            else:
                pending.append((name, target))
        for name, target in pending:
            target.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation also prevents an intervening writer being overwritten.
            with archive.open(name) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
    return len(pending)


def download_asset(asset: dict, cache: Path, repo: Path | None = None) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / asset["file"]
    if target.exists():
        if target.stat().st_size != asset["bytes"] or digest(target) != asset["sha256"]:
            raise ValueError("Cached data archive differs from its pinned checksum")
        return target
    if asset.get("pieces"):
        if repo is None:
            raise ValueError("Repository path required to assemble included data")
        temporary = target.with_suffix(".zip.part")
        with temporary.open("wb") as output:
            for piece in asset["pieces"]:
                source = (repo / piece["path"]).resolve()
                if not source.is_relative_to(repo.resolve()):
                    raise ValueError("Data piece escapes repository")
                if source.stat().st_size != piece["bytes"] or digest(source) != piece["sha256"]:
                    raise ValueError("Repository data piece checksum/size mismatch")
                with source.open("rb") as stream:
                    shutil.copyfileobj(stream, output)
        if temporary.stat().st_size != asset["bytes"] or digest(temporary) != asset["sha256"]:
            raise ValueError("Assembled archive checksum/size mismatch")
        temporary.replace(target)
        return target
    supplied = Path.home() / "Downloads" / asset["file"]
    if supplied.is_file():
        if supplied.stat().st_size != asset["bytes"] or digest(supplied) != asset["sha256"]:
            raise ValueError("Supplied data archive checksum/size mismatch")
        shutil.copy2(supplied, target)
        return target
    raise ValueError("Place the supplied snapshot ZIPs in Downloads or data/interim/share")


def install_snapshot(root: Path, *, processed_only: bool = False) -> dict:
    root = root.resolve()
    catalog = json.loads((root / CATALOG).read_text(encoding="utf-8"))
    installed = []
    for asset in catalog["assets"]:
        if processed_only and asset["kind"] != "processed":
            continue
        log.info("Checking repository data asset: %s", asset["file"])
        path = download_asset(asset, root / "data/interim/share", root)
        count = install_archive(path, root, catalog["data_version"])
        installed.append({"kind": asset["kind"], "new_files": count})
    return {"data_version": catalog["data_version"], "installed": installed}
