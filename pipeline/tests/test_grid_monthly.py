import duckdb

from firecal.clean import clean
from firecal.grid import GridSpec, aggregate_monthly
from firecal.ingest import ingest
from firecal.schema import publish_points, read_sql


def test_monthly_grid_totals_match_points(paths) -> None:
    spec = GridSpec(0.25)
    ingest(paths)
    clean(paths)
    publish_points(paths, spec)
    report = aggregate_monthly(paths, spec)
    assert report["totals_match"]
    assert report["months"] == 120  # 2011-01 .. 2020-12

    con = duckdb.connect()
    grid = con.sql(f"SELECT * FROM read_parquet('{paths.grid_monthly.as_posix()}')").df()
    assert {"cell_id", "year", "month", "n_modis", "n_viirs"} <= set(grid.columns)
    assert not grid.duplicated(["cell_id", "year", "month"]).any()

    pts = con.sql(f"SELECT sensor, count(*) AS n FROM {read_sql(paths.points)} GROUP BY ALL").df()
    totals = dict(zip(pts.sensor, pts.n, strict=True))
    assert grid.n_modis.sum() == totals["MODIS"]
    assert grid.n_viirs.sum() == totals["VIIRS"]

    sats = grid.groupby(["year", "month"]).n_viirs_sats.max()
    assert sats.loc[(2011, 6)] == 0  # VIIRS starts 2012
    assert sats.loc[(2015, 6)] == 1  # S-NPP only
    assert sats.loc[(2019, 6)] == 2  # + NOAA-20
