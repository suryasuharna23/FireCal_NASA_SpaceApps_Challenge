"""Experimental ratio estimators for training-only regional calibration audits.

These estimators do not alter the serving model or infer observation exposure.
Administrative groups are calibration strata, not ecological biome classes.
"""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Candidate:
    region: str = "latitude"
    shrinkage: float = 100
    balance: bool = False

    @property
    def name(self) -> str:
        suffix = "balanced" if self.balance else "original"
        return f"{self.region}_a{self.shrinkage:g}_{suffix}"


def fit_ratios(
    observed: np.ndarray,
    viirs: np.ndarray,
    groups: np.ndarray,
    candidate: Candidate,
    *,
    min_cell: float = 50,
    min_region: float = 500,
) -> np.ndarray:
    """Fit cell coefficients from training-only month-by-cell count matrices.

    ``viirs`` is the already normalized count per active satellite. Optional
    balancing restores the training total inside each sufficiently sampled group
    after shrinkage. Sparse groups retain the global prior without balancing.
    """
    observed, viirs = np.asarray(observed, float), np.asarray(viirs, float)
    if observed.ndim != 2 or observed.shape != viirs.shape:
        raise ValueError("Observed and VIIRS matrices must have the same 2D shape")
    if len(groups) != observed.shape[1] or candidate.shrinkage < 0:
        raise ValueError("Invalid groups or shrinkage")
    if not all(np.isfinite(a).all() and (a >= 0).all() for a in (observed, viirs)):
        raise ValueError("Counts must be finite and nonnegative")
    m, v = observed.sum(axis=0), viirs.sum(axis=0)
    if v.sum() <= 0:
        raise ValueError("No training VIIRS detections")
    _, labels = np.unique(groups, return_inverse=True)
    regional_m, regional_v = np.bincount(labels, weights=m), np.bincount(labels, weights=v)
    global_k = m.sum() / v.sum()
    regional_k = np.full(len(regional_m), global_k)
    enough_region = regional_v >= min_region
    np.divide(regional_m, regional_v, out=regional_k, where=enough_region)
    prior = regional_k[labels]
    k = prior.copy()
    np.divide(
        m + candidate.shrinkage * prior,
        v + candidate.shrinkage,
        out=k,
        where=v >= min_cell,
    )
    if candidate.balance:
        predicted = np.bincount(labels, weights=v * k)
        correction = np.ones(len(predicted))
        np.divide(
            regional_m,
            predicted,
            out=correction,
            where=enough_region & (predicted > 0),
        )
        k *= correction[labels]
    return k
