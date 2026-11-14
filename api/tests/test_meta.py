import json


def test_meta_exposes_experimental_scope_and_reported_versions(client, data_dir, monkeypatch):
    from app.db import Dataset

    meta = json.loads((data_dir / "meta.json").read_text())
    meta.update(
        {
            "dataset_status": "experimental",
            "source_versions": {"MODIS": ["6.03", "61.03"]},
            "coverage": {"country": "Indonesia", "includes_nrt": False},
        }
    )
    monkeypatch.setattr(Dataset, "meta", lambda self, con=None: meta)
    body = client.get("/meta").json()
    assert body["dataset_status"] == "experimental"
    assert body["coverage"]["country"] == "Indonesia"
    assert body["source_versions"]["MODIS"] == ["6.03", "61.03"]
    assert "C6.1" not in body["attribution"]


def test_meta_reports_version_range_and_nrt(client, data_dir) -> None:
    body = client.get("/meta").json()
    meta = json.loads((data_dir / "meta.json").read_text())
    assert body["status"] == "ok"
    assert body["data_version"] == meta["data_version"]
    assert body["last_updated"] == meta["processed_at"]
    assert body["start_month"] == "2011-01" and body["end_month"] == "2020-12"
    assert body["nrt"]["provisional"] is False  # synthetic archive has no NRT rows
    assert body["nrt"]["provisional_months"] == []
    assert body["nrt"]["ok"] is True
    assert "NASA FIRMS" in body["attribution"]


def test_meta_flags_failed_nrt_run(client, data_dir) -> None:
    report = data_dir / "reports" / "nrt.json"
    report.write_text(
        json.dumps(
            {
                "run_at": "2026-11-14T02:00:00+00:00",
                "ok": False,
                "errors": {"MODIS_NRT": "HTTP 500"},
            }
        )  # fmt: skip
    )
    try:
        nrt = client.get("/meta").json()["nrt"]
    finally:
        report.unlink()
    assert nrt["ok"] is False
    assert nrt["errors"] == {"MODIS_NRT": "HTTP 500"}
    assert nrt["last_run"].startswith("2026-11-14")
