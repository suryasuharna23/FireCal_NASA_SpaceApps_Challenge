"""Checkpointed FIRMS API acquisition with an observed transaction-budget guard."""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import threading
import time
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from firecal.firms import SOURCES, FirmsClient, FirmsError, FirmsQuotaError
from firecal.io import read_json, write_json

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RequestWindow:
    source: str
    start: str
    days: int

    @property
    def filename(self) -> str:
        return f"{self.source}_{self.start}_{self.days}d.csv"


def plan_windows(
    source: str, start: str, end: str, availability: list[dict]
) -> list[RequestWindow]:
    """Intersect an inclusive date range with NASA availability and split into <=5 days."""
    if source not in SOURCES:
        raise ValueError(f"Unknown source {source}")
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if first > last:
        raise ValueError("Start must not exceed end")
    rows = [row for row in availability if row["data_id"] == source]
    if len(rows) != 1:
        raise ValueError(f"NASA does not report a unique availability range for {source}")
    first = max(first, date.fromisoformat(rows[0]["min_date"]))
    last = min(last, date.fromisoformat(rows[0]["max_date"]))
    windows = []
    while first <= last:
        days = min(5, (last - first).days + 1)
        windows.append(RequestWindow(source, first.isoformat(), days))
        first += timedelta(days=days)
    return windows


class QuotaGuard:
    """Check actual NASA usage before every uncached request, retaining a 500+ reserve.

    There is no assumption that one HTTP request equals one transaction. The
    guard also tracks the largest observed request cost and reserves twice that
    amount. NASA's own limit still applies if other clients share the same key.
    """

    def __init__(self, client: FirmsClient, *, sleep=time.sleep, clock=time.monotonic):
        self.client, self.sleep, self.clock = client, sleep, clock
        self.largest_cost = 0
        self._active: dict[int, int] = {}
        self._lock = threading.Lock()

    def before_request(self) -> dict:
        started = self.clock()
        while True:
            with self._lock:
                status = self.client.key_status()
                limit = min(status.transaction_limit, 5000)
                reserve = max(500, 2 * self.largest_cost)
                in_flight = (len(self._active) + 1) * max(50, self.largest_cost)
                if reserve + in_flight >= limit:
                    raise FirmsError("Request cost exceeds the budget; reduce the query window")
                if status.current_transactions + reserve + in_flight < limit:
                    self._active[threading.get_ident()] = status.current_transactions
                    return asdict(status)
            if self.clock() - started >= 660:
                raise FirmsError("Quota did not recover within 11 minutes; checkpoint is preserved")
            log.info(
                "Quota pause: %d/%d transactions; checking again in 30 seconds",
                status.current_transactions,
                limit,
            )
            self.sleep(30)

    def after_request(self) -> dict:
        with self._lock:
            status = self.client.key_status()
            before = self._active.pop(threading.get_ident(), None)
            if before is not None:
                # Concurrent requests make this a conservative cost estimate.
                self.largest_cost = max(self.largest_cost, status.current_transactions - before)
        return asdict(status)

    def cancel_request(self) -> None:
        with self._lock:
            self._active.pop(threading.get_ident(), None)


def verify_receipts(manifest: dict, windows: list[RequestWindow], bbox: tuple[float, ...]) -> None:
    """Reject incomplete/different request plans before filling calendar months."""
    expected = [asdict(window) for window in windows]
    if (
        not manifest.get("complete")
        or manifest.get("bbox") != list(bbox)
        or manifest.get("planned_windows") != expected
        or [record.get("request") for record in manifest.get("records", [])] != expected
    ):
        raise ValueError("API receipts do not cover the complete requested source/date plan")


def inspect_payload(text: str, window: RequestWindow, bbox: tuple[float, ...]) -> dict:
    """Validate dates and bounds; zero detections do not establish observation coverage."""
    reader = csv.DictReader(io.StringIO(text))
    if text.strip() and not {"latitude", "longitude", "acq_date"}.issubset(reader.fieldnames or []):
        raise ValueError("Unexpected FIRMS CSV columns")
    first = date.fromisoformat(window.start)
    last = first + timedelta(days=window.days - 1)
    versions, satellites = Counter(), Counter()
    dates = []
    west, south, east, north = bbox
    for row in reader:
        acquired = date.fromisoformat(row["acq_date"])
        if not first <= acquired <= last:
            raise ValueError("NASA returned a detection outside the requested dates")
        lat, lon = float(row["latitude"]), float(row["longitude"])
        if not (west <= lon <= east and south <= lat <= north):
            raise ValueError("NASA returned a detection outside the requested bbox")
        versions[row.get("version", "unknown")] += 1
        satellites[row.get("satellite", "unknown")] += 1
        dates.append(acquired.isoformat())
    return {
        "rows": len(dates),
        "first_detection": min(dates) if dates else None,
        "last_detection": max(dates) if dates else None,
        "versions": dict(versions),
        "satellites": dict(satellites),
        "columns": reader.fieldnames or [],
    }


def download_windows(
    client: FirmsClient,
    windows: list[RequestWindow],
    bbox: tuple[float, ...],
    out: Path,
    *,
    guard: QuotaGuard | None = None,
    workers: int = 1,
) -> dict:
    """Persist each successful response atomically; resume only checksum-verified cached windows.

    Store these bbox responses separately from country-filtered pipeline inputs.
    Neither the manifest nor errors contain credential-bearing request URLs.
    """
    out.mkdir(parents=True, exist_ok=True)
    if not 1 <= workers <= 4:
        raise ValueError("Use one to four bounded workers")
    guard = guard or QuotaGuard(client)
    records = []
    manifest_path = out / "manifest.json"
    manifest = {
        "bbox": list(bbox),
        "planned_windows": [asdict(w) for w in windows],
        "complete": False,
        "records": records,
        "limitations": [
            "Bbox responses require country filtering before joining the Indonesia dataset.",
            "A successful request or zero detections does not establish observation coverage.",
        ],
    }
    write_json(manifest_path, manifest)

    def one(window: RequestWindow) -> dict:
        target = out / window.source / window.filename
        sidecar = target.with_suffix(".json")
        record = read_json(sidecar)
        if target.exists() and record:
            matches = (
                record.get("request") == asdict(window)
                and record.get("bbox") == list(bbox)
                and record.get("sha256") == hashlib.sha256(target.read_bytes()).hexdigest()
            )
            if not matches:
                raise ValueError(f"Cached response changed; preserve and inspect {target.name}")
        elif target.exists():
            raise ValueError(f"Cached response has no receipt; preserve and inspect {target.name}")
        else:
            for attempt in range(2):
                before = guard.before_request()
                try:
                    text = client.area_csv(window.source, bbox, window.days, window.start)
                    break
                except FirmsQuotaError:
                    guard.cancel_request()
                    if attempt:
                        raise
                    log.info(
                        "NASA rejected a request at its quota limit; waiting one full interval"
                    )
                    # Use short steps so progress/cancellation remains possible.
                    for _ in range(20):
                        guard.sleep(30)
                except BaseException:
                    guard.cancel_request()
                    raise
            info = inspect_payload(text, window, bbox)
            body = text.encode("utf-8")
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_suffix(".part")
            temp.write_bytes(body)
            temp.replace(target)
            record = {
                "request": asdict(window),
                "bbox": list(bbox),
                "sha256": hashlib.sha256(body).hexdigest(),
                "bytes": len(body),
                "downloaded_at": datetime.now(UTC).isoformat(),
                "quota_before": before,
                "path": target.as_posix(),
                **info,
            }
            write_json(sidecar, record)
            # Preserve the response before a potentially failing quota-status request.
            record["quota_after"] = guard.after_request()
            write_json(sidecar, record)
        return record

    def safe_one(window: RequestWindow) -> dict:
        try:
            return one(window)
        finally:
            cancel = getattr(guard, "cancel_request", None)
            if cancel:
                cancel()

    completed = {}
    queued = iter(enumerate(windows))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {}

        def submit_next() -> None:
            item = next(queued, None)
            if item is not None:
                index, window = item
                pending[pool.submit(safe_one, window)] = (index, window)

        for _ in range(workers):
            submit_next()
        try:
            while pending:
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    index, window = pending.pop(future)
                    record = future.result()
                    completed[index] = record
                    records[:] = [completed[i] for i in sorted(completed)]
                    manifest["completed_windows"] = len(records)
                    write_json(manifest_path, manifest)
                    log.info(
                        "Checkpoint %d/%d: %s (%s detections)",
                        len(records),
                        len(windows),
                        window.filename,
                        f"{record['rows']:,}",
                    )
                    submit_next()
        except BaseException:
            for future in pending:
                future.cancel()
            raise
    manifest["complete"] = True
    manifest["rows"] = sum(record["rows"] for record in records)
    write_json(manifest_path, manifest)
    return manifest
