"""Case-level influence calculations for fitted SDNA networks."""

import numpy as np

from sdna.estimation import fit_network
from sdna.results import InfluenceResult, NetworkFit
from sdna.validation import validate_data

__all__ = ["analytic_influence", "exact_loo_influence"]


def exact_loo_influence(X: np.ndarray, fitted: NetworkFit) -> InfluenceResult:
    """Calculate exact fixed-shrinkage leave-one-out deletion effects.

    Each returned value is the refitted partial correlation without case ``k``
    minus the full-sample partial correlation. The full-sample shrinkage
    intensity is passed to every refit, making this the authoritative v0.1
    case-influence result.
    """
    data = validate_data(X)
    n, p = data.shape
    if fitted.partial_correlation.shape != (p, p):
        raise ValueError("fitted network dimensions do not match X")
    if fitted.standardized.shape[0] != n:
        raise ValueError("fitted network row count does not match X")

    full_partial = fitted.partial_correlation
    changes = np.empty((n, p, p), dtype=float)
    for k in range(n):
        keep = np.arange(n) != k
        refit = fit_network(data[keep], shrinkage=fitted.shrinkage)
        delta = refit.partial_correlation - full_partial
        changes[k] = (delta + delta.T) / 2.0
        np.fill_diagonal(changes[k], 0.0)
    return InfluenceResult(changes=changes, method="exact_loo")


def analytic_influence(fitted: NetworkFit) -> InfluenceResult:
    """Calculate the first-order analytic deletion-effect approximation.

    This uses the influence-function chain rule through correlation,
    shrinkage, inversion, and the partial-correlation transform. It returns
    the same sign convention as exact LOO: approximate ``rho_without_k``
    minus full-sample ``rho``. It is an accelerator for ranking/search, never
    a replacement for exact LOO in user-facing results.
    """
    z = fitted.standardized
    precision = fitted.precision
    correlation = fitted.correlation
    partial = fitted.partial_correlation
    n, p = z.shape
    precision_diagonal = np.diag(precision)
    denominator = np.sqrt(np.outer(precision_diagonal, precision_diagonal))
    changes = np.empty((n, p, p), dtype=float)
    for k in range(n):
        row = z[k]
        squared = row**2
        derivative_correlation = np.outer(row, row) - 0.5 * (
            squared[:, None] * correlation + correlation * squared[None, :]
        )
        derivative_precision = -(1.0 - fitted.shrinkage) * (
            precision @ derivative_correlation @ precision
        )
        relative_diagonal = np.diag(derivative_precision) / precision_diagonal
        derivative_partial = (
            -derivative_precision / denominator
            - 0.5 * partial * (relative_diagonal[:, None] + relative_diagonal[None, :])
        )
        delta = -derivative_partial / (n - 1)
        changes[k] = (delta + delta.T) / 2.0
        np.fill_diagonal(changes[k], 0.0)
    return InfluenceResult(changes=changes, method="analytic")
