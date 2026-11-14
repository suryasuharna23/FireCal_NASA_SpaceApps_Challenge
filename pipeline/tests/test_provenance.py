import pandas as pd

from firecal.paths import DataPaths
from firecal.provenance import audit_source_versions


def test_mixed_modis_version_codes_do_not_claim_a_homogeneous_collection(tmp_path):
    paths = DataPaths(tmp_path).ensure()
    paths.detections.mkdir()
    pd.DataFrame(
        {
            "sensor": ["MODIS", "MODIS", "VIIRS"],
            "year": [2019, 2023, 2023],
            "version": ["6.03", "61.03", "2"],
        }
    ).to_parquet(paths.detections / "data.parquet")
    report = audit_source_versions(paths)
    assert report["reported_versions"]["MODIS"] == ["6.03", "61.03"]
    assert report["modis_61_codes_only"] is False
    assert "has not been verified" in report["limitations"][0]


def test_consistent_61_codes_still_preserve_the_original_processing_versions(tmp_path):
    paths = DataPaths(tmp_path).ensure()
    paths.detections.mkdir()
    pd.DataFrame(
        {
            "sensor": ["MODIS", "MODIS"],
            "year": [2023, 2024],
            "version": ["61.03", "61.03"],
        }
    ).to_parquet(paths.detections / "data.parquet")
    report = audit_source_versions(paths)
    assert report["modis_61_codes_only"] is True
    assert report["limitations"] == []
    assert len(report["yearly_counts"]) == 2
