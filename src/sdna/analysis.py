"""High-level analysis for explicitly selected network edges."""

from collections.abc import Iterable

import numpy as np

from sdna.calibration import calibrate_fragility
from sdna.estimation import fit_network
from sdna.fragility import FragilityTarget, greedy_fragility
from sdna.influence import analytic_influence, exact_loo_influence
from sdna.results import EdgeAnalysis, NetworkFit
from sdna.validation import validate_data

__all__ = ["analyze_edges", "top_edges_by_magnitude"]


def top_edges_by_magnitude(fitted: NetworkFit, k: int) -> list[tuple[int, int]]:
    """Select the ``k`` strongest off-diagonal fitted edges explicitly."""
    if k < 1:
        raise ValueError("k must be positive")
    p = fitted.partial_correlation.shape[0]
    ranked = sorted(
        ((abs(float(fitted.partial_correlation[i, j])), (i, j))
         for i in range(p) for j in range(i + 1, p)),
        key=lambda item: (-item[0], item[1]),
    )
    return [edge for _, edge in ranked[:k]]


def analyze_edges(
    X: np.ndarray,
    edges: Iterable[tuple[int, int]],
    *,
    target: FragilityTarget,
    calibrate: bool = False,
    n_sim: int = 500,
    rng: np.random.Generator | None = None,
    shrinkage: float | None = None,
    search_cap: int | None = None,
    require_reached: bool = True,
) -> list[EdgeAnalysis]:
    """Analyze caller-supplied focal edges without hidden edge thresholds."""
    data = validate_data(X)
    requested = list(edges)
    if not requested:
        raise ValueError("edges must contain at least one explicitly selected edge")
    if len(set(requested)) != len(requested):
        raise ValueError("edges must not contain duplicates")

    fitted = fit_network(data, shrinkage=shrinkage)
    p = data.shape[1]
    for i, j in requested:
        if i == j or not (0 <= i < p and 0 <= j < p):
            raise ValueError("edges must contain distinct valid column indices")

    exact = exact_loo_influence(data, fitted)
    approximate = analytic_influence(fitted)
    results: list[EdgeAnalysis] = []
    for edge in requested:
        calibration = None
        if calibrate:
            calibration = calibrate_fragility(
                data,
                edge=edge,
                target=target,
                n_sim=n_sim,
                rng=rng,
                shrinkage=fitted.shrinkage,
                search_cap=search_cap,
                require_reached=require_reached,
            )
        fragility = greedy_fragility(
            data,
            edge=edge,
            target=target,
            shrinkage=fitted.shrinkage,
            search_cap=search_cap,
        )
        results.append(
            EdgeAnalysis(
                edge=edge,
                full_value=float(fitted.partial_correlation[edge]),
                influence=exact,
                analytic_influence=approximate,
                fragility=fragility,
                calibration=calibration,
            )
        )
    return results
