"""Case-level influence calculations for fitted SDNA networks."""

import numpy as np

from sdna.estimation import fit_network
from sdna.results import InfluenceResult, NetworkFit
from sdna.validation import validate_data

__all__ = ["exact_loo_influence"]


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
