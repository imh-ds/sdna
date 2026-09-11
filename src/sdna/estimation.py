"""Shrinkage partial-correlation network estimation."""

from warnings import warn

import numpy as np

from sdna.results import NetworkDiagnostics, NetworkFit
from sdna.validation import validate_data, validate_shrinkage

__all__ = ["estimate_shrinkage", "fit_network"]


def _standardize(X: np.ndarray) -> np.ndarray:
    return (X - X.mean(axis=0)) / X.std(axis=0, ddof=1)


def estimate_shrinkage(X: np.ndarray) -> float:
    """Estimate analytic shrinkage intensity toward the identity matrix."""
    data = validate_data(X)
    z = _standardize(data)
    n, p = z.shape
    r = (z.T @ z) / (n - 1)
    numerator = 0.0
    denominator = 0.0
    for i in range(p):
        for j in range(i + 1, p):
            w = z[:, i] * z[:, j]
            var_r = (n / (n - 1) ** 3) * np.sum((w - w.mean()) ** 2)
            numerator += 2.0 * var_r
            denominator += 2.0 * r[i, j] ** 2
    if denominator == 0.0:
        return 1.0
    return float(np.clip(numerator / denominator, 0.0, 1.0))


def fit_network(X: np.ndarray, shrinkage: float | None = None) -> NetworkFit:
    """Fit a shrinkage partial-correlation network.

    When refitting subsets, pass the full-sample ``shrinkage`` value so that
    regularization changes do not confound deletion effects.
    """
    data = validate_data(X)
    z = _standardize(data)
    n, p = z.shape
    correlation = (z.T @ z) / (n - 1)
    lam = estimate_shrinkage(data) if shrinkage is None else validate_shrinkage(shrinkage)
    shrunk = (1.0 - lam) * correlation + lam * np.eye(p)
    precision = np.linalg.inv(shrunk)
    precision = (precision + precision.T) / 2.0
    diagonal = np.diag(precision)
    partial = -precision / np.sqrt(np.outer(diagonal, diagonal))
    np.fill_diagonal(partial, 1.0)

    if p >= n:
        warn("number of variables is at least the number of observations", RuntimeWarning)
    diagnostics = NetworkDiagnostics(
        rank=int(np.linalg.matrix_rank(correlation)),
        min_eigenvalue_correlation=float(np.min(np.linalg.eigvalsh(correlation))),
        min_eigenvalue_shrunk_correlation=float(np.min(np.linalg.eigvalsh(shrunk))),
        condition_number=float(np.linalg.cond(shrunk)),
    )
    return NetworkFit(
        standardized=z,
        correlation=correlation,
        shrunk_correlation=shrunk,
        precision=precision,
        partial_correlation=partial,
        shrinkage=lam,
        diagnostics=diagnostics,
    )
