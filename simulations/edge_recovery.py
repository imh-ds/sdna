"""Edge-recovery metrics: does an estimated network preserve true edge signs and ranks?"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from sdna.estimation import fit_network
from simulations.metrics import auc, spearman_correlation

FloatMatrix = NDArray[np.float64]

TRUE_EDGE_THRESHOLD = 1e-8


def ordinary_partial_correlation(X: FloatMatrix) -> FloatMatrix | None:
    """Return the unshrunk partial-correlation matrix, or None if not estimable."""
    n, p = X.shape
    if n <= p + 1:
        return None
    correlation = np.corrcoef(X, rowvar=False)
    if np.linalg.cond(correlation) > 1e12:
        return None
    precision = np.linalg.inv(correlation)
    scale = np.sqrt(np.outer(np.diag(precision), np.diag(precision)))
    partial = -precision / scale
    np.fill_diagonal(partial, 1.0)
    return np.asarray(partial, dtype=float)


def edge_recovery_metrics(
    estimated: FloatMatrix, truth: FloatMatrix
) -> dict[str, float | None]:
    """Compare estimated and true partial correlations over off-diagonal pairs.

    Sign agreement is computed over true edges only. The AUC asks how well
    ``abs(estimate)`` separates true edges from true non-edges. Metrics that need
    both classes (or non-constant inputs) are None rather than zero.
    """
    if estimated.shape != truth.shape or estimated.shape[0] != estimated.shape[1]:
        raise ValueError("estimated and truth must be square and equal-shaped")
    upper = np.triu_indices(truth.shape[0], k=1)
    est, true = estimated[upper], truth[upper]
    is_edge = np.abs(true) > TRUE_EDGE_THRESHOLD
    n_edges = int(is_edge.sum())

    sign_agreement: float | None = None
    if n_edges:
        sign_agreement = float(np.mean(np.sign(est[is_edge]) == np.sign(true[is_edge])))

    rank_corr: float | None = None
    if np.std(est) > 0.0 and np.std(true) > 0.0:
        rank_corr = spearman_correlation(est, true)

    edge_auc: float | None = None
    top_k_precision: float | None = None
    if 0 < n_edges < est.size:
        edge_auc = auc(is_edge.astype(int), np.abs(est))
        top = np.argsort(-np.abs(est), kind="stable")[:n_edges]
        top_k_precision = float(np.mean(is_edge[top]))

    edge_mask = is_edge
    magnitude_ratio: float | None = None
    if n_edges:
        magnitude_ratio = float(np.mean(np.abs(est[edge_mask])) / np.mean(np.abs(true[edge_mask])))

    return {
        "n_true_edges": float(n_edges),
        "sign_agreement": sign_agreement,
        "rank_correlation": rank_corr,
        "edge_auc": edge_auc,
        "top_k_precision": top_k_precision,
        "magnitude_ratio": magnitude_ratio,
    }


def recovery_row(X: FloatMatrix, truth: FloatMatrix) -> dict[str, float | None]:
    """Shrinkage-estimator and ordinary-partial recovery metrics on one dataset."""
    fitted = fit_network(X)
    shrunk = edge_recovery_metrics(fitted.partial_correlation, truth)
    row: dict[str, float | None] = {"lambda": fitted.shrinkage}
    row.update({f"shrunk_{key}": value for key, value in shrunk.items() if key != "n_true_edges"})
    row["n_true_edges"] = shrunk["n_true_edges"]
    ordinary = ordinary_partial_correlation(X)
    ordinary_metrics = (
        edge_recovery_metrics(ordinary, truth) if ordinary is not None else None
    )
    for key in ("sign_agreement", "rank_correlation", "edge_auc", "top_k_precision",
                "magnitude_ratio"):
        row[f"ordinary_{key}"] = None if ordinary_metrics is None else ordinary_metrics[key]
    return row
