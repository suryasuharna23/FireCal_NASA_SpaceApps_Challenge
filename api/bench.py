"""Load test for the calendar endpoint (T-37, NFR-01).

Sends cold and warm (cached) requests for five test AOIs of increasing size and prints
p50/p95 latency per AOI. Target: p95 <= 3 s for AOIs up to 1,000,000 km².

Usage::

    uv run python api/bench.py --base http://localhost:8000 --repeat 10
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time

import httpx

# (name, west, south, east, north) — about 50k to 950k km² around Sumatra/Kalimantan.
AOIS = [
    ("50k km²", 103.0, -3.0, 105.0, -1.0),
    ("200k km²", 102.0, -4.0, 106.0, 0.0),
    ("500k km²", 101.0, -5.0, 107.4, 1.4),
    ("760k km²", 101.0, -3.0, 110.5, 3.5),
    ("950k km²", 105.6, -5.4, 114.4, 3.4),
]


def box(west: float, south: float, east: float, north: float) -> dict:
    ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
    return {"type": "Polygon", "coordinates": [ring]}


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, round(q * (len(ordered) - 1))))
    return ordered[k]


def run(base: str, repeat: int, target: float) -> bool:
    ok = True
    with httpx.Client(base_url=base, timeout=60) as client:
        print(f"{'AOI':<10} {'cold s':>8} {'warm p50':>9} {'warm p95':>9} {'cells':>6}")
        for name, *bounds in AOIS:
            body = {"aoi": box(*bounds)}
            started = time.perf_counter()
            res = client.post("/calendar", json=body)
            cold = time.perf_counter() - started
            res.raise_for_status()
            warm = []
            for _ in range(repeat):
                started = time.perf_counter()
                client.post("/calendar", json=body).raise_for_status()
                warm.append(time.perf_counter() - started)
            p95 = max(cold, percentile(warm, 0.95))
            ok &= p95 <= target
            print(
                f"{name:<10} {cold:8.3f} {statistics.median(warm):9.3f} "
                f"{percentile(warm, 0.95):9.3f} {res.json()['aoi']['cells']:6d}"
                f"{'' if p95 <= target else '  <-- over target'}"
            )
    print(f"\nTarget p95 <= {target:.1f}s: {'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--repeat", type=int, default=10)
    parser.add_argument("--target", type=float, default=3.0)
    args = parser.parse_args()
    sys.exit(0 if run(args.base, args.repeat, args.target) else 1)
