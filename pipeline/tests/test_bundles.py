import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from firecal.bundles import digest, download_asset, install_archive, verified_entries


def bundle(path, entries, *, version="fixture"):
    manifest = {
        "data_version": version,
        "files": [
            {"path": name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
            for name, body in entries.items()
        ],
    }
    with zipfile.ZipFile(path, "w") as z:
        for name, body in entries.items():
            z.writestr(name, body)
        z.writestr("SNAPSHOT-MANIFEST-processed.json", json.dumps(manifest))


def test_verified_install_is_idempotent_and_preserves_existing_data(tmp_path):
    archive = tmp_path / "data.zip"
    bundle(archive, {"data/processed/test.parquet": b"fixture"})
    root = tmp_path / "repo"
    assert install_archive(archive, root, "fixture") == 2
    assert install_archive(archive, root, "fixture") == 0
    (root / "data/processed/test.parquet").write_bytes(b"changed")
    with pytest.raises(ValueError, match="Existing dataset differs"):
        install_archive(archive, root, "fixture")
    assert (root / "data/processed/test.parquet").read_bytes() == b"changed"


@pytest.mark.parametrize(
    "name", ["../outside", "C:/outside", "data/../outside", "data\\outside", ".env"]
)
def test_unsafe_archive_paths_are_rejected_before_extracting(tmp_path, name):
    archive = tmp_path / "data.zip"
    bundle(archive, {name: b"content"})
    with pytest.raises(ValueError):
        install_archive(archive, tmp_path / "repo", "fixture")
    assert not (tmp_path / "repo").exists()


def test_archive_corruption_and_version_mismatch_are_rejected(tmp_path):
    archive = tmp_path / "data.zip"
    bundle(archive, {"data/p": b"content"})
    with zipfile.ZipFile(archive) as z, pytest.raises(ValueError, match="version"):
        verified_entries(z, "wrong")
    with zipfile.ZipFile(archive, "a") as z:
        z.writestr("data/extra", b"unlisted")
    with pytest.raises(ValueError, match="contents"):
        install_archive(archive, tmp_path / "repo", "fixture")


def test_cached_archive_hash_is_checked_even_without_network(tmp_path):
    path = tmp_path / "data.zip"
    path.write_bytes(b"content")
    asset = {
        "file": "data.zip",
        "bytes": 7,
        "sha256": digest(path),
        "url": "https://unused.invalid",
    }
    assert download_asset(asset, tmp_path) == path
    path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="Cached"):
        download_asset(asset, tmp_path)


def test_supplied_downloads_archive_is_verified_and_cached(tmp_path, monkeypatch):
    user = tmp_path / "user"
    supplied = user / "Downloads" / "fixture.zip"
    supplied.parent.mkdir(parents=True)
    supplied.write_bytes(b"verified fixture")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: user))
    asset = {"file": supplied.name, "bytes": supplied.stat().st_size, "sha256": digest(supplied)}
    result = download_asset(asset, tmp_path / "cache")
    assert result.read_bytes() == supplied.read_bytes()


def test_included_pieces_assemble_and_reject_tampering(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    source = repo / "one.chunk"
    source.write_bytes(b"included data")
    asset = {
        "file": "data.zip",
        "bytes": source.stat().st_size,
        "sha256": digest(source),
        "pieces": [{"path": source.name, "bytes": source.stat().st_size, "sha256": digest(source)}],
    }
    assert download_asset(asset, tmp_path / "cache", repo).read_bytes() == source.read_bytes()
    source.write_bytes(b"changed")
    with pytest.raises(ValueError, match="piece checksum"):
        download_asset(asset, tmp_path / "another-cache", repo)
