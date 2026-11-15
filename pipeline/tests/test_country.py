import csv

import pytest
import shapely

from firecal.country import clip_csv


def test_country_filter_keeps_attributes_and_reports_excluded_pixels(tmp_path):
    source, target = tmp_path / "source.csv", tmp_path / "filtered.csv"
    source.write_text(
        "latitude,longitude,acq_date,acq_time,version\n"
        "-2,104,2026-01-01,0015,61.03\n"
        "10,104,2026-01-01,0015,61.03\n"
    )
    original = source.read_bytes()
    record = clip_csv(source, target, shapely.box(100, -5, 110, 0), "boundary-v1")
    assert record["input_rows"] == 2 and record["rows"] == 1
    assert record["excluded_by_country_polygon"] == 1
    with target.open() as handle:
        row = next(csv.DictReader(handle))
    assert row["acq_time"] == "0015" and row["version"] == "61.03"
    assert source.read_bytes() == original
    assert b"\r" not in target.read_bytes()  # consistent header/body endings on Windows too
    assert clip_csv(source, target, shapely.box(100, -5, 110, 0), "boundary-v1") == record
    with pytest.raises(ValueError, match="cache changed"):
        clip_csv(source, target, shapely.box(100, -5, 110, 0), "different-boundary")


def test_empty_response_does_not_create_an_unreadable_pipeline_csv(tmp_path):
    source, target = tmp_path / "source.csv", tmp_path / "filtered.csv"
    source.write_text("")
    assert clip_csv(source, target, shapely.box(100, -5, 110, 0), "boundary")["rows"] == 0
    assert not target.exists()
