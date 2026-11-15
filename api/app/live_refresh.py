"""One background updater for a live API; requests keep reading the last good version."""

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from firecal.firms import FirmsClient
from firecal.live import atomic_json, refresh

log = logging.getLogger(__name__)


def refresh_once(settings):
    root = Path(settings.live_repo_root).resolve()
    secret = settings.firms_map_key.get_secret_value()
    if not secret or secret == "your_map_key_here":
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
    except Exception:
        # The updater records a credential-free failure; the API keeps the last version.
        log.warning("Live NASA refresh did not complete; retaining the previous dataset")


def live_lifespan(settings):
    @asynccontextmanager
    async def lifespan(app):
        stop = threading.Event()
        worker = None
        if settings.live_auto_refresh:

            def loop():
                while not stop.is_set():
                    refresh_once(settings)
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
