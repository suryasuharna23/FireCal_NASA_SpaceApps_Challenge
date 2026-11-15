from dataclasses import dataclass

import pytest

from firecal.acquire import (
    QuotaGuard,
    RequestWindow,
    download_windows,
    inspect_payload,
    plan_windows,
    verify_receipts,
)
from firecal.firms import KeyStatus


def test_windows_intersect_availability_without_gaps_or_overlap():
    available = [{"data_id": "MODIS_SP", "min_date": "2026-01-03", "max_date": "2026-01-14"}]
    jobs = plan_windows("MODIS_SP", "2026-01-01", "2026-01-31", available)
    assert [(j.start, j.days) for j in jobs] == [
        ("2026-01-03", 5),
        ("2026-01-08", 5),
        ("2026-01-13", 2),
    ]


def test_quota_guard_waits_at_reserve_and_uses_observed_usage():
    class Client:
        values = iter([4700, 4800, 5, 19])

        def key_status(self):
            return KeyStatus(5000, next(self.values), "10 minutes")

    waits = []
    guard = QuotaGuard(Client(), sleep=waits.append, clock=lambda: 0)
    assert guard.before_request()["current_transactions"] == 5
    assert waits == [30, 30]
    guard.after_request()
    assert guard.largest_cost == 14


def test_payload_outside_window_is_rejected():
    with pytest.raises(ValueError, match="outside the requested dates"):
        inspect_payload(
            "latitude,longitude,acq_date\n-2,104,2026-01-06\n",
            RequestWindow("MODIS_SP", "2026-01-01", 5),
            (94, -12, 142, 7),
        )


def test_completed_response_is_reused_without_consuming_api_quota(tmp_path):
    @dataclass
    class Client:
        requests: int = 0

        def area_csv(self, *args):
            self.requests += 1
            return "latitude,longitude,acq_date,version\n-2,104,2026-01-01,61.03\n"

    class Guard:
        def before_request(self):
            return {"current_transactions": 0}

        def after_request(self):
            return {"current_transactions": 2}

    c = Client()
    args = (c, [RequestWindow("MODIS_SP", "2026-01-01", 5)], (94, -12, 142, 7), tmp_path)
    assert download_windows(*args, guard=Guard())["rows"] == 1
    assert download_windows(*args, guard=Guard())["rows"] == 1
    assert c.requests == 1
    csv = next(tmp_path.rglob("*.csv"))
    csv.write_text("corrupted")
    with pytest.raises(ValueError, match="Cached response changed"):
        download_windows(*args, guard=Guard())


def test_complete_flag_cannot_hide_an_omitted_request_window():
    jobs = [RequestWindow("MODIS_SP", "2026-01-01", 5)]
    manifest = {
        "complete": True,
        "bbox": [94, -12, 142, 7],
        "planned_windows": [{"source": "MODIS_SP", "start": "2026-01-01", "days": 5}],
        "records": [],
    }
    with pytest.raises(ValueError, match="complete requested"):
        verify_receipts(manifest, jobs, (94, -12, 142, 7))


def test_parallel_download_is_bounded_and_manifest_retains_date_order(tmp_path):
    import threading
    import time

    class Client:
        active = 0
        peak = 0
        lock = threading.Lock()

        def area_csv(self, source, bbox, days, start):
            with self.lock:
                self.active += 1
                self.peak = max(self.peak, self.active)
            time.sleep(0.02)
            with self.lock:
                self.active -= 1
            return f"latitude,longitude,acq_date\n-2,104,{start}\n"

    class Guard:
        def before_request(self):
            return {}

        def after_request(self):
            return {}

    client = Client()
    jobs = [RequestWindow("MODIS_SP", f"2026-01-{day:02}", 1) for day in range(1, 7)]
    report = download_windows(client, jobs, (94, -12, 142, 7), tmp_path, guard=Guard(), workers=3)
    verify_receipts(report, jobs, (94, -12, 142, 7))
    assert report["complete"] and report["rows"] == 6
    assert 1 < client.peak <= 3
