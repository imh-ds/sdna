"""Likert-composite generator for the composite-score study v2 (see composite_score_study_v2.md)."""

from __future__ import annotations

from functools import cache

import numpy as np
from numpy.typing import NDArray

from simulations.composite_dgp import CONDITIONS as _V1_CONDITIONS
from simulations.dgp import SimulatedDataset
from simulations.edge_recovery import ring_truth

FloatMatrix = NDArray[np.float64]

ITEMS = 5
LOADING = 0.7
CONTAMINATED_COUNT = 3
FOCAL_EDGE = (0, 1)
TRUTH_DRAWS = 1_000_000
TRUTH_SEED = 20261007
CONDITIONS = ("continuous_control", "symmetric", "moderate_ceiling", "severe_ceiling")
CONTAMINATIONS = ("none", "straight_top", "focal_discordant", "random_responder")
STRENGTHS = {"strong": 0.35, "weak": 0.18}
P_VALUES = (6, 12)
CONTINUOUS_EXTREME = 2.0


def _latent_cholesky(p: int, weight: float) -> FloatMatrix:
    covariance, _ = ring_truth(p, weight)
    scale = np.sqrt(np.diag(covariance))
    return np.asarray(np.linalg.cholesky(covariance / np.outer(scale, scale)), dtype=float)


def _item_latent(n: int, p: int, weight: float, rng: np.random.Generator) -> FloatMatrix:
    eta = rng.standard_normal((n, p)) @ _latent_cholesky(p, weight).T
    errors = rng.standard_normal((n, p, ITEMS))
    return np.asarray(
        LOADING * eta[:, :, None] + np.sqrt(1.0 - LOADING**2) * errors, dtype=float
    )


def _items(latent: FloatMatrix, condition: str) -> FloatMatrix:
    """Item scores: integer categories (ordinal) or the latent values (control)."""
    if condition not in CONDITIONS:
        raise ValueError(f"unknown composite condition: {condition}")
    spec = _V1_CONDITIONS[condition]
    if spec is None:
        return latent.copy()
    cuts, offsets = spec
    thresholds = np.asarray(cuts)[None, :] + np.asarray(offsets)[:, None]
    return np.asarray(
        1 + (latent[..., None] > thresholds[None, None, :, :]).sum(axis=3), dtype=float
    )


def _contaminate(
    items: FloatMatrix,
    cases: tuple[int, ...],
    contamination: str,
    condition: str,
    random_stream: np.random.Generator,
) -> None:
    rows = list(cases)
    control = condition == "continuous_control"
    top, bottom = (CONTINUOUS_EXTREME, -CONTINUOUS_EXTREME) if control else (5.0, 1.0)
    if control:
        random_values = random_stream.uniform(-2.0, 2.0, size=(len(rows),) + items.shape[1:])
    else:
        random_values = random_stream.integers(1, 6, size=(len(rows),) + items.shape[1:])
    if contamination == "none":
        return
    if contamination == "straight_top":
        items[rows, :, :] = top
    elif contamination == "focal_discordant":
        items[rows, FOCAL_EDGE[0], :] = bottom
        items[rows, FOCAL_EDGE[1], :] = top
    elif contamination == "random_responder":
        items[rows, :, :] = random_values
    else:
        raise ValueError(f"unknown contamination: {contamination}")


@cache
def composite_truth(
    p: int, strength: str, condition: str, draws: int = TRUTH_DRAWS
) -> tuple[FloatMatrix, FloatMatrix, FloatMatrix]:
    """Return (covariance, precision, partial) of uncontaminated composites."""
    weight = STRENGTHS[strength]
    rng = np.random.default_rng(TRUTH_SEED)
    total, cross, done = np.zeros(p), np.zeros((p, p)), 0
    while done < draws:
        size = min(100_000, draws - done)
        composites = _items(_item_latent(size, p, weight, rng), condition).mean(axis=2)
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


def edge_threshold(partial: FloatMatrix) -> float | None:
    """Pre-specified edge rule: ring pairs above, other pairs below half the weakest ring edge.

    Returns None when the rule does not separate the two sets (cell not classifiable).
    """
    p = partial.shape[0]
    ring = {tuple(sorted((i, (i + 1) % p))) for i in range(p)}
    magnitudes = np.abs(partial)
    ring_values = [magnitudes[i, j] for i, j in ring]
    other_values = [
        magnitudes[i, j] for i in range(p) for j in range(i + 1, p) if (i, j) not in ring
    ]
    threshold = 0.5 * min(ring_values)
    if max(other_values) >= threshold:
        return None
    return float(threshold)


def generate_composite_dataset(
    n: int,
    p: int,
    strength: str,
    condition: str,
    contamination: str,
    seed: int,
    truth_draws: int = TRUTH_DRAWS,
) -> SimulatedDataset:
    """Generate one dataset; all condition and contamination cells share draws for a seed."""
    if strength not in STRENGTHS:
        raise ValueError(f"unknown strength: {strength}")
    if contamination not in CONTAMINATIONS:
        raise ValueError(f"unknown contamination: {contamination}")
    if n <= CONTAMINATED_COUNT:
        raise ValueError("n must exceed the number of contaminated respondents")
    rng = np.random.default_rng(seed)
    latent = _item_latent(n, p, STRENGTHS[strength], rng)
    cases = tuple(sorted(int(i) for i in rng.choice(n, CONTAMINATED_COUNT, replace=False)))
    items = _items(latent, condition)
    _contaminate(items, cases, contamination, condition, np.random.default_rng([seed, 99]))
    composites = items.mean(axis=2)
    covariance, precision, partial = composite_truth(p, strength, condition, truth_draws)
    planted = () if contamination == "none" else cases
    return SimulatedDataset(composites, covariance, precision, partial, planted, FOCAL_EDGE)
