import pandas as pd
import pytest

from firecal.exposure_audit import daily_inventory, parse_missing_days


def payload(html, rows=1):
    return {"success": True, "html": html, "rowCount": rows}


def test_gap_columns_are_independent_lists_with_distinct_dates_and_modes():
    result = parse_missing_days(
        payload(
            "<tr><td>2026-05-01</td><td>Suomi NPP (VIIRS)</td>"
            "<td>2024-03-06</td><td>NOAA-21 (VIIRS)</td></tr>"
        )
    )
    assert result.to_dict("records") == [
        {"date": "2024-03-06", "satellite": "NOAA-21", "source_mode": "NRT"},
        {"date": "2026-05-01", "satellite": "S-NPP", "source_mode": "SP"},
    ]


@pytest.mark.parametrize(
    "bad",
    [
        {"success": False, "html": "", "rowCount": 0},
        payload("<tr><td>2026-05-01</td><td>Suomi NPP (VIIRS)</td></tr>"),
        payload("<tr><td>bad-date</td><td>Suomi NPP (VIIRS)</td><td></td><td></td></tr>"),
        payload("<tr><td>2026-05-01</td><td>unknown</td><td></td><td></td></tr>"),
        payload("", 1),
    ],
)
def test_failed_or_changed_table_cannot_be_read_as_no_gaps(bad):
    with pytest.raises(ValueError):
        parse_missing_days(bad)


def test_duplicate_gap_records_are_rejected():
    row = "<tr><td>2026-05-01</td><td>Suomi NPP (VIIRS)</td><td></td><td></td></tr>"
    with pytest.raises(ValueError, match="Duplicate"):
        parse_missing_days(payload(row + row, 2))


def test_listed_missing_day_with_detections_remains_unknown_exposure():
    daily = pd.DataFrame(
        {"date": ["2026-05-01"], "satellite": ["S-NPP"], "source": ["SP"], "n": [5]}
    )
    gaps = pd.DataFrame({"date": ["2026-05-01"], "satellite": ["S-NPP"], "source_mode": ["SP"]})
    availability = [
        {"data_id": "VIIRS_SNPP_SP", "min_date": "2012-01-20", "max_date": "2026-07-31"}
    ]
    result = daily_inventory(daily, gaps, availability, "2026-05-01", "2026-05-02")
    snpp = result[result.satellite == "S-NPP"].set_index("date")
    assert snpp.loc["2026-05-01", "evidence_state"] == "listed_missing_data_with_detections"
    assert snpp.loc["2026-05-02", "evidence_state"] == "no_retained_detections"
    assert result.valid_observation_exposure.eq("unknown").all()
    assert len(result) == 2 * 5


def test_other_processing_modes_are_not_conflated_and_cutoff_is_not_outage():
    daily = pd.DataFrame(
        {"date": ["2026-11-02"], "satellite": ["S-NPP"], "source": ["NRT"], "n": [5]}
    )
    gaps = pd.DataFrame({"date": ["2026-11-02"], "satellite": ["S-NPP"], "source_mode": ["SP"]})
    availability = [
        {"data_id": "VIIRS_SNPP_NRT", "min_date": "2026-08-01", "max_date": "2026-11-02"}
    ]
    result = daily_inventory(daily, gaps, availability, "2026-11-02", "2026-11-03")
    snpp = result[result.satellite == "S-NPP"].set_index("date")
    assert not snpp.loc["2026-11-02", "nasa_missing_data_day"]
    assert snpp.loc["2026-11-02", "other_mode_flags"] == "SP"
    assert snpp.loc["2026-11-03", "evidence_state"] == "outside_saved_availability"
    assert result.valid_observation_exposure.eq("unknown").all()


def test_empty_successful_table_does_not_establish_valid_observations():
    gaps = parse_missing_days(payload("", 0))
    daily = pd.DataFrame(columns=["date", "satellite", "source", "n"])
    availability = [
        {"data_id": "VIIRS_SNPP_SP", "min_date": "2012-01-20", "max_date": "2026-07-31"}
    ]
    result = daily_inventory(daily, gaps, availability, "2026-05-01", "2026-05-01")
    assert not result.nasa_missing_data_day.any()
    assert result.valid_observation_exposure.eq("unknown").all()


def test_exposure_runner_freezes_and_rechecks_serialized_paths(tmp_path, monkeypatch):
    """Exercise the file/SQL path with a tiny fixture, not real Indonesia data."""
    import hashlib
    import importlib.util
    import json
    from datetime import date
    from pathlib import Path

    script = Path(__file__).resolve().parents[2] / "scripts/audit_indonesia_exposure.py"
    spec = importlib.util.spec_from_file_location("exposure_runner", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    processed, acquisition, evidence, out = [tmp_path / n for n in ("p", "a", "e", "out")]
    (processed / "points").mkdir(parents=True)
    acquisition.mkdir()
    evidence.mkdir()
    (processed / "meta.json").write_text(
        json.dumps(
            {
                "data_version": "593ae2d95fdf",
                "coverage": {"snapshot_end": "2026-05-02"},
            }
        )
    )
    pd.DataFrame(
        {"acq_date": [date(2026, 5, 1)], "satellite": ["S-NPP"], "source": ["SP"], "year": [2026]}
    ).to_parquet(processed / "points/p.parquet")
    (acquisition / "availability.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "data_id": "VIIRS_SNPP_SP",
                        "min_date": "2012-01-20",
                        "max_date": "2026-07-31",
                    }
                ]
            }
        )
    )
    response = evidence / "response.json"
    response.write_text(
        json.dumps(
            payload("<tr><td>2026-05-01</td><td>Suomi NPP (VIIRS)</td><td></td><td></td></tr>")
        )
    )
    receipt = evidence / "receipt.json"
    receipt.write_text(
        json.dumps(
            {"http_status": 200, "sha256": hashlib.sha256(response.read_bytes()).hexdigest()}
        )
    )
    before = hashlib.sha256(response.read_bytes()).hexdigest()
    monkeypatch.setattr(
        "sys.argv",
        [
            str(script),
            "--processed",
            str(processed),
            "--acquisition",
            str(acquisition),
            "--response",
            str(response),
            "--retrieval",
            str(receipt),
            "--out",
            str(out),
        ],
    )
    module.main()
    report = json.loads((out / "exposure.json").read_text())
    assert report["flags_with_retained_detections"] == 1
    assert report["detections_on_flagged_days"] == 1
    assert report["exposure_fraction_estimated"] is False
    assert hashlib.sha256(response.read_bytes()).hexdigest() == before
    with pytest.raises(ValueError, match="previous exposure run"):
        module.main()
