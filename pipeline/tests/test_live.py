"""Catch-up planning and complete version publication with an offline NASA fixture."""

import json
import shutil
from datetime import date, timedelta

import duckdb
import pandas as pd
import pytest
import shapely

from firecal.bundles import CATALOG, digest
from firecal.clean import clean
from firecal.firms import NRT_SOURCES, SP_SOURCES, FirmsError, KeyStatus
from firecal.grid import GridSpec, aggregate_monthly
from firecal.harmonize import HarmonizeConfig, calibrate, merge_series
from firecal.ingest import ingest
from firecal.io import read_json, write_json
from firecal.live import (
    atomic_json,
    catchup_plan,
    refresh,
    resolve_pointer,
    seed_pointer,
    update_lock,
)
from firecal.paths import DataPaths
from firecal.schema import publish_points
from firecal.synth import SynthConfig, generate


def availability(end="2025-01-20", snpp="2025-01-02"):
    return [
        {
            "data_id": s,
            "min_date": "2000-11-01" if s in SP_SOURCES else "2025-01-01",
            "max_date": "2024-12-31" if s in SP_SOURCES else snpp if "SNPP" in s else end,
        }
        for s in (*SP_SOURCES, *NRT_SOURCES)
    ]


def cursors():
    return dict.fromkeys([*SP_SOURCES, *NRT_SOURCES], "2024-12-31")


def test_full_gap_is_split_into_five_day_requests_with_platform_specific_coverage():
    plan = catchup_plan(cursors(), availability(), date(2025, 1, 20))
    assert len([w for w in plan["windows"] if w.source == "MODIS_NRT"]) == 4
    assert all(1 <= w.days <= 5 for w in plan["windows"])
    assert plan["watermarks"]["MODIS_NRT"] == "2025-01-20"
    assert plan["watermarks"]["VIIRS_SNPP_NRT"] == "2025-01-02"
    assert plan["lagging_sources"] == [
        {"source": "VIIRS_SNPP_NRT", "available_through": "2025-01-02"}
    ]


def test_unavailable_gap_is_reported_instead_of_silently_advancing():
    available = availability()
    for row in available:
        if row["data_id"] == "MODIS_NRT":
            row["min_date"] = "2025-01-05"
    plan = catchup_plan(cursors(), available, date(2025, 1, 20))
    assert plan["unavailable_gaps"] == [
        {"source": "MODIS_NRT", "start": "2025-01-01", "end": "2025-01-04"}
    ]


def test_new_standard_data_covers_retired_nrt_dates_before_planning_nrt():
    available = availability()
    for row in available:
        if row["data_id"] == "MODIS_SP":
            row["max_date"] = "2025-01-10"
        if row["data_id"] == "MODIS_NRT":
            row["min_date"] = "2025-01-11"
    plan = catchup_plan(cursors(), available, date(2025, 1, 20))
    assert not plan["unavailable_gaps"]
    assert min(w.start for w in plan["windows"] if w.source == "MODIS_NRT") == "2025-01-11"


@pytest.fixture(scope="module")
def seed(tmp_path_factory):
    root = tmp_path_factory.mktemp("live-seed")
    paths = DataPaths(root / "snapshot").ensure()
    generate(
        paths.raw / "synthetic",
        SynthConfig(bbox=(100, -4, 116, 4), start=(2011, 1), end=(2024, 12), clusters=4, seed=7),
    )
    spec = GridSpec()
    cfg = HarmonizeConfig(test_years=(2016, 2019))
    ingest(paths)
    clean(paths)
    publish_points(paths, spec)
    aggregate_monthly(paths, spec)
    coef = calibrate(paths, spec, cfg)
    meta = merge_series(paths, spec, cfg)
    pd.DataFrame({"cell_id": coef.cell_id, "biome": "lat:tropical"}).to_parquet(paths.cells)
    pd.DataFrame(
        {"name": ["test"], "geometry": [shapely.to_wkb(shapely.box(100, -4, 116, 4))]}
    ).to_parquet(paths.regions)
    write_json(
        paths.reports / "validation.json", {"limitations": ["fixture, not real observations"]}
    )
    return root, meta


@pytest.fixture
def repo(tmp_path, seed):
    source, meta = seed
    shutil.copytree(source / "snapshot/processed", tmp_path / "snapshot/processed")
    catalog = {
        "data_version": meta["data_version"],
        "processed": "snapshot/processed",
        "acquisition": "acquisition",
        "bbox": [94, -12, 142, 7],
    }
    write_json(tmp_path / CATALOG, catalog)
    for source in (*SP_SOURCES, *NRT_SOURCES):
        write_json(
            tmp_path / "acquisition/responses" / source / "manifest.json",
            {
                "complete": True,
                "records": [{"request": {"source": source, "start": "2024-12-31", "days": 1}}],
            },
        )
    boundary = tmp_path / "acquisition/reference/indonesia_10m.geojson"
    boundary.parent.mkdir(parents=True)
    boundary.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": shapely.geometry.mapping(shapely.box(100, -4, 116, 4)),
                    }
                ],
            }
        )
    )
    return tmp_path


class NASA:
    def __init__(self, *, empty=False, failed=None, end="2025-01-20"):
        self.empty, self.failed, self.end = empty, failed, end
        self.calls = []

    def availability(self):
        return availability(self.end)

    def key_status(self):
        return KeyStatus(5000, 0, "10 minutes")

    def area_csv(self, source, bbox, days, start):
        self.calls.append((source, start, days))
        if source == self.failed:
            raise FirmsError("simulated unavailable source")
        modis = source.startswith("MODIS")
        temp = "brightness" if modis else "bright_ti4"
        header = (
            f"latitude,longitude,{temp},acq_date,acq_time,satellite,"
            "confidence,version,frp,daynight,type\n"
        )
        if self.empty:
            return header
        satellite = (
            "T"
            if modis
            else {"VIIRS_SNPP_NRT": "N", "VIIRS_NOAA20_NRT": "N20", "VIIRS_NOAA21_NRT": "N21"}[
                source.replace("_SP", "_NRT")
            ]
        )
        conf, version = ("75", "6.1NRT") if modis else ("n", "2.0NRT")
        typ = ""
        if source in SP_SOURCES:
            version = "61.03" if modis else "2"
            typ = "0"
        rows = []
        for offset in range(days):
            day = (date.fromisoformat(start) + timedelta(days=offset)).isoformat()
            rows.extend(
                [
                    f"0.5,105.5,330,{day},1300,{satellite},{conf},{version},5,D,{typ}\n",
                    f"5,125,330,{day},1300,{satellite},{conf},{version},5,D,{typ}\n",
                ]
            )
        return header + "".join(rows)


def test_real_pipeline_update_keeps_snapshot_immutable_filters_country_and_publishes_pointer(repo):
    frozen = repo / "snapshot/processed"
    before = {p: digest(p) for p in frozen.rglob("*") if p.is_file()}
    nasa = NASA()
    result = refresh(repo, nasa, today=date(2025, 1, 20))
    current = resolve_pointer(repo / "data/live/current.json")
    meta = read_json(current / "meta.json")
    assert result["status"] == "updated" and meta["last_acq_date"].startswith("2025-01")
    assert current != frozen and digest(current / "coefficients.parquet") == digest(
        frozen / "coefficients.parquet"
    )
    assert all(digest(p) == value for p, value in before.items())
    assert read_json(repo / "data/live/current.json")["watermarks"]["MODIS_NRT"] == "2025-01-20"
    with duckdb.connect() as con:
        n = con.execute(
            "SELECT count(*) FROM "
            f"read_parquet('{current.as_posix()}/points/**/*.parquet',hive_partitioning=true) "
            "WHERE year=2025"
        ).fetchone()[0]
    assert n == sum(days for _, _, days in nasa.calls)


def test_zero_detections_advance_query_coverage_and_publish_zero_month(repo):
    result = refresh(repo, NASA(empty=True), today=date(2025, 1, 20))
    current = resolve_pointer(repo / "data/live/current.json")
    assert result["status"] == "updated"
    assert read_json(current / "meta.json")["end_month"] == "2025-01"
    assert read_json(repo / "data/live/current.json")["watermarks"]["MODIS_NRT"] == "2025-01-20"
    index = pd.read_parquet(current / "months.parquet")
    january = index[(index.year == 2025) & (index.month == 1)].iloc[0]
    assert january.total == 0 and january.has_nrt


def test_failed_source_does_not_publish_or_advance_cursors(repo):
    pointer = repo / "data/live/current.json"
    seed_pointer(repo, repo / "data/live")
    before = pointer.read_bytes()
    with pytest.raises(FirmsError):
        refresh(repo, NASA(failed="VIIRS_NOAA20_NRT"), today=date(2025, 1, 20))
    assert pointer.read_bytes() == before
    assert read_json(repo / "data/live/status.json")["status"] == "failed"


def test_misconfigured_live_location_never_writes_to_frozen_snapshot(repo):
    frozen = repo / "snapshot/processed"
    before = {p: digest(p) for p in frozen.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="overlaps"):
        refresh(repo, NASA(), live_root=frozen, today=date(2025, 1, 20))
    assert set(before) == {p for p in frozen.rglob("*") if p.is_file()}
    assert all(digest(p) == value for p, value in before.items())


def test_overlap_refresh_is_idempotent_and_standard_data_replace_nrt(repo):
    refresh(repo, NASA(), today=date(2025, 1, 20))
    first = resolve_pointer(repo / "data/live/current.json")

    def count(path, condition="true"):
        with duckdb.connect() as con:
            return con.execute(
                "SELECT count(*) FROM "
                f"read_parquet('{path.as_posix()}/points/**/*.parquet',hive_partitioning=true) "
                f"WHERE {condition}"
            ).fetchone()[0]

    before = count(first)
    refresh(repo, NASA(), today=date(2025, 1, 20))
    assert count(resolve_pointer(repo / "data/live/current.json")) == before

    class StandardArrived(NASA):
        def availability(self):
            rows = super().availability()
            for row in rows:
                if row["data_id"] == "MODIS_SP":
                    row["max_date"] = "2025-01-10"
            return rows

    refresh(repo, StandardArrived(), today=date(2025, 1, 20))
    latest = resolve_pointer(repo / "data/live/current.json")
    assert (
        count(latest, "sensor='MODIS' AND year=2025 AND acq_date<='2025-01-10' AND source='NRT'")
        == 0
    )
    assert (
        count(latest, "sensor='MODIS' AND year=2025 AND acq_date<='2025-01-10' AND source='SP'")
        == 10
    )


def test_pointer_resolution_and_lock_are_atomic_and_exclusive(tmp_path):
    data = tmp_path / "version/processed"
    write_json(data / "meta.json", {"data_version": "fixture"})
    pointer = tmp_path / "live/current.json"
    atomic_json(pointer, {"format": "firecal-live-v1", "processed": "../version/processed"})
    assert resolve_pointer(pointer) == data.resolve()
    with update_lock(tmp_path / "live"), pytest.raises(OSError), update_lock(tmp_path / "live"):
        pass
    with update_lock(tmp_path / "live"):
        pass


def test_live_startup_rejects_unverified_or_synthetic_pointer_without_fallback(tmp_path):
    write_json(tmp_path / CATALOG, {"data_version": "real-pinned", "processed": "frozen"})
    fake = tmp_path / "data/live/runs/fake/processed"
    write_json(fake / "meta.json", {"data_version": "synthetic"})
    pointer = tmp_path / "data/live/current.json"
    atomic_json(pointer, {"format": "firecal-live-v1", "processed": "runs/fake/processed"})
    before = pointer.read_bytes()
    with pytest.raises(ValueError, match="Unverified dataset rejected"):
        seed_pointer(tmp_path, tmp_path / "data/live")
    assert pointer.read_bytes() == before
