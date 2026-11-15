import hashlib
import json
from dataclasses import asdict
from datetime import date, timedelta

import duckdb
import pytest

from firecal.acquire import inspect_payload
from firecal.global_data import WORLD, build_global, global_plan, three_months_before
from firecal.io import write_json


def availability():
    return [
        {"data_id": p + suffix, "min_date": first, "max_date": last}
        for p in ("MODIS", "VIIRS_SNPP", "VIIRS_NOAA20", "VIIRS_NOAA21")
        for suffix, first, last in (
            ("_SP", "2020-01-01", "2026-08-31"),
            ("_NRT", "2026-08-01", "2026-11-15"),
        )
    ]


def test_three_month_window_clamps_short_months():
    assert three_months_before(date(2026, 11, 15)) == date(2026, 8, 15)
    assert three_months_before(date(2024, 5, 31)) == date(2024, 2, 29)
    assert three_months_before(date(2026, 1, 31)) == date(2025, 10, 31)


def test_sp_priority_has_no_overlapping_days_and_reports_lag():
    sources = availability()
    for row in sources:
        if row["data_id"] == "VIIRS_SNPP_NRT":
            row["max_date"] = "2026-11-02"
    plan = global_plan(date(2026, 8, 15), date(2026, 11, 15), sources)
    coverage = {}
    for w in plan["windows"]:
        for offset in range(w.days):
            key = (w.source.rsplit("_", 1)[0], date.fromisoformat(w.start) + timedelta(days=offset))
            assert key not in coverage
            coverage[key] = w.source
    assert coverage["MODIS", date(2026, 8, 31)] == "MODIS_SP"
    assert coverage["MODIS", date(2026, 9, 1)] == "MODIS_NRT"
    assert ("VIIRS_SNPP", date(2026, 11, 3)) not in coverage
    assert plan["lagging_sources"] == [
        {"source": "VIIRS_SNPP_NRT", "available_through": "2026-11-02"}
    ]


def test_unavailable_dates_cannot_silently_become_zero():
    sources = availability()
    for row in sources:
        if row["data_id"] == "VIIRS_NOAA20_NRT":
            row["min_date"] = "2026-09-03"
    with pytest.raises(ValueError, match="cannot supply"):
        global_plan(date(2026, 8, 15), date(2026, 11, 15), sources)


@pytest.fixture
def global_inputs(tmp_path):
    root = tmp_path / "acquisition"
    plan = global_plan(date(2026, 8, 15), date(2026, 8, 15), availability())
    records = []
    for window in plan["windows"]:
        modis = window.source.startswith("MODIS")
        # Small provider-format fixtures; no generated production fallback.
        header = "latitude,longitude,acq_date,acq_time,satellite,version,confidence,frp"
        sat = (
            "T"
            if modis
            else {"VIIRS_SNPP_SP": "N", "VIIRS_NOAA20_SP": "1", "VIIRS_NOAA21_SP": "2"}[
                window.source
            ]
        )
        body = (header + f"\n40,-8,2026-08-15,1200,{sat},6.1,{'80' if modis else 'n'},5\n").encode()
        target = root / "responses" / window.source / window.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        records.append(
            {
                "request": asdict(window),
                "bbox": list(WORLD),
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                **inspect_payload(body.decode(), window, WORLD),
            }
        )
    write_json(root / "plan.json", {**plan, "windows": [asdict(w) for w in plan["windows"]]})
    write_json(root / "availability.json", availability())
    write_json(
        root / "responses/manifest.json",
        {
            "complete": True,
            "bbox": list(WORLD),
            "planned_windows": [asdict(w) for w in plan["windows"]],
            "records": records,
        },
    )
    return root


def test_real_format_rows_survive_points_and_hourly_grid(global_inputs, tmp_path):
    out = tmp_path / "processed"
    meta = build_global(global_inputs, out)
    assert meta["rows"] == 4
    assert meta["harmonized_available"] is False
    assert {p["satellite"] for p in meta["platforms"]} == {"Terra", "S-NPP", "NOAA-20", "NOAA-21"}
    with duckdb.connect() as con:
        assert con.execute(
            "SELECT sum(raw),sum(n_modis),sum(n_viirs) FROM read_parquet(?)",
            [str(out / "globe.parquet")],
        ).fetchone() == (4, 1, 3)
        assert (
            con.execute(
                "SELECT count(*) FROM read_parquet(?) WHERE weight IS NOT NULL",
                [str(out / "points/**/*.parquet")],
            ).fetchone()[0]
            == 0
        )
    assert json.loads((out / "provenance.json").read_text())["complete"]


def test_corrupt_raw_response_stops_publication(global_inputs, tmp_path):
    next((global_inputs / "responses").rglob("*.csv")).write_text("changed")
    with pytest.raises(ValueError, match="checksum"):
        build_global(global_inputs, tmp_path / "processed")


def test_global_refresh_replaces_covered_dates_and_failed_refresh_preserves_pointer(
    global_inputs, tmp_path
):
    from firecal.firms import KeyStatus
    from firecal.global_live import refresh_global
    from firecal.live import atomic_json, resolve_pointer

    repo = tmp_path / "repo"
    base = repo / "data/global/snapshots/base"
    meta = build_global(global_inputs, base)
    catalog = repo / "datasets/global/recent/dataset.json"
    write_json(catalog, {"data_version": meta["data_version"]})
    pointer = repo / "data/global/current.json"
    atomic_json(
        pointer,
        {
            "format": "firecal-live-v1",
            "processed": "snapshots/base",
            "base_data_version": meta["data_version"],
        },
    )

    class Client:
        def availability(self):
            return [{**r, "max_date": "2026-08-16"} for r in availability()]

        def key_status(self):
            return KeyStatus(5000, 0, "10 minutes")

        def area_csv(self, source, bbox, days, start):
            assert bbox == WORLD
            assert start == "2026-08-16" and days == 1 and source.endswith("_SP")
            satellite = {
                "MODIS_SP": "T",
                "VIIRS_SNPP_SP": "N",
                "VIIRS_NOAA20_SP": "1",
                "VIIRS_NOAA21_SP": "2",
            }[source]
            return (
                "latitude,longitude,acq_date,acq_time,satellite,version,confidence,frp\n"
                f"40,-8,{start},1200,{satellite},6.1,n,5\n"
            )

    refresh_global(repo, Client(), target=date(2026, 8, 16))
    current = resolve_pointer(pointer)
    updated = json.loads((current / "meta.json").read_text())
    assert updated["rows"] == 8
    assert updated["start_date"] == "2026-08-15"
    refresh_global(repo, Client(), target=date(2026, 8, 16))
    assert json.loads((resolve_pointer(pointer) / "meta.json").read_text())["rows"] == 8
    previous = pointer.read_bytes()

    class BrokenClient:
        def availability(self):
            raise RuntimeError("provider unreachable")

    with pytest.raises(RuntimeError, match="unreachable"):
        refresh_global(repo, BrokenClient(), target=date(2026, 8, 17))
    assert pointer.read_bytes() == previous
    assert json.loads((repo / "data/global/status.json").read_text())["status"] == "failed"


def test_empty_standard_response_removes_superseded_nrt_instead_of_falling_back(
    global_inputs, tmp_path
):
    from firecal.firms import KeyStatus
    from firecal.global_live import refresh_global
    from firecal.live import atomic_json, resolve_pointer

    repo = tmp_path / "repo"
    base = repo / "data/global/snapshots/base"
    meta = build_global(global_inputs, base)
    with duckdb.connect() as con:
        for path in (base / "points").rglob("*.parquet"):
            temporary = path.with_suffix(".updated.parquet")
            con.execute(
                "COPY (SELECT * REPLACE ('NRT' AS source,'6.1NRT' AS version) "
                f"FROM read_parquet('{path.as_posix()}')) "
                f"TO '{temporary.as_posix()}' (FORMAT parquet)"
            )
            temporary.replace(path)
    write_json(repo / "datasets/global/recent/dataset.json", {"data_version": meta["data_version"]})
    watermarks = {
        r["data_id"]: ("2026-08-14" if r["data_id"].endswith("_SP") else "2026-08-15")
        for r in availability()
    }
    pointer = repo / "data/global/current.json"
    atomic_json(
        pointer,
        {
            "format": "firecal-live-v1",
            "processed": "snapshots/base",
            "base_data_version": meta["data_version"],
            "watermarks": watermarks,
        },
    )

    class Standard:
        def availability(self):
            return [{**r, "max_date": "2026-08-15"} for r in availability()]

        def key_status(self):
            return KeyStatus(5000, 0, "10 minutes")

        def area_csv(self, source, *args):
            header = "latitude,longitude,acq_date,acq_time,satellite,version,confidence,frp\n"
            if source == "MODIS_SP":
                return header
            satellite = {"VIIRS_SNPP_SP": "N", "VIIRS_NOAA20_SP": "1", "VIIRS_NOAA21_SP": "2"}[
                source
            ]
            return header + f"40,-8,2026-08-15,1200,{satellite},6.1,n,5\n"

    refresh_global(repo, Standard(), target=date(2026, 8, 15))
    current = resolve_pointer(pointer)
    updated = json.loads((current / "meta.json").read_text())
    assert updated["rows"] == 3
    assert updated["provisional"] is False
    assert "Terra" not in {p["satellite"] for p in updated["platforms"]}


def test_nrt_is_refetched_when_observations_change_within_the_same_utc_day(global_inputs, tmp_path):
    from firecal.firms import KeyStatus
    from firecal.global_live import refresh_global
    from firecal.live import atomic_json, resolve_pointer

    repo = tmp_path / "repo"
    base = repo / "data/global/snapshots/base"
    meta = build_global(global_inputs, base)
    write_json(repo / "datasets/global/recent/dataset.json", {"data_version": meta["data_version"]})
    pointer = repo / "data/global/current.json"
    atomic_json(
        pointer,
        {
            "format": "firecal-live-v1",
            "processed": "snapshots/base",
            "base_data_version": meta["data_version"],
        },
    )

    class ChangingNASA:
        calls = 0
        revision = 1

        def availability(self):
            return [
                {**r, "max_date": "2026-08-15" if r["data_id"].endswith("_SP") else "2026-08-16"}
                for r in availability()
            ]

        def key_status(self):
            return KeyStatus(5000, 0, "10 minutes")

        def area_csv(self, source, bbox, days, start):
            assert source.endswith("_NRT") and start == "2026-08-16" and days == 1
            self.calls += 1
            sat = {
                "MODIS_NRT": "T",
                "VIIRS_SNPP_NRT": "N",
                "VIIRS_NOAA20_NRT": "1",
                "VIIRS_NOAA21_NRT": "2",
            }[source]
            header = "latitude,longitude,acq_date,acq_time,satellite,version,confidence,frp\n"
            return header + "".join(
                f"40,-8,{start},{1300 + i},{sat},6.1NRT,n,5\n" for i in range(self.revision)
            )

    provider = ChangingNASA()
    refresh_global(repo, provider, target=date(2026, 8, 16))
    assert json.loads((resolve_pointer(pointer) / "meta.json").read_text())["rows"] == 8
    provider.revision = 2
    refresh_global(repo, provider, target=date(2026, 8, 16))
    assert provider.calls == 8
    assert json.loads((resolve_pointer(pointer) / "meta.json").read_text())["rows"] == 12
