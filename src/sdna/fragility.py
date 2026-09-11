"""Greedy edge-fragility search with explicit stopping semantics."""

from dataclasses import replace
from itertools import combinations
from math import comb
from collections.abc import Iterable

import numpy as np

from sdna.estimation import fit_network
from sdna.influence import analytic_influence
from sdna.results import FragilityResult, FragilityTarget
from sdna.validation import validate_data, validate_shrinkage

__all__ = [
    "FragilityTarget",
    "certify_fragility",
    "criterion_met",
    "fragility_profile",
    "greedy_fragility",
]


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
                shrinkage=lam,
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
        shrinkage=lam,
    )


def fragility_profile(
    X: np.ndarray,
    edge: tuple[int, int],
    fractions: Iterable[float],
    shrinkage: float | None = None,
    search_cap: int | None = None,
) -> dict[float, FragilityResult]:
    """Run independent relative-fragility searches for explicit fractions.

    The returned dictionary preserves the input order. Every fraction gets a
    separate search and result, so its selected coalition is target-specific.
    Defaults belong in reporting code; this low-level function requires the
    caller to provide the fractions explicitly.
    """
    requested = tuple(float(fraction) for fraction in fractions)
    if not requested:
        raise ValueError("fractions must contain at least one value")
    if len(set(requested)) != len(requested):
        raise ValueError("fractions must not contain duplicates")
    if any(not np.isfinite(fraction) or not 0.0 < fraction < 1.0 for fraction in requested):
        raise ValueError("fractions must be between 0 and 1")

    return {
        fraction: greedy_fragility(
            X,
            edge=edge,
            target=FragilityTarget("relative", fraction),
            shrinkage=shrinkage,
            search_cap=search_cap,
        )
        for fraction in requested
    }


def certify_fragility(
    X: np.ndarray,
    greedy: FragilityResult,
    shrinkage: float | None = None,
    max_combinations: int = 200_000,
) -> FragilityResult:
    """Certify the exact minimum below a reached greedy upper bound.

    Complete subset sizes are enumerated from one through (but excluding) the
    greedy count. If the next complete size exceeds the budget, enumeration
    stops before that size begins and the result remains uncertified.
    """
    if not greedy.reached or greedy.greedy_count is None:
        raise ValueError("greedy result must have reached the target before certification")
    if max_combinations < 1:
        raise ValueError("max_combinations must be positive")

    stored_shrinkage = validate_shrinkage(greedy.shrinkage)
    effective_shrinkage = (
        stored_shrinkage if shrinkage is None else validate_shrinkage(shrinkage)
    )
    if not np.isclose(effective_shrinkage, stored_shrinkage, rtol=0.0, atol=1e-15):
        raise ValueError("certification shrinkage does not match the greedy result")

    data = validate_data(X)
    n, p = data.shape
    i, j = greedy.edge
    if not (0 <= i < p and 0 <= j < p and i != j):
        raise ValueError("greedy result contains an invalid edge")
    full_fit = fit_network(data, shrinkage=effective_shrinkage)
    full_value = float(full_fit.partial_correlation[i, j])
    checked = 0

    for size in range(1, greedy.greedy_count):
        size_total = comb(n, size)
        if checked + size_total > max_combinations:
            return replace(
                greedy,
                certified=False,
                exact_minimum=None,
                combinations_checked=checked,
            )
        for dropped in combinations(range(n), size):
            keep = np.ones(n, dtype=bool)
            keep[list(dropped)] = False
            candidate = fit_network(data[keep], shrinkage=full_fit.shrinkage)
            checked += 1
            value = float(candidate.partial_correlation[i, j])
            if criterion_met(value, full_value, greedy.target):
                return replace(
                    greedy,
                    cases=tuple(dropped),
                    exact_minimum=size,
                    certified=True,
                    combinations_checked=checked,
                )

    return replace(
        greedy,
        exact_minimum=greedy.greedy_count,
        certified=True,
        combinations_checked=checked,
    )
