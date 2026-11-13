import numpy as np
import pandas as pd
import pytest

AOIS = {
    "west": (101, -3, 105, 1),
    "centre": (104, -2, 108, 2),
    "east": (110, -1, 115.5, 3.5),
}


def _manual(client, box, bounds, ref=(2012, 2018), start="2013-01", end="2020-12") -> dict:
    payload = {"aoi": box(*bounds), "reference_years": list(ref)}
    full = pd.DataFrame(client.post("/calendar", json=payload).json()["months"])
    refd = full[(full.year >= ref[0]) & (full.year <= ref[1])]
    view = full[(full.year * 100 + full.month >= int(start.replace("-", ""))) & (
        full.year * 100 + full.month <= int(end.replace("-", "")))]  # fmt: skip
    med = refd.groupby("month").value.median()
    threshold = np.percentile(refd.value, 75)
    annual = view.groupby("year").value.sum()
    return {
        "median": med,
        "p25": refd.groupby("month").value.quantile(0.25),
        "p75": refd.groupby("month").value.quantile(0.75),
        "critical": sorted(int(m) for m in med.index if med[m] > threshold),
        "annual": annual,
        "peak_month": int(med.idxmax()),
        "max_year": int(annual.idxmax()),
        "total": view.value.sum(),
        "current": view.iloc[-1],
    }


@pytest.mark.parametrize("name", AOIS)
def test_stats_match_manual_calculation(client, box, name) -> None:
    bounds = AOIS[name]
    body = client.post(
        "/stats",
        json={
            "aoi": box(*bounds),
            "start": "2013-01",
            "end": "2020-12",
            "reference_years": [2012, 2018],
        },
    ).json()
    manual = _manual(client, box, bounds)

    for row in body["climatology"]:
        m = row["month"]
        assert row["median"] == pytest.approx(manual["median"][m], abs=0.02)
        assert row["p25"] == pytest.approx(manual["p25"][m], abs=0.02)
        assert row["p75"] == pytest.approx(manual["p75"][m], abs=0.02)
    assert body["critical_months"] == manual["critical"]
    assert [a["year"] for a in body["annual"]] == list(range(2013, 2021))
    for a in body["annual"]:
        assert a["total"] == pytest.approx(manual["annual"][a["year"]], abs=0.5)
    assert next(a for a in body["annual"] if a["rank"] == 1)["year"] == manual["max_year"]

    summary = body["summary"]
    assert summary["peak_month"] == manual["peak_month"]
    assert summary["max_year"] == manual["max_year"]
    assert summary["total"] == pytest.approx(manual["total"], abs=0.5)
    assert summary["current"]["month"] == "2020-12"
    assert summary["current"]["value"] == pytest.approx(manual["current"].value, abs=0.01)
    assert summary["current"]["anomaly_pct"] == pytest.approx(
        manual["current"].anomaly_pct, abs=0.1
    )


def test_reference_years_are_configurable(client, box) -> None:
    a = client.post("/stats", json={"aoi": box(104, -2, 108, 2), "reference_years": [2011, 2013]})
    b = client.post("/stats", json={"aoi": box(104, -2, 108, 2), "reference_years": [2017, 2020]})
    assert a.json()["reference_years"] == [2011, 2013]
    assert a.json()["climatology"] != b.json()["climatology"]


def test_current_year_line_uses_last_year_of_range(client, box) -> None:
    body = client.post("/stats", json={"aoi": box(104, -2, 108, 2), "end": "2020-06"}).json()
    current = [c["current"] for c in body["climatology"]]
    assert all(v is not None for v in current[:6]) and all(v is None for v in current[6:])
    assert body["annual"][-1] == {**body["annual"][-1], "year": 2020, "complete": False}
