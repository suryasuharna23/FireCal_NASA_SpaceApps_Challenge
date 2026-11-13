"""Synthetic FIRMS archive generator for local development and tests.

Writes yearly CSVs with the exact column layout of FIRMS country/year downloads
(``modis_2019_synthetic.csv``, ``viirs-snpp_2019_synthetic.csv`` ...), so the real
pipeline can run end-to-end without a MAP_KEY or a multi-gigabyte archive request.

The truth model is simple and known, which makes harmonization testable:

* fire clusters with a seasonal cycle, inter-annual variability and a mild trend;
* MODIS (Terra from Nov 2000, Aqua from Jul 2002) observes ``Poisson(rate)``;
* each VIIRS satellite observes ``Poisson(rate * ratio)`` where ``ratio`` depends on
  the cluster's latitude zone (S-NPP 2012, NOAA-20 Apr 2018, NOAA-21 Jan 2024);
* static heat sources (gas flares, a volcano) and low-confidence noise are added
  so the cleaning stage has something to remove.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

MODIS_COLUMNS = [
    "latitude", "longitude", "brightness", "scan", "track", "acq_date", "acq_time",
    "satellite", "instrument", "confidence", "version", "bright_t31", "frp", "daynight", "type",
]  # fmt: skip
VIIRS_COLUMNS = [
    "latitude", "longitude", "bright_ti4", "scan", "track", "acq_date", "acq_time",
    "satellite", "instrument", "confidence", "version", "bright_ti5", "frp", "daynight", "type",
]  # fmt: skip

#: (file prefix, FIRMS satellite code, first available month)
PLATFORMS = {
    "Terra": ("modis", "Terra", (2000, 11)),
    "Aqua": ("modis", "Aqua", (2002, 7)),
    "S-NPP": ("viirs-snpp", "N", (2012, 1)),
    "NOAA-20": ("viirs-noaa20", "N20", (2018, 4)),
    "NOAA-21": ("viirs-noaa21", "N21", (2024, 1)),
}

#: True VIIRS-per-satellite / MODIS(Terra+Aqua) detection ratio by latitude zone.
ZONE_RATIO = {"tropical": 3.2, "subtropical": 2.6, "temperate": 2.2}


@dataclass(frozen=True)
class SynthConfig:
    bbox: tuple[float, float, float, float] = (95.0, -11.0, 141.0, 6.0)
    start: tuple[int, int] = (2000, 11)
    end: tuple[int, int] | None = None
    clusters: int = 120
    mean_rate: float = 6.0
    seed: int = 42


def _zone(lat: np.ndarray) -> np.ndarray:
    a = np.abs(lat)
    return np.where(a < 23.5, "tropical", np.where(a < 35, "subtropical", "temperate"))


def _months(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    out, (y, m) = [], start
    while (y, m) <= end:
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _rows(rng, lat, lon, n, year, month, sat_code, sensor, conf, typ, nrt=False):
    """Detections scattered around (lat, lon) with jitter and random time of day."""
    if n == 0:
        return None
    days = pd.Timestamp(year=year, month=month, day=1).days_in_month
    day = rng.integers(1, days + 1, n)
    hhmm = rng.choice([130, 245, 545, 605, 1350, 1440, 1730, 1815], n) + rng.integers(0, 14, n)
    dn = np.where((hhmm >= 600) & (hhmm < 1800), "D", "N")
    is_modis = sensor == "MODIS"
    jitter = 0.08 if typ == 0 else 0.002
    return {
        "latitude": np.round(lat + rng.normal(0, jitter, n), 4),
        "longitude": np.round(lon + rng.normal(0, jitter, n), 4),
        "b1": np.round(rng.normal(320 if is_modis else 340, 8, n), 2),
        "scan": np.round(rng.uniform(1, 2, n) if is_modis else rng.uniform(0.32, 0.6, n), 1),
        "track": np.round(rng.uniform(1, 1.5, n) if is_modis else rng.uniform(0.36, 0.6, n), 1),
        "acq_date": [f"{year:04d}-{month:02d}-{d:02d}" for d in day],
        "acq_time": hhmm,
        "satellite": sat_code,
        "instrument": sensor,
        "confidence": conf,
        "version": ("6.1NRT" if nrt else "6.1") if is_modis else ("2.0NRT" if nrt else "2"),
        "b2": np.round(rng.normal(295, 5, n), 2),
        "frp": np.round(rng.gamma(1.5, 12 if is_modis else 4, n), 2),
        "daynight": dn,
        "type": typ,
    }


def generate(out_dir: Path, cfg: SynthConfig = SynthConfig()) -> dict[str, int]:
    """Write synthetic FIRMS CSVs to ``out_dir``; returns row counts per file."""
    rng = np.random.default_rng(cfg.seed)
    today = date.today()
    end = cfg.end or (today.year, today.month)
    months = _months(cfg.start, end)
    west, south, east, north = cfg.bbox

    lat = rng.uniform(south, north, cfg.clusters)
    lon = rng.uniform(west, east, cfg.clusters)
    base = rng.gamma(2.0, cfg.mean_rate / 2, cfg.clusters)
    peak = np.where(lat < 0, rng.normal(9, 0.8, cfg.clusters), rng.normal(3, 0.8, cfg.clusters))
    ratio = np.array([ZONE_RATIO[z] for z in _zone(lat)]) * rng.lognormal(0, 0.08, cfg.clusters)
    year_factor = {y: rng.lognormal(0, 0.45) for y in range(cfg.start[0], end[0] + 1)}

    static = [  # (lat, lon, type, daily detections)
        (lat[0] + 0.5, lon[0] + 0.5, 2, 1.5),
        (lat[1] - 0.4, lon[1] + 0.3, 2, 1.0),
        (lat[2] + 0.2, lon[2] - 0.6, 1, 0.6),
    ]

    frames: dict[tuple[str, int], list[pd.DataFrame]] = {}

    def add(prefix, year, chunk, sensor):
        if chunk is None:
            return
        df = pd.DataFrame(chunk)
        names = MODIS_COLUMNS if sensor == "MODIS" else VIIRS_COLUMNS
        df.columns = names
        frames.setdefault((prefix, year), []).append(df)

    for year, month in months:
        season = 0.15 + np.exp(-0.5 * ((((month - peak) + 6) % 12 - 6) / 1.3) ** 2)
        trend = 1 + 0.01 * (year - 2000)
        rate = base * season * year_factor[year] * trend
        for prefix, code, first in PLATFORMS.values():
            if (year, month) < first:
                continue
            sensor = "MODIS" if prefix == "modis" else "VIIRS"
            # Terra and Aqua each see half of the combined MODIS rate.
            mult = 0.5 if sensor == "MODIS" else ratio
            counts = rng.poisson(rate * mult)
            for i in np.flatnonzero(counts):
                n = int(counts[i])
                if sensor == "MODIS":
                    conf = rng.integers(30, 101, n)
                else:
                    conf = rng.choice(["n", "h"], n, p=[0.8, 0.2])
                add(prefix, year, _rows(rng, lat[i], lon[i], n, year, month, code, sensor,
                                        conf, 0), sensor)  # fmt: skip
            # low-confidence noise that the cleaning step must drop
            n_noise = int(rng.poisson(cfg.clusters * 0.3))
            j = rng.integers(0, cfg.clusters, 1)[0]
            noise_conf = rng.integers(0, 30, n_noise) if sensor == "MODIS" else "l"
            add(prefix, year, _rows(rng, lat[j], lon[j], n_noise, year, month, code, sensor,
                                    noise_conf, 0), sensor)  # fmt: skip
            for s_lat, s_lon, s_type, per_day in static:
                n = int(rng.poisson(per_day * 30 * (0.5 if sensor == "MODIS" else 1)))
                conf = rng.integers(50, 101, n) if sensor == "MODIS" else "n"
                add(prefix, year, _rows(rng, s_lat, s_lon, n, year, month, code, sensor,
                                        conf, s_type), sensor)  # fmt: skip

    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for (prefix, year), parts in sorted(frames.items()):
        df = pd.concat(parts, ignore_index=True).sort_values(["acq_date", "acq_time"])
        path = out_dir / f"{prefix}_{year}_synthetic.csv"
        df.to_csv(path, index=False)
        written[path.name] = len(df)
    return written
