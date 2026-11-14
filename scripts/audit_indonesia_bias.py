"""Freeze and diagnose the saved Indonesia snapshot without downloads or refitting.

Run --check-inputs first. All outputs are new files in a separate, new directory.
No .env, serving products, snapshot reports or existing audit locks are written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from importlib.metadata import version as package_version
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import shapely

from app.aoi import Grid
from firecal.acquire import plan_windows, verify_receipts
from firecal.bias_audit import (
    PERIODS,
    PLATFORMS,
    YEARS,
    check_counts,
    compare_reference,
    diagnose,
    reconcile_grid,
    summarize,
)

REPO = Path(__file__).resolve().parents[1]
REQUIRED = (
    "meta.json",
    "coefficients.parquet",
    "grid_monthly.parquet",
    "harmonized.parquet",
    "months.parquet",
    "regions.parquet",
    "reports/regional_regression.csv",
    "reports/satellite_source_counts.csv",
    "reports/country_filter.json",
    "reports/extended_summary.json",
    "reports/extended_verification.json",
)
SOURCES = (
    "MODIS_SP",
    "MODIS_NRT",
    "VIIRS_SNPP_SP",
    "VIIRS_SNPP_NRT",
    "VIIRS_NOAA20_SP",
    "VIIRS_NOAA20_NRT",
    "VIIRS_NOAA21_SP",
    "VIIRS_NOAA21_NRT",
)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def inventory(processed: Path, acquisition: Path, prior_audit: Path) -> dict:
    missing = [str(processed / name) for name in REQUIRED if not (processed / name).is_file()]
    points = sorted((processed / "points").rglob("*.parquet"))
    if not points:
        missing.append(str(processed / "points/**/*.parquet"))
    for name in ("plan.json", "availability.json", "progress.json"):
        if not (acquisition / name).is_file():
            missing.append(str(acquisition / name))
    for source in SOURCES:
        if not (acquisition / "responses" / source / "manifest.json").is_file():
            missing.append(str(acquisition / "responses" / source / "manifest.json"))
    if not (prior_audit / "selection_lock.json").is_file():
        missing.append(str(prior_audit / "selection_lock.json"))
    return {"ready": not missing, "missing": missing, "point_partitions": len(points)}


def receipt_inventory(acquisition: Path) -> tuple[list[Path], list[dict]]:
    """Verify complete receipts and relocated responses without following old absolute paths."""
    plan, available = read(acquisition / "plan.json"), read(acquisition / "availability.json")
    by_source = {item["source"]: item for item in plan["sources"]}
    if len(plan["sources"]) != 8 or set(by_source) != set(SOURCES):
        raise ValueError("Eight unique acquisition sources are required")
    if not read(acquisition / "progress.json").get("complete"):
        raise ValueError("Acquisition progress is incomplete")
    paths, windows = [], []
    for source in SOURCES:
        item = by_source[source]
        jobs = plan_windows(
            source, item["requested_start"], item["requested_end"], available["sources"]
        )
        manifest_path = acquisition / "responses" / source / "manifest.json"
        manifest = read(manifest_path)
        verify_receipts(manifest, jobs, tuple(plan["bbox"]))
        paths.append(manifest_path)
        for job, receipt in zip(jobs, manifest["records"], strict=True):
            # The acquisition tool nests the source folder twice. Locate by the
            # generated request filename so an ASUS path can be safely relocated.
            matches = list(manifest_path.parent.rglob(job.filename))
            if len(matches) != 1 or not matches[0].resolve().is_relative_to(acquisition.resolve()):
                raise ValueError(f"A unique saved response is required for {job.filename}")
            path = matches[0]
            if sha(path) != receipt["sha256"] or path.stat().st_size != receipt["bytes"]:
                raise ValueError(f"Saved response checksum/size differs for {job.filename}")
            paths.append(path)
            sidecar = path.with_suffix(".json")
            if not sidecar.is_file() or read(sidecar).get("sha256") != receipt["sha256"]:
                raise ValueError(f"Matching response receipt required for {job.filename}")
            paths.append(sidecar)
            windows.append(
                {
                    "source": source,
                    "start": job.start,
                    "days": job.days,
                    "rows_before_country_and_quality_filters": receipt["rows"],
                    "downloaded_at": receipt.get("downloaded_at"),
                    "request_status": "success_zero_detections"
                    if receipt["rows"] == 0
                    else "success",
                    "observation_exposure": "unknown",
                }
            )
    return paths, windows


def fingerprint(
    processed: Path, acquisition: Path, prior_audit: Path, extra: list[Path]
) -> list[dict]:
    files = [processed / name for name in REQUIRED] + sorted(
        (processed / "points").rglob("*.parquet")
    )
    files += [acquisition / name for name in ("plan.json", "availability.json", "progress.json")]
    files += [prior_audit / "selection_lock.json", *extra]
    code = [
        "scripts/audit_indonesia_bias.py",
        "pipeline/firecal/bias_audit.py",
        "pipeline/firecal/grid.py",
        "pipeline/firecal/harmonize.py",
        "pipeline/firecal/ingest.py",
        "pipeline/firecal/nrt.py",
        "pipeline/firecal/acquire.py",
        "api/app/aoi.py",
        "scripts/verify_indonesia_extended.py",
        "docs/bias-audit-protocol.md",
        "docs/bias-audit-exposure-evidence.csv",
        "uv.lock",
    ]
    files += [REPO / name for name in code]
    roots = {
        "snapshot": processed,
        "acquisition": acquisition,
        "prior_audit": prior_audit,
        "code": REPO,
    }
    result = []
    for path in sorted(set(p.resolve() for p in files)):
        label, relative = next(
            (label, path.relative_to(root.resolve()).as_posix())
            for label, root in roots.items()
            if path.is_relative_to(root.resolve())
        )
        result.append(
            {"group": label, "path": relative, "bytes": path.stat().st_size, "sha256": sha(path)}
        )
    return result


def area_weights(
    processed: Path, coef: pd.DataFrame, resolution: float
) -> tuple[pd.DataFrame, dict]:
    provinces = pd.read_parquet(processed / "regions.parquet").query("level == 1")
    if provinces.name.duplicated().any() or "Indonesia" in set(provinces.name):
        raise ValueError("Administrative area names must be unique")
    frames = [pd.DataFrame({"cell_id": coef.cell_id, "area": "Indonesia", "w": 1.0})]
    eligible = {"Indonesia": True}
    for row in provinces.itertuples():
        w = Grid(resolution).cell_weights(shapely.from_wkb(row.geometry))
        w = w.merge(coef[["cell_id", "n_cal_modis"]], on="cell_id")
        eligible[row.name] = bool((w.w * w.n_cal_modis).sum() >= 1000)
        # Preserve even a region intersecting no coefficient cell in the audit.
        if w.empty:
            w = pd.DataFrame({"cell_id": [coef.cell_id.iloc[0]], "w": [0.0]})
        frames.append(w[["cell_id", "w"]].assign(area=row.name))
    return pd.concat(frames, ignore_index=True), eligible


def run(processed: Path, acquisition: Path, prior_audit: Path, out: Path, version: str) -> dict:
    for root in (processed, acquisition, prior_audit):
        if out == root or out.is_relative_to(root) or root.is_relative_to(out):
            raise ValueError("Audit output must be separate from all input trees")
    if out.exists():
        raise ValueError("Audit output already exists; choose a new directory to preserve the lock")
    status = inventory(processed, acquisition, prior_audit)
    if not status["ready"]:
        raise ValueError("Required snapshot/receipts/selection lock missing; run --check-inputs")
    meta = read(processed / "meta.json")
    if meta.get("data_version") != version or meta.get("dataset_status") != "experimental":
        raise ValueError("Dataset version/status differs from the requested frozen snapshot")
    if meta.get("coverage", {}).get("country") != "Indonesia":
        raise ValueError("This audit requires the Indonesia snapshot")
    snapshot_end = meta["coverage"].get("snapshot_end")
    dates = {item["requested_end"] for item in read(acquisition / "plan.json")["sources"]}
    if dates != {snapshot_end} or meta.get("end_month") != str(snapshot_end)[:7]:
        raise ValueError("Snapshot and acquisition end dates disagree")
    receipt_paths, windows = receipt_inventory(acquisition)
    before = fingerprint(processed, acquisition, prior_audit, receipt_paths)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "code_commit": revision,
        "data_version": version,
        "inputs": before,
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "packages": {
                name: package_version(name)
                for name in ("duckdb", "pandas", "numpy", "shapely", "pyproj")
            },
        },
        "configuration": {
            "grid_res_deg": meta["grid_res_deg"],
            "calibration_period": meta.get("calibration_period"),
            "test_years": meta.get("test_years"),
            "periods": PERIODS,
            "coefficients": "fixed_snapshot_coefficients_no_refit",
            "eligibility_modis": 1000,
            "denominator": "distinct retained VIIRS satellites globally within each scenario/month",
        },
        "observed_periods_are_fresh_holdouts": False,
    }
    out.mkdir(parents=True, exist_ok=False)
    write(out / "input_manifest.json", manifest)
    coef = pd.read_parquet(processed / "coefficients.parquet")
    grid = pd.read_parquet(processed / "grid_monthly.parquet")
    grid = grid[grid.year.isin(YEARS) & ((grid.year != 2026) | (grid.month <= 11))]
    with duckdb.connect() as con:
        points = str(processed / "points/**/*.parquet").replace("\\", "/").replace("'", "''")
        counts = con.execute(
            "SELECT cell_id,year,month,sensor,satellite,source,"
            "coalesce(version,'unknown') AS version,"
            f"count(*) n FROM read_parquet('{points}', hive_partitioning=true) "
            "WHERE year IN (2016,2019,2022,2023,2024,2025,2026) "
            "AND (year<>2026 OR month<=11) GROUP BY ALL"
        ).df()
        actual = con.execute(
            "SELECT satellite,source,count(*) AS rows,"
            "min(acq_date) AS first_date,max(acq_date) AS last_date "
            f"FROM read_parquet('{points}', hive_partitioning=true) GROUP BY ALL ORDER BY ALL"
        ).df()
        saved = pd.read_csv(processed / "reports/satellite_source_counts.csv")
        pd.testing.assert_frame_equal(
            actual.astype(str).sort_values(["satellite", "source"]).reset_index(drop=True),
            saved[actual.columns]
            .astype(str)
            .sort_values(["satellite", "source"])
            .reset_index(drop=True),
        )
        actual_clean = (
            actual.assign(sensor=actual.satellite.map(PLATFORMS)).groupby("sensor").rows.sum()
        )
        if (
            actual_clean.to_dict()
            != read(processed / "reports/extended_summary.json")["clean_rows"]
        ):
            raise ValueError("Retained counts differ from the snapshot clean-count report")
        cube_path = (processed / "harmonized.parquet").as_posix().replace("'", "''")
        balance_error = con.execute(
            f"WITH p AS (SELECT cell_id,year,month,sum(weight) weighted "
            f"FROM read_parquet('{points}', hive_partitioning=true) "
            "WHERE in_series GROUP BY ALL) "
            "SELECT max(abs(coalesce(weighted,0)-coalesce(n_harmonized,0))) "
            f"FROM p FULL JOIN read_parquet('{cube_path}') USING(cell_id,year,month)"
        ).fetchone()[0]
        if balance_error is None or not np.isfinite(balance_error) or balance_error >= 1e-8:
            raise ValueError("Published point weights do not reconcile with the harmonized cube")
    check_counts(counts, coef)
    reconciliation = reconcile_grid(counts, grid)
    weights, eligible = area_weights(processed, coef, float(meta["grid_res_deg"]))
    pairs = sorted(set(pair for pairs in PERIODS.values() for pair in pairs))
    months = pd.DataFrame(pairs, columns=["year", "month"])
    stored_months = pd.read_parquet(processed / "months.parquet")
    present = set(zip(stored_months.year, stored_months.month, strict=True))
    if not set(pairs).issubset(present):
        raise ValueError("Snapshot does not contain every requested audit month")
    monthly, contributions = diagnose(counts, coef, weights, months)
    summary = summarize(monthly, eligible)
    reference = pd.read_csv(processed / "reports/regional_regression.csv")
    expected_rows = {
        (period, area)
        for period in ("known_2016_2019", "known_2022_2025", "2026_Jan_Oct_provisional")
        for area in eligible
    }
    if set(zip(reference.period, reference.area, strict=True)) != expected_rows:
        raise ValueError("Saved regression does not cover all required areas and baseline periods")
    reproduced = compare_reference(summary, reference)
    regimes = (
        counts.groupby(["year", "month", "sensor", "satellite", "source", "version"])
        .n.sum()
        .reset_index()
    )
    # Report kept/raw counts separately. Country/quality filtering means receipt
    # row counts must never be compared directly with clean retained totals.
    end_fingerprint = fingerprint(processed, acquisition, prior_audit, receipt_paths)
    if before != end_fingerprint:
        raise ValueError("An input or code file changed during the audit; no report published")
    national = summary[
        (summary.area == "Indonesia")
        & (summary.scenario == "baseline")
        & (summary.reference == "Terra+Aqua")
        & (summary.period == "2026_Jan_Oct_provisional")
    ].iloc[0]
    report = {
        "status": "diagnostics_complete_exposure_unresolved",
        "data_version": version,
        "baseline_reproduction": reproduced,
        "point_grid_reconciliation": reconciliation,
        "max_point_weight_balance_error": balance_error,
        "eligible_provinces": sum(v for k, v in eligible.items() if k != "Indonesia"),
        "national_2026_jan_oct": {
            k: (
                None
                if pd.isna(national[k])
                else national[k].item()
                if hasattr(national[k], "item")
                else national[k]
            )
            for k in ("r", "bias", "mae", "months", "meets_target")
        },
        "model_refitted": False,
        "serving_changed": False,
        "limitations": [
            "SP/NRT periods are seasonally confounded, not paired processing experiments.",
            "Satellite-subset diagnostics retain coefficients trained on another mixture.",
            "Terra/Aqua separately are uncalibrated references, not replacement target scales.",
            "Successful requests and detection days do not establish valid observation exposure.",
            "November 2026 is partial; S-NPP availability ending Nov 2 is not proof of outage.",
            "2016/2019, 2022-2025 and observed 2026 outcomes are known, not fresh hold-outs.",
            "Residual contributions are accounting, not causal effects of source/satellite.",
        ],
    }
    monthly.to_csv(out / "monthly_sensitivity.csv", index=False)
    contributions.to_csv(out / "platform_source_contributions.csv", index=False)
    summary.to_csv(out / "period_metrics.csv", index=False)
    regimes.to_csv(out / "retained_platform_source_versions.csv", index=False)
    pd.DataFrame(windows).to_csv(out / "request_exposure_inventory.csv", index=False)
    actual.to_csv(out / "satellite_source_counts.csv", index=False)
    write(out / "audit.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--processed", type=Path, default=Path("data/interim/indonesia-extended-20261114/processed")
    )
    parser.add_argument("--acquisition", type=Path, default=Path("data/interim/api-acquisition"))
    parser.add_argument("--prior-audit", type=Path, default=Path("data/interim/regional-audit"))
    parser.add_argument("--out", type=Path, default=Path("data/interim/bias-audit-20261114"))
    parser.add_argument("--expected-version", default="593ae2d95fdf")
    parser.add_argument("--check-inputs", action="store_true")
    args = parser.parse_args()
    processed, acquisition, prior, out = (
        p.resolve() for p in (args.processed, args.acquisition, args.prior_audit, args.out)
    )
    if args.check_inputs:
        status = inventory(processed, acquisition, prior)
        if status["ready"]:
            meta = read(processed / "meta.json")
            if meta.get("data_version") != args.expected_version:
                status.update(ready=False, problem="Unexpected snapshot data version")
            else:
                try:
                    _, windows = receipt_inventory(acquisition)
                    status["verified_api_responses"] = len(windows)
                except (ValueError, OSError):
                    status.update(ready=False, problem="Response/receipt verification failed")
        print(json.dumps(status, indent=2))
        return 0 if status["ready"] else 2
    try:
        report = run(processed, acquisition, prior, out, args.expected_version)
    except (ValueError, OSError, AssertionError) as exc:
        # Never echo arbitrary receipt/provider payloads or credential-bearing URLs.
        print(
            f"Audit stopped ({type(exc).__name__}). No model or serving changes. "
            "Check local inputs and the audit protocol; rerun --check-inputs for missing files."
        )
        return 1
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
