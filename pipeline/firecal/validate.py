"""Hold-out validation of the harmonization (T-13, FR-D-12).

For every test year (``TEST_YEARS``, excluded from calibration) and month in which
both sensors observed, the calibrated model predicts MODIS from VIIRS::

    predicted = k_cell * n_viirs / n_viirs_sats

Monthly totals are compared with observed MODIS per region (biome) and globally:

* ``r``     Pearson correlation of monthly totals (target >= 0.9)
* ``bias``  (sum predicted - sum observed) / sum observed (target within +/-10 %)
* ``mae``   mean absolute monthly error (detections)

The same metrics for raw VIIRS-per-satellite counts ("before") show what
harmonization fixes. Regions that miss the targets are listed as limitations.
"""

from __future__ import annotations

import logging

import duckdb
import numpy as np
import pandas as pd

from firecal.grid import GridSpec
from firecal.harmonize import HarmonizeConfig
from firecal.io import write_json
from firecal.overlap import region_of
from firecal.paths import DataPaths

log = logging.getLogger(__name__)

TARGET_R = 0.9
TARGET_BIAS = 0.10


def _metrics(obs: np.ndarray, pred: np.ndarray) -> dict[str, float | None]:
    if len(obs) < 3 or obs.sum() == 0:
        return {"r": None, "bias": None, "mae": None, "months": int(len(obs))}
    r = float(np.corrcoef(obs, pred)[0, 1]) if obs.std() and pred.std() else None
    return {
        "r": r,
        "bias": float((pred.sum() - obs.sum()) / obs.sum()),
        "mae": float(np.mean(np.abs(pred - obs))),
        "months": int(len(obs)),
    }


def monthly_test_series(paths: DataPaths, grid: GridSpec, cfg: HarmonizeConfig) -> pd.DataFrame:
    tests = ", ".join(map(str, cfg.test_years))
    df = (
        duckdb.connect()
        .execute(
            f"""SELECT g.cell_id, g.year, g.month, g.n_modis,
                       g.n_viirs / g.n_viirs_sats::DOUBLE AS v_norm,
                       c.k * g.n_viirs / g.n_viirs_sats::DOUBLE AS predicted
                FROM read_parquet('{paths.grid_monthly.as_posix()}') g
                JOIN read_parquet('{paths.coefficients.as_posix()}') c USING (cell_id)
                WHERE g.n_viirs_sats > 0 AND g.year IN ({tests})"""
        )
        .df()
    )
    df["region"] = region_of(paths, grid, df["cell_id"].to_numpy())
    regional = df.groupby(["region", "year", "month"], as_index=False)[
        ["n_modis", "v_norm", "predicted"]
    ].sum()
    glob = df.groupby(["year", "month"], as_index=False)[["n_modis", "v_norm", "predicted"]].sum()
    glob["region"] = "global"
    return pd.concat([glob, regional], ignore_index=True)


def plot(series: pd.DataFrame, path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    g = series[series.region == "global"].sort_values(["year", "month"])
    labels = [f"{y}-{m:02d}" for y, m in zip(g.year, g.month, strict=True)]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.2), gridspec_kw={"width_ratios": [2, 1]})
    x = np.arange(len(g))
    ax1.plot(x, g.n_modis, color="#222", lw=2, label="MODIS observed")
    ax1.plot(x, g.v_norm, color="#d95f02", ls="--", label="VIIRS raw (per satellite)")
    ax1.plot(x, g.predicted, color="#1b9e77", label="VIIRS harmonized")
    step = max(1, len(x) // 8)
    ax1.set_xticks(x[::step], labels[::step], rotation=30, ha="right", fontsize=8)
    ax1.set(ylabel="detections / month", title="Hold-out years: monthly global totals")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.3)
    hi = float(max(g.n_modis.max(), g.v_norm.max(), g.predicted.max(), 1)) * 1.05
    ax2.scatter(g.n_modis, g.v_norm, s=14, color="#d95f02", label="before")
    ax2.scatter(g.n_modis, g.predicted, s=14, color="#1b9e77", label="after")
    ax2.plot([0, hi], [0, hi], color="#888", lw=1)
    ax2.set(xlim=(0, hi), ylim=(0, hi), xlabel="MODIS observed", ylabel="VIIRS",
            title="Before / after harmonization")  # fmt: skip
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3)
    fig.text(0.01, 0.01, "Data: NASA FIRMS", fontsize=7, color="#666")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def validate(paths: DataPaths, grid: GridSpec, cfg: HarmonizeConfig) -> dict[str, object]:
    if not cfg.test_years:
        raise ValueError("TEST_YEARS is empty; nothing to validate")
    series = monthly_test_series(paths, grid, cfg)
    if series.empty:
        raise ValueError(f"No MODIS-VIIRS overlap in test years {cfg.test_years}")

    regions = {}
    for region, g in series.groupby("region"):
        after = _metrics(g.n_modis.to_numpy(float), g.predicted.to_numpy())
        before = _metrics(g.n_modis.to_numpy(float), g.v_norm.to_numpy())
        passed = (
            after["r"] is not None and after["r"] >= TARGET_R and abs(after["bias"]) <= TARGET_BIAS
        )
        regions[region] = {"after": after, "before": before, "meets_target": passed}

    limitations = [
        f"{name}: r={m['after']['r'] if m['after']['r'] is None else round(m['after']['r'], 3)}, "
        f"bias={'n/a' if m['after']['bias'] is None else f'{m["after"]["bias"]:+.1%}'} "
        f"over {m['after']['months']} months misses the target (r >= {TARGET_R}, "
        f"|bias| <= {TARGET_BIAS:.0%})"
        for name, m in regions.items()
        if not m["meets_target"]
    ]
    report = {
        "test_years": list(cfg.test_years),
        "targets": {"r": TARGET_R, "abs_bias": TARGET_BIAS},
        "global": regions.get("global"),
        "regions": {k: v for k, v in regions.items() if k != "global"},
        "meets_target_global": bool(regions.get("global", {}).get("meets_target")),
        "limitations": limitations,
        "plot": "validation.png",
    }
    paths.reports.mkdir(parents=True, exist_ok=True)
    series.to_csv(paths.reports / "validation_series.csv", index=False)
    plot(series, paths.reports / "validation.png")
    write_json(paths.reports / "validation.json", report)
    log.info("Validation on %s: global %s", cfg.test_years, report["global"])
    return report
