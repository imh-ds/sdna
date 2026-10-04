"""Python approximation of qgraph::EBICglasso (not validated against qgraph; see the study protocol)."""

from __future__ import annotations

import warnings

import numpy as np
from numpy.typing import NDArray
from sklearn.covariance import graphical_lasso
from sklearn.exceptions import ConvergenceWarning

FloatMatrix = NDArray[np.float64]


def ebic_glasso(
    X: FloatMatrix, gamma: float = 0.5, n_lambda: int = 100, lambda_min_ratio: float = 0.01
) -> tuple[FloatMatrix, int]:
    """Return (partial-correlation matrix, number of selected edges) at the EBIC optimum."""
    n, p = X.shape
    S = np.corrcoef(X, rowvar=False)
    off = np.abs(S[np.triu_indices(p, k=1)])
    lam_max = float(off.max())
    if lam_max <= 0.0:
        return np.eye(p), 0
    alphas = np.exp(np.linspace(np.log(lam_max), np.log(lam_max * lambda_min_ratio), n_lambda))
    upper = np.triu_indices(p, k=1)
    best_ebic, best_precision = np.inf, np.eye(p)
    for alpha in alphas:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", ConvergenceWarning)
                _, precision = graphical_lasso(S, alpha=float(alpha), max_iter=200)
        except (FloatingPointError, np.linalg.LinAlgError):
            continue
        sign, logdet = np.linalg.slogdet(precision)
        if sign <= 0:
            continue
        edges = int(np.count_nonzero(np.abs(precision[upper]) > 1e-10))
        loglik = n / 2.0 * (logdet - float(np.trace(S @ precision)))
        ebic = -2.0 * loglik + edges * np.log(n) + 4.0 * gamma * edges * np.log(p)
        if ebic < best_ebic:
            best_ebic, best_precision = ebic, precision
    diagonal = np.sqrt(np.diag(best_precision))
    partial = -best_precision / np.outer(diagonal, diagonal)
    np.fill_diagonal(partial, 1.0)
    partial[np.abs(best_precision) <= 1e-10] = 0.0
    np.fill_diagonal(partial, 1.0)
    return partial, int(np.count_nonzero(np.abs(best_precision[upper]) > 1e-10))
