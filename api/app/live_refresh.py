"""One background updater for a live API; requests keep reading the last good version."""

import logging
import threading
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from firecal.firms import FirmsClient
from firecal.live import atomic_json, refresh

log = logging.getLogger(__name__)


def refresh_once(settings):
    root = Path(settings.live_repo_root).resolve()
    secret = settings.firms_map_key.get_secret_value()
    if not secret or secret == "your_map_key_here":
        log.error("NASA live updates UNAVAILABLE: FIRMS_MAP_KEY is missing")
        atomic_json(
            root / "data/live/status.json",
            {
                "status": "missing_key",
                "detail": "Frozen data available; configure FIRMS_MAP_KEY for updates.",
            },
        )
        return
    try:
        with FirmsClient(secret, allow_mirror=False) as client:
            refresh(root, client)
    except Exception as exc:
        # Also cover failures before refresh() can write its own status. Never log
        # arbitrary exception text: provider URLs can contain credentials.
        atomic_json(
            root / "data/live/status.json",
            {
                "status": "failed",
                "checked_at": datetime.now(UTC).isoformat(),
                "error": type(exc).__name__,
                "detail": "NASA update failed. Last real data shown; freshness is unverified.",
            },
        )
        log.error("NASA refresh FAILED (%s); retaining last real observations", type(exc).__name__)


def live_lifespan(settings):
    @asynccontextmanager
    async def lifespan(app):
        stop = threading.Event()
        worker = None
        if settings.live_auto_refresh:

            def loop():
                while not stop.is_set():
                    refresh_once(settings)
                    if not stop.is_set():
                        refresh_global_once(settings)
                    if stop.wait(settings.live_refresh_seconds):
                        break

            worker = threading.Thread(target=loop, name="firecal-live-refresh", daemon=True)
            worker.start()
        try:
            yield
        finally:
            stop.set()
            # Do not block shutdown on a long provider request. Published data remain atomic.
            if worker:
                worker.join(timeout=1)

    return lifespan


def refresh_global_once(settings):
    from firecal.global_data import CATALOG
    from firecal.global_live import refresh_global

    root = Path(settings.live_repo_root).resolve()
    if not (root / CATALOG).exists():
        return
    status = root / "data/global/status.json"
    secret = settings.firms_map_key.get_secret_value()
    if not secret or secret == "your_map_key_here":
        atomic_json(status, {"status": "missing_key", "detail": "NASA access key is missing."})
        return
    try:
        with FirmsClient(secret, allow_mirror=False, timeout=120) as client:
            refresh_global(root, client)
    except Exception as exc:
        atomic_json(
            status,
            {
                "status": "failed",
                "checked_at": datetime.now(UTC).isoformat(),
                "error": type(exc).__name__,
                "detail": "Worldwide NASA update failed; freshness is unverified.",
            },
        )
        log.error("Global NASA refresh FAILED (%s)", type(exc).__name__)
