"""Run the frozen training-only selection protocol and out-of-time evaluation."""

import argparse
import hashlib
import itertools
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import shapely

from app.aoi import Grid
from firecal.config import get_settings
from firecal.io import read_json, write_json
from firecal.overlap import region_of
from firecal.provenance import audit_source_versions
from firecal.regional import Candidate, fit_ratios
from firecal.validate import _metrics

TRAIN = [2013, 2014, 2015, 2017, 2018, 2020, 2021]
KNOWN = [2016, 2019]
FUTURE = [2022, 2023, 2024, 2025]
BASELINE = Candidate()


def sha(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def matrices(con, source: Path, years: list[int], ids: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Read only the requested years; never expose evaluation outcomes to selection."""
    markers = ",".join("?" for _ in years)
    data = con.execute(
        f"SELECT cell_id,year,month,n_modis,n_viirs/n_viirs_sats::DOUBLE AS v "
        f"FROM read_parquet('{source.as_posix()}') "
        f"WHERE year IN ({markers}) AND n_viirs_sats > 0",
        years,
    ).df()
    present = {(int(y), int(m)) for y, m in zip(data.year, data.month, strict=True)}
    if present != {(y, m) for y in years for m in range(1, 13)}:
        raise ValueError("Missing sensor-months in the requested evaluation/training years")
    row = data.year.map({year: i for i, year in enumerate(years)}).to_numpy() * 12
    row += data.month.to_numpy() - 1
    col = pd.Index(ids).get_indexer(data.cell_id)
    if (col < 0).any():
        raise ValueError("Baseline coefficient support does not cover the grid")
    m = np.zeros((12 * len(years), len(ids)))
    v = np.zeros_like(m)
    np.add.at(m, (row, col), data.n_modis.to_numpy())
    np.add.at(v, (row, col), data.v.to_numpy())
    return m, v


def metrics(observed: np.ndarray, predicted: np.ndarray) -> dict:
    result = _metrics(observed, predicted)
    result["meets_target"] = bool(
        result["r"] is not None and result["r"] >= 0.9 and abs(result["bias"]) <= 0.1
    )
    return result


def score(observed: np.ndarray, predicted: np.ndarray, eligible: np.ndarray) -> dict:
    scores = [metrics(observed[:, i], predicted[:, i]) for i in np.flatnonzero(eligible)]
    return {
        "macro_nmae": float(
            np.mean(
                [
                    s["mae"] / observed[:, i].mean()
                    for i, s in zip(np.flatnonzero(eligible), scores, strict=True)
                ]
            )
        ),
        "macro_abs_bias": float(np.mean([abs(s["bias"]) for s in scores])),
        "pass_fraction": float(np.mean([s["meets_target"] for s in scores])),
        "provinces": len(scores),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--annotate-metadata",
        action="store_true",
        help="Add limitations to serving metadata without changing calibrated values.",
    )
    args = parser.parse_args()
    settings = get_settings()
    paths = settings.paths
    out = paths.interim / "regional-audit"
    out.mkdir(parents=True, exist_ok=True)
    protocol = Path("docs/regional-audit-protocol.md")
    coef = pd.read_parquet(paths.coefficients).sort_values("cell_id")
    ids = coef.cell_id.to_numpy()
    provinces = pd.read_parquet(paths.regions).query("level == 1").sort_values("name")
    names = provinces.name.tolist()
    weights = np.zeros((len(ids), len(provinces)))
    for i, geometry in enumerate(provinces.geometry):
        w = Grid(settings.grid_res_deg).cell_weights(shapely.from_wkb(geometry))
        rows = pd.Index(ids).get_indexer(w.cell_id)
        hit = rows >= 0
        weights[rows[hit], i] = w.w.to_numpy()[hit]
    latitude = region_of(paths, settings.grid, ids).astype(str)
    admin = latitude.astype(object).copy()
    has_province = weights.max(axis=1) > 0
    admin[has_province] = np.asarray(names)[weights[has_province].argmax(axis=1)]
    groups = {"latitude": latitude, "province": admin.astype(str)}
    candidates = [BASELINE] + [
        c
        for region, a, balance in itertools.product(
            ("latitude", "province"), (0, 25, 100, 400), (False, True)
        )
        if (c := Candidate(region, a, balance)) != BASELINE
    ]
    source_sha = sha(paths.grid_monthly)
    protocol_sha = sha(protocol)

    with duckdb.connect() as con:
        m, v = matrices(con, paths.grid_monthly, TRAIN, ids)
        observed = m @ weights
        eligible = observed.sum(axis=0) >= 1000
        if not eligible.any():
            raise ValueError("No provinces meet the frozen training-volume threshold")
        records = []
        for candidate in candidates:
            predicted = np.zeros_like(observed)
            for fold in range(len(TRAIN)):
                test = np.repeat(np.arange(len(TRAIN)) == fold, 12)
                k = fit_ratios(m[~test], v[~test], groups[candidate.region], candidate)
                predicted[test] = (v[test] * k) @ weights
            result = {"candidate": asdict(candidate), **score(observed, predicted, eligible)}
            records.append(result)
            print(candidate.name, result, flush=True)
        base_score = records[0]
        best = min(records, key=lambda r: r["macro_nmae"])
        accepted = (
            best["macro_nmae"] <= base_score["macro_nmae"] * 0.95
            and best["macro_abs_bias"] <= base_score["macro_abs_bias"]
            and best["pass_fraction"] >= base_score["pass_fraction"]
        )
        selected = Candidate(**best["candidate"]) if accepted else BASELINE
        lock = {
            "source_sha256": source_sha,
            "protocol_sha256": protocol_sha,
            "training_years": TRAIN,
            "known_regression_years": KNOWN,
            "untouched_evaluation_years": FUTURE,
            "eligible_provinces": np.asarray(names)[eligible].tolist(),
            "selected": asdict(selected),
            "candidate_accepted_by_training_rule": accepted,
            "cv": records,
            "baseline_cv": base_score,
            "best_cv": best,
        }
        lock_path = out / "selection_lock.json"
        if lock_path.exists():
            old = read_json(lock_path)
            if any(
                old[key] != lock[key]
                for key in ("source_sha256", "protocol_sha256", "selected", "eligible_provinces")
            ):
                raise ValueError("Existing selection lock differs; create a new audit version")
            lock = old
        else:
            lock["locked_at"] = datetime.now(UTC).isoformat()
            write_json(lock_path, lock)
        print("SELECTION LOCKED before out-of-time read:", selected.name, flush=True)

        baseline_k = fit_ratios(m, v, latitude, BASELINE)
        np.testing.assert_allclose(baseline_k, coef.k.to_numpy(), rtol=1e-12)
        selected_k = fit_ratios(m, v, groups[selected.region], selected)
        coefficient_table = pd.DataFrame(
            {
                "cell_id": ids,
                "group": groups[selected.region],
                "baseline_k": baseline_k,
                "candidate_k": selected_k,
                "training_modis": m.sum(axis=0),
                "training_viirs_per_sat": v.sum(axis=0),
            }
        )
        coefficient_table.to_parquet(out / "candidate_coefficients.parquet", index=False)

        training_fit = []
        for i, name in enumerate(names):
            training_fit.append(
                {
                    "province": name,
                    "eligible": bool(eligible[i]),
                    "original": metrics(observed[:, i], ((v * baseline_k) @ weights)[:, i]),
                    "without_shrinkage": metrics(
                        observed[:, i],
                        ((v * fit_ratios(m, v, latitude, Candidate(shrinkage=0))) @ weights)[:, i],
                    ),
                }
            )
        write_json(out / "training_diagnostics.json", {"province_training_fit": training_fit})

        rows = []
        for period, years in (("known_holdout", KNOWN), ("out_of_time", FUTURE)):
            test_m, test_v = matrices(con, paths.grid_monthly, years, ids)
            for model, k in (("baseline", baseline_k), ("candidate", selected_k)):
                obs, pred = test_m @ weights, (test_v * k) @ weights
                monthly = []
                for i, name in enumerate(names):
                    rows.append(
                        {
                            "period": period,
                            "model": model,
                            "area": name,
                            "eligible": bool(eligible[i]),
                            **metrics(obs[:, i], pred[:, i]),
                        }
                    )
                    for j in range(len(years) * 12):
                        monthly.append(
                            {
                                "area": name,
                                "year": years[j // 12],
                                "month": j % 12 + 1,
                                "observed": obs[j, i],
                                "predicted": pred[j, i],
                            }
                        )
                rows.append(
                    {
                        "period": period,
                        "model": model,
                        "area": "Indonesia",
                        "eligible": True,
                        **metrics(test_m.sum(axis=1), (test_v * k).sum(axis=1)),
                    }
                )
                pd.DataFrame(monthly).to_csv(out / f"{period}_{model}_monthly.csv", index=False)
                for j, year in enumerate(years):
                    for i, name in enumerate(names):
                        part = slice(j * 12, (j + 1) * 12)
                        rows.append(
                            {
                                "period": f"{period}_{year}",
                                "model": model,
                                "area": name,
                                "eligible": bool(eligible[i]),
                                **metrics(obs[part, i], pred[part, i]),
                            }
                        )
        result = pd.DataFrame(rows)
        result.to_csv(out / "evaluation.csv", index=False)
        write_json(
            out / "audit.json",
            {
                "selection": lock,
                "evaluation": rows,
                "serving_dataset_changed": False,
                "limitations": [
                    "2016/2019 results were known before this audit; they are regression checks.",
                    "Administrative groups are calibration strata, not ecological biomes.",
                    "Detection counts do not establish observation exposure or true fire counts.",
                    "Candidate intervals have not been calibrated or evaluated.",
                ],
            },
        )
        selected_rows = result[
            result.area.isin(["Indonesia", "Riau", "Sumatera Selatan", "Kalimantan Tengah"])
            & result.period.isin(["known_holdout", "out_of_time"])
        ]
        print(selected_rows.to_string(index=False), flush=True)
        normalization = (
            con.execute(
                f"""WITH p AS (
                SELECT year, month,
                    count(*) FILTER (WHERE sensor='MODIS') AS m,
                    count(*) FILTER (WHERE sensor='VIIRS') AS v,
                    count(DISTINCT satellite) FILTER (WHERE sensor='VIIRS') AS sats
                FROM read_parquet('{paths.points.as_posix()}/**/*.parquet') GROUP BY ALL
            ), g AS (
                SELECT year, month, sum(n_modis) AS m, sum(n_viirs) AS v,
                    max(n_viirs_sats) AS sats
                FROM read_parquet('{paths.grid_monthly.as_posix()}') GROUP BY ALL
            ) SELECT count(*) AS checked_months, count(*) FILTER (
                WHERE p.m IS DISTINCT FROM g.m OR p.v IS DISTINCT FROM g.v
                   OR p.sats IS DISTINCT FROM g.sats
            ) AS mismatch_months FROM p FULL JOIN g USING(year,month)"""
            )
            .df()
            .iloc[0]
            .to_dict()
        )
        if normalization["mismatch_months"]:
            raise ValueError("Satellite normalization does not reconcile with the raw points")
        write_json(
            out / "coverage_checks.json",
            {
                "reconciliation": normalization,
                "note": "Detection days do not establish valid satellite observation exposure.",
            },
        )
        provenance = audit_source_versions(paths)
        write_json(out / "source_versions.json", provenance)
        if args.annotate_metadata:
            meta = read_json(paths.meta)
            meta["source_versions"] = provenance["reported_versions"]
            meta["sources"] = "NASA FIRMS MODIS annual archives and VIIRS 375 m"
            meta["dataset_status"] = "experimental"
            coverage = meta.get("coverage") or {}
            coverage["limitations"] = list(
                dict.fromkeys(coverage.get("limitations", []) + provenance["limitations"])
            )
            meta["coverage"] = coverage
            write_json(paths.meta, meta)
            validation = read_json(paths.reports / "validation.json")
            known_rows = [
                row
                for row in rows
                if row["period"] == "known_holdout"
                and row["model"] == "baseline"
                and row["area"] != "Indonesia"
            ]
            validation["administrative_regions"] = {
                row["area"]: {
                    "after": {key: row[key] for key in ("r", "bias", "mae", "months")},
                    "meets_target": row["meets_target"],
                    "eligible": row["eligible"],
                }
                for row in known_rows
            }
            future_rows = [
                row for row in rows if row["period"] == "out_of_time" and row["model"] == "baseline"
            ]
            validation["out_of_time"] = {"years": FUTURE, "areas": future_rows}
            validation["source_version_audit"] = provenance
            new_limits = [
                f"Temporal audit 2022-2025 {r['area']}: r={r['r']:.4f}, "
                f"bias={r['bias']:+.2%} misses the regional target."
                for r in future_rows
                if r["eligible"] and not r["meets_target"] and r["r"] is not None
            ]
            old_limits = [
                text
                for text in validation.get("limitations", [])
                if not text.startswith(("Temporal audit ", "Province "))
            ]
            new_limits += [
                f"Province {r['area']}: known 2016/2019 r={r['r']:.4f}, "
                f"bias={r['bias']:+.2%} misses the regional target."
                for r in known_rows
                if r["eligible"] and not r["meets_target"] and r["r"] is not None
            ]
            validation["limitations"] = list(
                dict.fromkeys(old_limits + provenance["limitations"] + new_limits)
            )
            write_json(paths.reports / "validation.json", validation)
            pilot = read_json(paths.reports / "indonesia_pilot.json")
            pilot["validation"] = validation
            pilot["coverage"] = coverage
            write_json(paths.reports / "indonesia_pilot.json", pilot)
            write_json(
                paths.reports / "regional_audit.json",
                {
                    "selection_lock": lock,
                    "evaluation": rows,
                    "source_versions": provenance,
                    "normalization": normalization,
                    "serving_coefficients_changed": False,
                },
            )
    print("Audit saved to", out)


if __name__ == "__main__":
    main()
