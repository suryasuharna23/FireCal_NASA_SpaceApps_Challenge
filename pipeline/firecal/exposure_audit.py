"""Parse NASA's two independent gap-table columns without inventing exposure.

A listed day can be partially missing and still contain detections. No listed
gap, a successful request, and a detection-free day all leave exposure unknown.
"""

from __future__ import annotations

from datetime import date
from html.parser import HTMLParser

import numpy as np
import pandas as pd

LABELS = {
    "Suomi NPP (VIIRS)": "S-NPP",
    "NOAA-20 (VIIRS)": "NOAA-20",
    "NOAA-21 (VIIRS)": "NOAA-21",
    "Terra (MODIS)": "Terra",
    "Aqua (MODIS)": "Aqua",
}
SOURCES = {
    "S-NPP": "VIIRS_SNPP",
    "NOAA-20": "VIIRS_NOAA20",
    "NOAA-21": "VIIRS_NOAA21",
    "Terra": "MODIS",
    "Aqua": "MODIS",
}


class _Rows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], [], None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag == "td":
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr":
            self.rows.append(self.row)


def parse_missing_days(payload: dict) -> pd.DataFrame:
    """Standard and NRT columns are separate lists, not paired observations."""
    if payload.get("success") is not True or not isinstance(payload.get("html"), str):
        raise ValueError("NASA missing-data response did not succeed")
    parser = _Rows()
    parser.feed(payload["html"])
    if len(parser.rows) != payload.get("rowCount") or parser.cell is not None:
        raise ValueError("NASA gap-table row count/structure changed")
    records = []
    for cells in parser.rows:
        if len(cells) != 4:
            raise ValueError("Expected two independent date/platform pairs")
        for mode, offset in (("SP", 0), ("NRT", 2)):
            day, label = cells[offset : offset + 2]
            if not day and not label:
                continue
            date.fromisoformat(day)
            if label not in LABELS:
                raise ValueError("Unrecognized NASA platform label; inspect before using")
            records.append({"date": day, "satellite": LABELS[label], "source_mode": mode})
    table = pd.DataFrame(records, columns=["date", "satellite", "source_mode"])
    if table.duplicated().any():
        raise ValueError("Duplicate NASA gap records")
    return table.sort_values(["date", "satellite", "source_mode"]).reset_index(drop=True)


def daily_inventory(
    daily: pd.DataFrame,
    gaps: pd.DataFrame,
    availability: list[dict],
    start: str,
    end: str,
) -> pd.DataFrame:
    """Join database-gap flags to retained country counts, without estimating valid days."""
    if daily.duplicated(["date", "satellite", "source"]).any():
        raise ValueError("Daily counts must be unique")
    if not daily.satellite.isin(SOURCES).all() or not daily.source.isin(["SP", "NRT"]).all():
        raise ValueError("Unknown retained platform or source")
    values = daily.n.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any() or (values != np.floor(values)).any():
        raise ValueError("Invalid retained counts")
    if gaps.duplicated(["date", "satellite", "source_mode"]).any():
        raise ValueError("Duplicate gap records")
    by_source = {row["data_id"]: row for row in availability}
    if len(by_source) != len(availability):
        raise ValueError("Duplicate availability source")
    dates = [day.date().isoformat() for day in pd.date_range(start, end)]
    if not dates:
        raise ValueError("Empty date range")
    counts = daily.set_index(["date", "satellite", "source"]).n.to_dict()
    flagged = set(gaps.itertuples(index=False, name=None))
    records = []
    for day in dates:
        for platform, prefix in SOURCES.items():
            modes = []
            for mode in ("SP", "NRT"):
                row = by_source.get(f"{prefix}_{mode}")
                if row and row["min_date"] <= day <= row["max_date"]:
                    modes.append(mode)
            # SP supersedes overlapping NRT availability in the saved acquisition.
            mode = modes[0] if modes else "unavailable"
            observed = sum(counts.get((day, platform, m), 0) for m in ("SP", "NRT"))
            matching_count = counts.get((day, platform, mode), 0)
            matching = mode != "unavailable" and (day, platform, mode) in flagged
            other_mode_flags = [
                m for m in ("SP", "NRT") if (day, platform, m) in flagged and m != mode
            ]
            if mode == "unavailable":
                state = "outside_saved_availability"
            elif matching:
                state = (
                    "listed_missing_data_with_detections"
                    if matching_count
                    else "listed_missing_data"
                )
            else:
                state = "no_listed_gap" if observed else "no_retained_detections"
            records.append(
                {
                    "date": day,
                    "satellite": platform,
                    "saved_source_mode": mode,
                    "retained_detections": observed,
                    "retained_in_saved_mode": matching_count,
                    "retained_sp": counts.get((day, platform, "SP"), 0),
                    "retained_nrt": counts.get((day, platform, "NRT"), 0),
                    "nasa_missing_data_day": matching,
                    "other_mode_flags": ",".join(other_mode_flags),
                    "evidence_state": state,
                    "valid_observation_exposure": "unknown",
                }
            )
    return pd.DataFrame(records)
