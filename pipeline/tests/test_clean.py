import duckdb
import pandas as pd

from firecal.clean import CleanConfig, clean
from firecal.ingest import ingest


def _points(paths) -> pd.DataFrame:
    glob = (paths.clean / "**" / "*.parquet").as_posix()
    return duckdb.sql(f"SELECT * FROM read_parquet('{glob}', hive_partitioning = true)").df()


def test_clean_drops_low_confidence_and_static_sources(paths) -> None:
    ingest(paths)
    report = clean(paths)
    df = _points(paths)

    assert df[df.sensor == "MODIS"].confidence.astype(int).ge(30).all()
    assert set(df[df.sensor == "VIIRS"].confidence) <= {"nominal", "high"}
    assert df.type.eq(0).all()
    assert report.static_bins > 0
    for sensor in ("MODIS", "VIIRS"):
        assert report.before[sensor] > report.after_confidence[sensor] > 0
        assert report.after_confidence[sensor] > report.after_static[sensor]
        assert report.after_static[sensor] == int((df.sensor == sensor).sum())
    assert (paths.reports / "clean.json").exists()


def test_thresholds_are_configurable(paths) -> None:
    ingest(paths)
    strict = clean(paths, CleanConfig(modis_min_confidence=80, viirs_confidence=("high",)))
    df = _points(paths)
    assert df[df.sensor == "MODIS"].confidence.astype(int).ge(80).all()
    assert set(df[df.sensor == "VIIRS"].confidence) == {"high"}
    loose = clean(paths)
    assert loose.after_static["MODIS"] > strict.after_static["MODIS"]


def test_nrt_rows_inside_static_mask_are_dropped(paths) -> None:
    ingest(paths)
    glob = f"{paths.detections.as_posix()}/**/*.parquet"
    flare = duckdb.sql(
        f"SELECT latitude, longitude FROM read_parquet('{glob}') WHERE type = 2 LIMIT 1"
    ).fetchall()[0]
    nrt = pd.DataFrame(
        {
            "latitude": [flare[0], 0.5],
            "longitude": [flare[1], 110.5],
            "acq_datetime": pd.to_datetime(["2020-12-30 01:30", "2020-12-30 01:30"]),
            "acq_date": pd.to_datetime(["2020-12-30", "2020-12-30"]).date,
            "daynight": "N",
            "confidence": "nominal",
            "frp": 5.0,
            "sensor": "VIIRS",
            "satellite": "NOAA-20",
            "instrument": "VIIRS",
            "version": "2.0NRT",
            "type": pd.array([pd.NA, pd.NA], dtype="Int32"),
            "source": "NRT",
            "year": 2020,
            "month": 12,
        }
    )
    paths.nrt.parent.mkdir(parents=True, exist_ok=True)
    nrt.to_parquet(paths.nrt, index=False)
    clean(paths)
    kept = _points(paths).query("source == 'NRT'")
    assert len(kept) == 1
    assert kept.longitude.iloc[0] == 110.5
