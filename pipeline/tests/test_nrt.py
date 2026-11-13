import json

import duckdb
import httpx

from firecal.firms import FirmsClient
from firecal.ingest import ingest
from firecal.nrt import update

HEADER_V = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,"
    "confidence,version,bright_ti5,frp,daynight\n"
)
HEADER_M = (
    "latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,instrument,"
    "confidence,version,bright_t31,frp,daynight\n"
)


def _client(rows_by_source: dict[str, str], failing: set[str] = frozenset()) -> FirmsClient:
    def handler(request: httpx.Request) -> httpx.Response:
        source = request.url.path.split("/")[5]
        if source in failing:
            return httpx.Response(500, text="Internal error")
        header = HEADER_M if source.startswith("MODIS") else HEADER_V
        return httpx.Response(200, text=header + rows_by_source.get(source, ""))

    return FirmsClient("k" * 32, transport=httpx.MockTransport(handler))


ROWS = {
    # 2020-12-30 is before the last synthetic SP date (2020-12-31) -> replaced by SP
    "VIIRS_SNPP_NRT": (
        "1.1,110.1,330,0.4,0.4,2021-01-02,0545,N,VIIRS,n,2.0NRT,290,4.2,N\n"
        "1.2,110.2,331,0.4,0.4,2020-12-30,0545,N,VIIRS,n,2.0NRT,290,4.2,N\n"
    ),
    "VIIRS_NOAA20_NRT": "1.3,110.3,335,0.4,0.4,2021-01-03,1810,N20,VIIRS,h,2.0NRT,290,9.0,D\n",
    "MODIS_NRT": "1.4,110.4,320,1.0,1.0,2021-01-03,0230,T,MODIS,75,6.1NRT,295,12.5,N\n",
}


def _nrt(paths):
    return duckdb.sql(f"SELECT * FROM read_parquet('{paths.nrt.as_posix()}')").df()


def test_update_merges_sources_and_drops_dates_covered_by_sp(paths) -> None:
    ingest(paths)
    report = update(_client(ROWS), paths, (100, -4, 116, 4), 5)
    df = _nrt(paths)
    assert report.ok
    assert len(df) == 3
    assert report.replaced_by_sp == 1
    assert set(df.source) == {"NRT"}
    assert set(df.satellite) == {"S-NPP", "NOAA-20", "Terra"}
    assert df.type.isna().all()
    saved = json.loads((paths.reports / "nrt.json").read_text())
    assert saved["rows_after"] == 3 and len(saved["history"]) == 1


def test_update_is_idempotent(paths) -> None:
    ingest(paths)
    update(_client(ROWS), paths, (100, -4, 116, 4), 5)
    first = _nrt(paths)
    report = update(_client(ROWS), paths, (100, -4, 116, 4), 5)
    assert report.rows_before == report.rows_after == len(first)
    assert len(_nrt(paths)) == len(first)


def test_failed_source_keeps_existing_data(paths) -> None:
    ingest(paths)
    update(_client(ROWS), paths, (100, -4, 116, 4), 5)
    report = update(_client({}, failing={"MODIS_NRT", "VIIRS_SNPP_NRT"}), paths, (0, 0, 1, 1), 1)
    assert not report.ok
    assert set(report.errors) == {"MODIS_NRT", "VIIRS_SNPP_NRT"}
    assert len(_nrt(paths)) == 3
