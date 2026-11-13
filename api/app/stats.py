"""Climatology, summary, annual totals and critical periods (FR-W-06/11/12/13/14)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.series import Window, clean_number, fmt_ym, in_window


def compute_stats(series: pd.DataFrame, window: Window) -> dict[str, Any]:
    """``series`` is the gap-free AOI series (with anomaly columns) over all data."""
    ref = series[(series.year >= window.reference[0]) & (series.year <= window.reference[1])]
    view = in_window(series, window.start, window.end)
    current_year = window.end[0]

    # Critical threshold: 75th percentile of every reference month in the AOI.
    threshold = float(np.percentile(ref.n_harmonized, 75)) if len(ref) else 0.0
    climatology = []
    for month in range(1, 13):
        values = ref.loc[ref.month == month, "n_harmonized"].to_numpy()
        current = view[(view.year == current_year) & (view.month == month)]
        median = float(np.median(values)) if len(values) else None
        climatology.append(
            {
                "month": month,
                "median": clean_number(median),
                "p25": clean_number(np.percentile(values, 25)) if len(values) else None,
                "p75": clean_number(np.percentile(values, 75)) if len(values) else None,
                "current": clean_number(current.n_harmonized.iloc[0]) if len(current) else None,
                "critical": bool(median is not None and median > threshold and median > 0),
            }
        )

    annual = (
        view.groupby("year")
        .agg(total=("n_harmonized", "sum"), months=("month", "size"))
        .reset_index()
    )
    annual["rank"] = annual.total.rank(ascending=False, method="min").astype(int)
    annual_rows = [
        {
            "year": int(r.year),
            "total": clean_number(r.total, 1),
            "rank": int(r.rank),
            "complete": bool(r.months == 12),
        }
        for r in annual.itertuples()
    ]

    latest = view.iloc[-1] if len(view) else None
    medians = [c["median"] or 0 for c in climatology]
    top = annual.sort_values(["total", "year"], ascending=[False, True]).head(1)
    summary = {
        "total": clean_number(view.n_harmonized.sum(), 1),
        "monthly_mean": clean_number(view.n_harmonized.mean(), 2) if len(view) else None,
        "peak_month": int(np.argmax(medians)) + 1 if any(medians) else None,
        "max_year": int(top.year.iloc[0]) if len(top) else None,
        "max_year_total": clean_number(top.total.iloc[0], 1) if len(top) else None,
        "current": None
        if latest is None
        else {
            "month": fmt_ym((int(latest.year), int(latest.month))),
            "value": clean_number(latest.n_harmonized),
            "median": clean_number(latest["median"]),
            "anomaly_pct": clean_number(latest.anomaly_pct, 1),
            "percentile": clean_number(latest.percentile, 1),
            "provisional": bool(latest.provisional),
        },
    }
    return {
        "climatology": climatology,
        "critical_threshold": clean_number(threshold),
        "critical_months": [c["month"] for c in climatology if c["critical"]],
        "annual": annual_rows,
        "summary": summary,
    }
