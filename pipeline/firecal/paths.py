"""Canonical on-disk layout of the ``data/`` folder (FRD 7.2)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DataPaths:
    root: Path

    @property
    def raw(self) -> Path:
        """Original FIRMS archive CSVs."""
        return self.root / "raw"

    @property
    def reference(self) -> Path:
        """Downloaded reference layers (land mask, ecoregions, boundaries)."""
        return self.raw / "reference"

    @property
    def interim(self) -> Path:
        return self.root / "interim"

    @property
    def processed(self) -> Path:
        return self.root / "processed"

    # --- interim ---
    @property
    def detections(self) -> Path:
        """Normalized archive (SP) detections, hive-partitioned by sensor/year."""
        return self.interim / "detections"

    @property
    def nrt(self) -> Path:
        """Normalized near-real-time detections (merged, deduplicated)."""
        return self.interim / "nrt" / "nrt.parquet"

    @property
    def clean(self) -> Path:
        """Clean unified point table, hive-partitioned by year."""
        return self.interim / "points"

    # --- processed (read by the API) ---
    @property
    def cells(self) -> Path:
        return self.processed / "cells.parquet"

    @property
    def grid_monthly(self) -> Path:
        return self.processed / "grid_monthly.parquet"

    @property
    def coefficients(self) -> Path:
        return self.processed / "coefficients.parquet"

    @property
    def harmonized(self) -> Path:
        return self.processed / "harmonized.parquet"

    @property
    def points(self) -> Path:
        return self.processed / "points"

    @property
    def static_mask(self) -> Path:
        return self.processed / "static_mask.parquet"

    @property
    def regions(self) -> Path:
        return self.processed / "regions.parquet"

    @property
    def meta(self) -> Path:
        return self.processed / "meta.json"

    @property
    def reports(self) -> Path:
        return self.processed / "reports"

    def ensure(self) -> DataPaths:
        for path in (self.raw, self.reference, self.interim, self.processed, self.reports):
            path.mkdir(parents=True, exist_ok=True)
        return self
