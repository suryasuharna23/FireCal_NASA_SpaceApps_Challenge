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
