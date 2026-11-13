import pyarrow as pa

from firecal.clean import clean
from firecal.grid import GridSpec
from firecal.ingest import ingest
from firecal.schema import (
    POINT_SCHEMA,
    PUBLISHED_SCHEMA,
    check_schema,
    connect,
    publish_points,
)


def test_schema_covers_fr_d_06_attributes() -> None:
    required = {"latitude", "longitude", "acq_datetime", "daynight", "confidence", "frp"}
    assert required | {"sensor", "satellite"} <= set(POINT_SCHEMA.names)
    assert POINT_SCHEMA.field("frp").type == pa.float64()


def test_every_stage_uses_the_unified_schema(paths) -> None:
    ingest(paths)
    clean(paths)
    assert check_schema(paths.detections) == []  # sensor comes from the partition path
    assert check_schema(paths.clean) == []

    total = publish_points(paths, GridSpec(0.25))
    assert check_schema(paths.points, PUBLISHED_SCHEMA) == []

    con = connect(paths)
    by_sensor = dict(con.sql("SELECT sensor, count(*) FROM points GROUP BY ALL").fetchall())
    assert set(by_sensor) == {"MODIS", "VIIRS"}
    assert sum(by_sensor.values()) == total
    # cell ids computed in DuckDB agree with the NumPy encoder
    row = con.sql("SELECT latitude, longitude, cell_id FROM points LIMIT 1").fetchall()
    lat, lon, cell = row[0]
    assert GridSpec(0.25).cell_ids([lon], [lat])[0] == cell


def test_check_schema_reports_problems(tmp_path) -> None:
    import pyarrow.parquet as pq

    folder = tmp_path / "bad"
    folder.mkdir()
    pq.write_table(pa.table({"latitude": ["x"]}), folder / "part.parquet")
    problems = check_schema(folder)
    assert "latitude: expected double, got string" in problems
    assert "missing column frp" in problems
