"""Likert-composite data generator for the composite-score study (v1)."""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from numpy.typing import NDArray

from simulations.dgp import SimulatedDataset
from simulations.edge_recovery import ring_truth

FloatMatrix = NDArray[np.float64]

P = 6
ITEMS = 5
LOADING = 0.7
CARELESS_COUNT = 3
CONTINUOUS_STRAIGHT_LINE = 2.0
TRUTH_DRAWS = 1_000_000
TRUTH_SEED = 20261005
FOCAL_EDGE = (0, 1)

_MODERATE = (-2.0, -1.2, -0.5, 0.25)
CONDITIONS: dict[str, tuple[tuple[float, ...], tuple[float, ...]] | None] = {
    "continuous_control": None,
    "symmetric": ((-1.5, -0.5, 0.5, 1.5), (0.0,) * ITEMS),
    "moderate_ceiling": (_MODERATE, (0.0,) * ITEMS),
    "severe_ceiling": ((-2.5, -1.8, -1.2, -0.4), (0.0,) * ITEMS),
    "moderate_heterogeneous": (_MODERATE, (-0.4, -0.2, 0.0, 0.2, 0.4)),
}


def _latent_cholesky() -> FloatMatrix:
    covariance, _ = ring_truth(P)
    scale = np.sqrt(np.diag(covariance))
    return np.asarray(np.linalg.cholesky(covariance / np.outer(scale, scale)), dtype=float)


def _item_latent(n: int, rng: np.random.Generator) -> FloatMatrix:
    """Return latent item values with shape (n, P, ITEMS)."""
    eta = rng.standard_normal((n, P)) @ _latent_cholesky().T
    errors = rng.standard_normal((n, P, ITEMS))
    return np.asarray(
        LOADING * eta[:, :, None] + np.sqrt(1.0 - LOADING**2) * errors, dtype=float
    )


def _composites(latent: FloatMatrix, condition: str) -> FloatMatrix:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown composite condition: {condition}")
    spec = CONDITIONS[condition]
    if spec is None:
        return np.asarray(latent.mean(axis=2), dtype=float)
    cuts, offsets = spec
    thresholds = np.asarray(cuts)[None, :] + np.asarray(offsets)[:, None]  # (ITEMS, 4)
    categories = 1 + (latent[..., None] > thresholds[None, None, :, :]).sum(axis=3)
    return np.asarray(categories.mean(axis=2), dtype=float)


@lru_cache(maxsize=None)
def composite_truth(
    condition: str, draws: int = TRUTH_DRAWS
) -> tuple[FloatMatrix, FloatMatrix, FloatMatrix]:
    """Return (covariance, precision, partial) of uncontaminated composites."""
    rng = np.random.default_rng(TRUTH_SEED)
    chunk = 100_000
    total = np.zeros(P)
    cross = np.zeros((P, P))
    done = 0
    while done < draws:
        size = min(chunk, draws - done)
        composites = _composites(_item_latent(size, rng), condition)
        total += composites.sum(axis=0)
        cross += composites.T @ composites
        done += size
    mean = total / draws
    covariance = cross / draws - np.outer(mean, mean)
    precision = np.linalg.inv(covariance)
    partial = -precision / np.sqrt(np.outer(np.diag(precision), np.diag(precision)))
    np.fill_diagonal(partial, 1.0)
    for matrix in (covariance, precision, partial):
        matrix.setflags(write=False)
    return covariance, precision, partial


def generate_composite_dataset(
    n: int, condition: str, careless: int, seed: int, truth_draws: int = TRUTH_DRAWS
) -> SimulatedDataset:
    """Generate one composite dataset; all conditions share draws for a given seed."""
    if careless not in (0, CARELESS_COUNT):
        raise ValueError(f"careless must be 0 or {CARELESS_COUNT}")
    if n <= CARELESS_COUNT:
        raise ValueError("n must exceed the number of careless respondents")
    rng = np.random.default_rng(seed)
    latent = _item_latent(n, rng)
    careless_cases = tuple(sorted(int(i) for i in rng.choice(n, CARELESS_COUNT, replace=False)))
    X = _composites(latent, condition)
    cases: tuple[int, ...] = ()
    if careless:
        cases = careless_cases
        X[list(cases), :] = (
            CONTINUOUS_STRAIGHT_LINE if CONDITIONS[condition] is None else 5.0
        )
    covariance, precision, partial = composite_truth(condition, truth_draws)
    return SimulatedDataset(X, covariance, precision, partial, cases, FOCAL_EDGE)
