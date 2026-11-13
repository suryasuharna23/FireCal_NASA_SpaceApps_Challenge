import json

import duckdb
import pandas as pd

from firecal.ingest import detect_sensor, discover, ingest


def _read(paths, sensor: str) -> pd.DataFrame:
    glob = (paths.detections / f"sensor={sensor}" / "**" / "*.parquet").as_posix()
    return duckdb.sql(f"SELECT * FROM read_parquet('{glob}', hive_partitioning = true)").df()


def test_detect_sensor_from_header() -> None:
    assert detect_sensor(["latitude", "longitude", "brightness", "bright_t31"]) == "MODIS"
    assert detect_sensor(["foo", "bar"]) is None


def test_discover_groups_modis_files(paths) -> None:
    groups = discover(paths.raw)
    assert groups["MODIS"]
    assert all(p.name.startswith("modis_") for p in groups["MODIS"])


def test_modis_ingest_matches_source_rows_per_year(paths) -> None:
    (report,) = [r for r in ingest(paths, ["MODIS"]) if r.sensor == "MODIS"]
    assert report.years_match
    assert sorted(report.written_rows) == list(range(2011, 2021))

    source = pd.concat(pd.read_csv(p) for p in sorted(paths.raw.rglob("modis_*.csv")))
    expected = source.drop_duplicates(
        ["latitude", "longitude", "acq_date", "acq_time", "satellite"]
    )
    assert sum(report.written_rows.values()) == len(expected)

    saved = json.loads((paths.reports / "ingest_modis.json").read_text())
    assert saved["years_match"] is True


def test_modis_schema_and_partitions(paths) -> None:
    ingest(paths, ["MODIS"])
    assert (paths.detections / "sensor=MODIS" / "year=2015").is_dir()
    df = _read(paths, "MODIS")
    assert set(df.satellite) == {"Terra", "Aqua"}
    assert set(df.source) == {"SP"}
    assert df.acq_datetime.dt.year.eq(df.year).all()
    assert {"latitude", "longitude", "confidence", "frp", "daynight", "type"} <= set(df.columns)


def test_ingest_is_reproducible(paths) -> None:
    ingest(paths, ["MODIS"])
    first = _read(paths, "MODIS")
    ingest(paths, ["MODIS"])
    pd.testing.assert_frame_equal(first, _read(paths, "MODIS"))


def test_viirs_ingest_keeps_satellite_and_normalizes_confidence(paths) -> None:
    reports = {r.sensor: r for r in ingest(paths)}
    viirs = reports["VIIRS"]
    assert viirs.years_match
    assert viirs.warnings == []
    df = _read(paths, "VIIRS")
    assert set(df.satellite) == {"S-NPP", "NOAA-20"}  # NOAA-21 starts 2024
    assert set(df.confidence) <= {"low", "nominal", "high"}
    first = pd.to_datetime(df.groupby("satellite").acq_date.min())
    assert first["NOAA-20"] >= pd.Timestamp("2018-04-01")
    assert df.instrument.eq("VIIRS").all()


def test_unknown_satellite_is_reported(tmp_path) -> None:
    from firecal.paths import DataPaths

    paths = DataPaths(tmp_path / "data").ensure()
    (paths.raw / "viirs.csv").write_text(
        "latitude,longitude,bright_ti4,acq_date,acq_time,satellite,confidence,version,frp,"
        "daynight\n1.0,100.0,330,2019-05-01,0130,X9,n,2,3.1,N\n"
    )
    (report,) = ingest(paths, ["VIIRS"])
    assert report.warnings and "X9" in report.warnings[0]
