import time

import pytest

from app import series

# Five test AOIs of increasing size inside the test cube (T-37).
AOIS = [
    (103.0, -3.0, 105.0, -1.0),
    (102.0, -4.0, 106.0, 0.0),
    (101.0, -4.0, 107.0, 1.4),
    (101.0, -3.0, 110.5, 3.5),
    (104.0, -4.0, 113.0, 4.0),
]


@pytest.mark.parametrize("bounds", AOIS)
def test_calendar_p95_under_three_seconds(client, box, bounds) -> None:
    series._cache.clear()
    timings = []
    for _ in range(5):
        started = time.perf_counter()
        assert client.post("/calendar", json={"aoi": box(*bounds)}).status_code == 200
        timings.append(time.perf_counter() - started)
    assert max(timings) < 3.0  # p95 of 5 = the worst request, cold included


def test_repeated_queries_hit_the_cache(client, box) -> None:
    series._cache.clear()
    aoi = {"aoi": box(104, -2, 108, 2)}
    client.post("/calendar", json=aoi)
    assert len(series._cache) == 1
    # /stats and /export for the same AOI reuse the cached series
    client.post("/stats", json=aoi)
    client.post("/export", json={**aoi, "kind": "monthly"})
    assert len(series._cache) == 1


def test_get_endpoints_send_cache_headers(client) -> None:
    globe = client.get("/globe", params={"year": 2019, "month": 9})
    assert "max-age=3600" in globe.headers["cache-control"]
    assert "max-age=60" in client.get("/meta").headers["cache-control"]
