"""Small I/O helpers shared by pipeline stages."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)


def download(url: str, dest: Path, *, timeout: float = 300.0) -> Path:
    """Download ``url`` to ``dest`` once; later calls reuse the cached file."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    log.info("Downloading %s", url)
    with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as response:
        response.raise_for_status()
        with tmp.open("wb") as fh:
            for chunk in response.iter_bytes():
                fh.write(chunk)
    tmp.replace(dest)
    return dest


def resolve_source(source: str, cache_dir: Path) -> Path:
    """Return a local path for ``source``, downloading it if it is a URL."""
    if source.startswith(("http://", "https://")):
        return download(source, cache_dir / source.rsplit("/", 1)[-1])
    return Path(source)


def reset_dir(path: Path) -> Path:
    """Remove and recreate ``path`` so reruns produce identical output (NFR-09)."""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}
