import gzip
import json
import time

import pandas as pd
import pytest


def test_globe_returns_positive_half_degree_cells(client, data_dir) -> None:
    res = client.get("/globe", params={"year": 2019, "month": 9})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["res"] == 0.5 and body["source"] == "VIIRS"
    assert body["count"] == len(body["cells"]) > 0
    assert all(v > 0 for _, _, v in body["cells"])
    assert all(((lon + 180 - 0.25) / 0.5).is_integer() for lon, _, _ in body["cells"])
    assert body["max"] == max(v for _, _, v in body["cells"])

    h = pd.read_parquet(data_dir / "harmonized.parquet")
    expected = h[(h.year == 2019) & (h.month == 9)].n_harmonized.sum()
    assert body["total"] == pytest.approx(expected, rel=1e-3)


def test_globe_raw_mode_shows_unconverted_counts(client) -> None:
    harm = client.get("/globe", params={"year": 2019, "month": 9}).json()
    raw = client.get("/globe", params={"year": 2019, "month": 9, "mode": "raw"}).json()
    assert raw["mode"] == "raw"
    assert raw["total"] > harm["total"] * 2  # raw VIIRS overcounts vs MODIS scale


def test_globe_is_small_and_fast(client) -> None:
    started = time.perf_counter()
    res = client.get(
        "/globe", params={"year": 2020, "month": 8}, headers={"Accept-Encoding": "gzip"}
    )
    assert time.perf_counter() - started < 1.0
    assert len(gzip.compress(json.dumps(res.json()).encode())) < 1_000_000
    assert res.json()["truncated"] is False


def test_globe_rejects_months_outside_data(client) -> None:
    assert client.get("/globe", params={"year": 2030, "month": 1}).status_code == 422


def test_globe_year_sums_months(client) -> None:
    annual = client.get("/globe", params={"year": 2019, "period": "year"}).json()
    monthly = [client.get("/globe", params={"year": 2019, "month": month}).json()
               for month in range(1, 13)]
    assert annual["period"] == "year"
    assert annual["total"] == pytest.approx(sum(m["total"] for m in monthly), abs=1)


def test_globe_daily_and_hourly_match_acquisition_window(client) -> None:
    daily = client.get("/globe", params={"year": 2019, "month": 9,
                                       "day": 15, "period": "day"})
    assert daily.status_code == 200, daily.text
    hourly = [client.get("/globe", params={"year": 2019, "month": 9,
                                         "day": 15, "hour": h, "period": "hour"}).json()
              for h in range(24)]
    assert daily.json()["total"] == pytest.approx(sum(h["total"] for h in hourly), abs=1)
    assert client.get("/globe", params={"year": 2019, "month": 2, "day": 30,
                                       "period": "day"}).status_code == 422
