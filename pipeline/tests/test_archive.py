import io

import pytest

from firecal import archive

HEADER = "latitude,longitude,acq_date,acq_time,satellite,confidence,type,version\n"
ROW = "-2,104,2019-08-01,0130,N,nominal,0,1\n"


def test_catalog_requires_every_expected_product_year():
    catalog = "filename,size,updated\nmodis_2019_Indonesia.csv,100,today\n"
    with pytest.raises(ValueError, match="viirs-snpp/2019"):
        archive.select_files(catalog, "Indonesia", 2019, 2019)


def test_catalog_excludes_other_countries_and_unrequested_years():
    catalog = "filename,size,updated\n" + "\n".join(
        [
            "modis_2000_Indonesia.csv,100,today",
            "modis_2001_Indonesia.csv,110,today",
            "modis_2000_Malaysia.csv,120,today",
        ]
    )
    selected = archive.select_files(catalog, "Indonesia", 2000, 2000)
    assert [r["filename"] for r in selected] == ["modis_2000_Indonesia.csv"]


@pytest.mark.parametrize(
    "row,problem",
    [
        (ROW.replace("2019-08-01", "2020-08-01"), "outside requested year"),
        (ROW.replace("-2,104", "-92,104"), "Invalid coordinates"),
        (ROW.replace(",0,1", ",0,2.0NRT"), "NRT observation"),
    ],
)
def test_archive_rejects_invalid_observations(tmp_path, row, problem):
    path = tmp_path / "archive.csv"
    path.write_text(HEADER + row)
    with pytest.raises(ValueError, match=problem):
        archive.inspect_csv(path, 2019)


def test_archive_provenance(tmp_path):
    path = tmp_path / "archive.csv"
    path.write_text(HEADER + ROW)
    result = archive.inspect_csv(path, 2019)
    assert result["rows"] == 1
    assert result["satellites"] == {"N": 1}
    assert result["months_with_detections"] == ["2019-08"]
    assert len(result["sha256"]) == 64


def test_incomplete_download_never_becomes_an_archive(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, "urlopen", lambda *a, **kw: io.BytesIO(b"truncated"))
    monkeypatch.setattr(archive.time, "sleep", lambda _: None)
    target = tmp_path / "archive.csv"
    with pytest.raises(RuntimeError, match="Incomplete"):
        archive.fetch("https://example.test/file.csv", target, expected_size=100)
    assert not target.exists()


def test_corrupt_cached_archive_is_preserved(tmp_path):
    target = tmp_path / "archive.csv"
    target.write_bytes(b"original")
    with pytest.raises(ValueError, match="preserve and inspect"):
        archive.fetch("https://example.test/file.csv", target, expected_size=100)
    assert target.read_bytes() == b"original"
