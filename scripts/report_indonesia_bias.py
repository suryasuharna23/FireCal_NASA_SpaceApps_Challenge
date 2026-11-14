"""Publish small reproducible diagnostic tables/figures from a completed frozen audit."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
VERSION = "593ae2d95fdf"


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=Path("data/interim/bias-audit-20261114"))
    parser.add_argument(
        "--exposure", type=Path, default=Path("data/interim/bias-audit-exposure-20261114-r2")
    )
    parser.add_argument(
        "--evidence", type=Path, default=Path("data/interim/exposure-evidence-20261114")
    )
    parser.add_argument("--out", type=Path, default=Path("docs/reports/bias-audit-20261114"))
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Report output exists; preserve it and choose a new directory")
    report = json.loads((args.audit / "audit.json").read_text())
    manifest = json.loads((args.audit / "input_manifest.json").read_text())
    if report["data_version"] != VERSION or not report["baseline_reproduction"]["matches"]:
        raise ValueError("A reproduced real snapshot is required")
    roots = {
        "snapshot": ROOT / "data/interim/indonesia-extended-20261114/processed",
        "acquisition": ROOT / "data/interim/api-acquisition",
        "prior_audit": ROOT / "data/interim/regional-audit",
        "code": ROOT,
    }
    for entry in manifest["inputs"]:
        if digest(roots[entry["group"]] / entry["path"]) != entry["sha256"]:
            raise ValueError("Frozen audit input changed before report generation")
    metrics = pd.read_csv(args.audit / "period_metrics.csv")
    metrics["passed"] = metrics.meets_target.astype("string").eq("True").fillna(False)
    combined = metrics[metrics.reference == "Terra+Aqua"]
    national = combined[(combined.area == "Indonesia") & (combined.scenario == "baseline")]
    regional = combined[(combined.area != "Indonesia") & (combined.scenario == "baseline")]
    sensitivity = combined[combined.period == "2026_Jan_Oct_provisional"]
    monthly = pd.read_csv(args.audit / "monthly_sensitivity.csv")
    national_months = monthly[(monthly.area == "Indonesia") & (monthly.year == 2026)]
    base_months = national_months[national_months.scenario == "baseline"].sort_values("month")
    jan_oct = base_months[base_months.month <= 10]
    composition = pd.read_csv(args.audit / "retained_platform_source_versions.csv")
    exposure = json.loads((args.exposure / "exposure.json").read_text())
    args.out.mkdir(parents=True)
    tables = {
        "national-periods.csv": national,
        "regional-periods.csv": regional,
        "satellite-sensitivity.csv": sensitivity,
        "national-monthly-sensitivity.csv": national_months,
        "source-composition-2026.csv": composition[composition.year == 2026],
    }
    for name, table in tables.items():
        table.to_csv(args.out / name, index=False, lineterminator="\n")
    for source, name in (
        (args.audit / "input_manifest.json", "input-manifest.json"),
        (args.audit / "audit.json", "audit-result.json"),
        (args.exposure / "exposure.json", "exposure-result.json"),
        (args.exposure / "nasa_missing_days.csv", "nasa-missing-days.csv"),
        (args.exposure / "daily_evidence_inventory.csv", "daily-exposure-evidence.csv"),
        (args.exposure / "monthly_gap_flags.csv", "monthly-gap-flags.csv"),
    ):
        # Published text uses LF so Git does not change the checksummed artifacts.
        (args.out / name).write_bytes(source.read_bytes().replace(b"\r\n", b"\n"))
    # Preserve the HTTP response byte-for-byte, including its original EOF,
    # inside a binary archive rather than passing it through text normalization.
    (args.out / "nasa-missing-data-response.json.gz").write_bytes(
        gzip.compress((args.evidence / "nasa-missing-data-response.json").read_bytes(), mtime=0)
    )
    summary = {
        "data_version": VERSION,
        "baseline_rows_reproduced": report["baseline_reproduction"]["rows_compared"],
        "jan_oct_modis": float(jan_oct.observed.sum()),
        "jan_oct_prediction": float(jan_oct.predicted.sum()),
        "jan_oct_net_shortfall": float(-jan_oct.residual.sum()),
        "aug_sep_fraction_of_net_shortfall": float(
            jan_oct[jan_oct.month.isin([8, 9])].residual.sum() / jan_oct.residual.sum()
        ),
        "eligible_provinces": report["eligible_provinces"],
        "baseline_eligible_passes": int(
            sensitivity[
                (sensitivity.area != "Indonesia")
                & sensitivity.eligible
                & (sensitivity.scenario == "baseline")
            ].passed.sum()
        ),
        "exposure": exposure,
        "frozen_inputs_rechecked": True,
    }
    (args.out / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov*"]
    fig, axes = plt.subplots(2, 1, figsize=(11, 7.2), sharex=True, height_ratios=[2, 1])
    x = np.arange(11)
    axes[0].plot(x, base_months.observed, "o-", color="#253858", label="MODIS reference")
    axes[0].plot(
        x,
        base_months.predicted,
        "o-",
        color="#d95f02",
        label="VIIRS prediction, fixed coefficients",
    )
    axes[0].set(
        ylabel="Monthly counts",
        title="Indonesia 2026: shortfall is concentrated in August and September",
    )
    axes[0].legend(loc="upper left")
    bias = (base_months.predicted / base_months.observed - 1) * 100
    axes[1].bar(x, bias, color=np.where(bias < 0, "#b24436", "#2a788e"))
    axes[1].axhline(0, color="#555555", lw=0.8)
    axes[1].set(ylabel="Monthly bias (%)", xticks=x, xticklabels=labels)
    for ax in axes:
        for lo, hi, color in [(-0.4, 6.4, "#e7f0f3"), (6.6, 7.4, "#f9edd3"), (7.6, 9.4, "#f4e4e0")]:
            ax.axvspan(lo, hi, color=color, alpha=0.7, zorder=-1)
    axes[0].text(3, 31000, "SP / SP", ha="center")
    axes[0].text(7, 44000, "SP / NRT", ha="center")
    axes[0].text(8.6, 44000, "NRT / NRT", ha="center")
    fig.text(
        0.08,
        0.025,
        "Source: frozen FIRMS snapshot 593ae2d95fdf. Modes: MODIS / VIIRS. "
        "*November is partial. Association is not causation.",
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(args.out / "monthly-diagnosis.png", dpi=170)
    plt.close(fig)
    national_s = sensitivity[sensitivity.area == "Indonesia"].set_index("scenario")
    order = [
        "baseline",
        "without_NOAA-21",
        "without_S-NPP",
        "without_NOAA-20",
        "only_NOAA-20",
        "only_NOAA-21",
        "only_S-NPP",
    ]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    y = np.arange(len(order))
    values = national_s.loc[order, "bias"].to_numpy() * 100
    ax.barh(y, values, color=["#253858"] + ["#bd6b43"] * 6)
    ax.axvline(-10, color="#777777", ls="--", label="-10% bias threshold")
    ax.set(
        yticks=y,
        yticklabels=[v.replace("_", " ") for v in order],
        xlabel="Aggregate bias against combined MODIS (%)",
        title="Removing NOAA-21 does not resolve the 2026 national bias",
    )
    for i, v in enumerate(values):
        ax.text(
            v + 0.10,
            i,
            f"{v:.2f}%",
            va="center",
            color="white" if v < -11 else "#222222",
            fontsize=9,
        )
    ax.invert_yaxis()
    ax.legend(loc="lower right")
    fig.text(
        0.06,
        0.02,
        "January-October 2026. Subset divisors recomputed; conversion coefficients unchanged. "
        "Diagnostics, not selected models.",
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(args.out / "satellite-sensitivity.png", dpi=170)
    plt.close(fig)
    region = sensitivity[
        (sensitivity.scenario == "baseline")
        & sensitivity.eligible
        & (sensitivity.area != "Indonesia")
    ].sort_values("bias")
    fig, ax = plt.subplots(figsize=(10, 9))
    y = np.arange(len(region))
    v = region.bias.to_numpy() * 100
    ax.barh(y, v, color=np.where(region.passed, "#2a788e", "#b24436"))
    ax.axvline(-10, color="#888888", ls="--", lw=0.8)
    ax.axvline(10, color="#888888", ls="--", lw=0.8)
    ax.set(
        yticks=y,
        yticklabels=region.area,
        xlabel="Aggregate bias (%)",
        title="Only 8 of 27 eligible provinces meet both accuracy targets",
    )
    ax.invert_yaxis()
    fig.text(
        0.06,
        0.015,
        "January-October 2026. Blue meets r >= 0.9 and |bias| <= 10%; red misses at least one. "
        "Province totals use grid-overlap fractions.",
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(args.out / "regional-bias.png", dpi=170)
    plt.close(fig)
    source_files = [
        args.audit / n
        for n in (
            "period_metrics.csv",
            "monthly_sensitivity.csv",
            "retained_platform_source_versions.csv",
        )
    ]
    source_files += [args.exposure / n for n in ("exposure.json", "daily_evidence_inventory.csv")]
    output_hashes = {
        path.name: digest(path) for path in sorted(args.out.iterdir()) if path.is_file()
    }
    (args.out / "report-manifest.json").write_text(
        json.dumps(
            {
                "data_version": VERSION,
                "report_script_sha256": digest(__file__),
                "source_files": {str(p): digest(p) for p in source_files},
                "outputs": output_hashes,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
