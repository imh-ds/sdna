"""Greedy edge-fragility search with explicit stopping semantics."""

import numpy as np

from sdna.estimation import fit_network
from sdna.influence import analytic_influence
from sdna.results import FragilityResult, FragilityTarget
from sdna.validation import validate_data

__all__ = ["FragilityTarget", "criterion_met", "greedy_fragility"]


def criterion_met(
    rho: float, rho_full: float, target: FragilityTarget, tol: float = 1e-12
) -> bool:
    """Return whether an edge value meets an explicit fragility target."""
    if target.kind == "relative":
        assert target.value is not None
        return abs(rho) <= target.value * abs(rho_full) + tol
    if target.kind == "absolute":
        assert target.value is not None
        return abs(rho) <= target.value + tol
    if target.kind == "sign_reversal":
        return rho * rho_full <= tol
    raise ValueError(f"unknown fragility target: {target.kind}")


def greedy_fragility(
    X: np.ndarray,
    edge: tuple[int, int],
    target: FragilityTarget,
    shrinkage: float | None = None,
    search_cap: int | None = None,
) -> FragilityResult:
    """Search for cases whose deletion reaches an edge-fragility target.

    Analytic influence ranks candidates, while every accepted deletion is
    verified with an exact fixed-shrinkage refit. If the cap is reached first,
    the result is censored: ``reached`` is false and ``greedy_count`` is None.
    """
    data = validate_data(X)
    n, p = data.shape
    i, j = edge
    if i == j or not (0 <= i < p and 0 <= j < p):
        raise ValueError("edge must contain two distinct valid column indices")
    if search_cap is not None and search_cap < 1:
        raise ValueError("search_cap must be positive")
    if n < 4:
        raise ValueError("fragility search requires at least 4 rows")

    full_fit = fit_network(data, shrinkage=shrinkage)
    lam = full_fit.shrinkage
    full_value = float(full_fit.partial_correlation[i, j])
    cap = min(max(3, n // 3), n - 3) if search_cap is None else min(search_cap, n - 3)
    retained = list(range(n))
    chosen: list[int] = []
    trajectory = [full_value]
    current_fit = full_fit

    for _ in range(cap):
        current_value = float(current_fit.partial_correlation[i, j])
        if criterion_met(current_value, full_value, target):
            return FragilityResult(
                edge=edge,
                target=target,
                full_value=full_value,
                reached=True,
                greedy_count=len(chosen),
                cases=tuple(chosen),
                trajectory=np.asarray(trajectory),
            )
        ranking = analytic_influence(current_fit).changes[:, i, j]
        direction = np.sign(full_value) or 1.0
        candidate_position = int(np.argmax(-direction * ranking))
        chosen.append(retained.pop(candidate_position))
        current_fit = fit_network(data[retained], shrinkage=lam)
        trajectory.append(float(current_fit.partial_correlation[i, j]))

    reached = criterion_met(trajectory[-1], full_value, target)
    return FragilityResult(
        edge=edge,
        target=target,
        full_value=full_value,
        reached=reached,
        greedy_count=len(chosen) if reached else None,
        cases=tuple(chosen),
        trajectory=np.asarray(trajectory),
    )
