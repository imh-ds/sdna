"""Reproducible, truth-aware data-generating processes for SDNA."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SimulatedDataset:
    """Simulated observations with population covariance truth and metadata.

    For a mixture DGP, the covariance and precision describe the overall
    mixture-weighted second-moment distribution, not only one subgroup.
    """

    X: np.ndarray
    covariance: np.ndarray
    precision: np.ndarray
    partial_correlation: np.ndarray
    contaminated_cases: tuple[int, ...]
    focal_edge: tuple[int, int]


def _validate_dimensions(n: int, p: int, edge: tuple[int, int]) -> None:
    if n < 3:
        raise ValueError("n must be at least 3")
    if p < 2:
        raise ValueError("p must be at least 2")
    i, j = edge
    if i == j or not (0 <= i < p and 0 <= j < p):
        raise ValueError("focal_edge must contain distinct valid indices")


def construct_precision(
    p: int,
    edges: dict[tuple[int, int], float],
    diagonal_margin: float = 0.5,
) -> np.ndarray:
    """Construct a symmetric strictly diagonally dominant precision matrix."""
    if p < 2 or diagonal_margin <= 0.0:
        raise ValueError("p must be at least 2 and diagonal_margin must be positive")
    precision = np.zeros((p, p), dtype=float)
    for (i, j), value in edges.items():
        if i == j or not (0 <= i < p and 0 <= j < p):
            raise ValueError("edges must contain distinct valid indices")
        if not np.isfinite(value):
            raise ValueError("edge weights must be finite")
        precision[i, j] = precision[j, i] = -float(value)
    for i in range(p):
        precision[i, i] = np.sum(np.abs(precision[i])) + diagonal_margin
    return precision


def _population_from_precision(precision: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    covariance = np.linalg.inv(precision)
    scale = np.sqrt(np.diag(covariance))
    covariance = covariance / np.outer(scale, scale)
    precision = np.linalg.inv(covariance)
    partial = -precision / np.sqrt(np.outer(np.diag(precision), np.diag(precision)))
    np.fill_diagonal(partial, 1.0)
    return covariance, partial


def _single_edge_model(
    p: int, edge: tuple[int, int], partial: float
) -> tuple[np.ndarray, np.ndarray]:
    if not -1.0 < partial < 1.0:
        raise ValueError("partial must be strictly between -1 and 1")
    precision = np.eye(p)
    i, j = edge
    precision[i, j] = precision[j, i] = -partial
    covariance, population_partial = _population_from_precision(precision)
    return covariance, population_partial


def _dataset(
    X: np.ndarray,
    covariance: np.ndarray,
    focal_edge: tuple[int, int],
    contaminated_cases: tuple[int, ...] = (),
) -> SimulatedDataset:
    precision = np.linalg.inv(covariance)
    partial = -precision / np.sqrt(np.outer(np.diag(precision), np.diag(precision)))
    np.fill_diagonal(partial, 1.0)
    return SimulatedDataset(X, covariance, precision, partial, contaminated_cases, focal_edge)


def clean_planted_edge(
    n: int,
    p: int,
    rng: np.random.Generator,
    focal_edge: tuple[int, int] = (0, 1),
    partial: float = 0.4,
) -> SimulatedDataset:
    """Generate a clean dataset with a known nonzero focal partial edge."""
    _validate_dimensions(n, p, focal_edge)
    covariance, _ = _single_edge_model(p, focal_edge, partial)
    return _dataset(
        rng.multivariate_normal(np.zeros(p), covariance, size=n), covariance, focal_edge
    )


def single_influential_case(
    n: int,
    p: int,
    rng: np.random.Generator,
    focal_edge: tuple[int, int] = (0, 1),
    shift: float = 4.0,
) -> SimulatedDataset:
    """Generate a null focal edge with one shifted observation."""
    _validate_dimensions(n, p, focal_edge)
    covariance, _ = _single_edge_model(p, focal_edge, 0.0)
    X = rng.multivariate_normal(np.zeros(p), covariance, size=n)
    index = int(rng.integers(0, n))
    i, j = focal_edge
    X[index, [i, j]] += shift
    return _dataset(X, covariance, focal_edge, (index,))


def coalition_contamination(
    n: int,
    p: int,
    rng: np.random.Generator,
    n_contaminated: int = 3,
    focal_edge: tuple[int, int] = (0, 1),
    shift: float = 4.0,
) -> SimulatedDataset:
    """Generate a null focal edge with a known shifted coalition."""
    _validate_dimensions(n, p, focal_edge)
    if not 1 <= n_contaminated < n:
        raise ValueError("n_contaminated must be between 1 and n-1")
    covariance, _ = _single_edge_model(p, focal_edge, 0.0)
    X = rng.multivariate_normal(np.zeros(p), covariance, size=n)
    indices = tuple(sorted(rng.choice(n, size=n_contaminated, replace=False).tolist()))
    i, j = focal_edge
    X[np.ix_(list(indices), [i, j])] += shift
    return _dataset(X, covariance, focal_edge, indices)


def mixture_subgroup(
    n: int,
    p: int,
    rng: np.random.Generator,
    subgroup_fraction: float = 0.15,
    focal_edge: tuple[int, int] = (0, 1),
    subgroup_partial: float = 0.6,
) -> SimulatedDataset:
    """Generate a mixture where a known subgroup follows another covariance."""
    _validate_dimensions(n, p, focal_edge)
    if not 0.0 < subgroup_fraction < 1.0:
        raise ValueError("subgroup_fraction must be between 0 and 1")
    subgroup_size = max(1, int(round(n * subgroup_fraction)))
    base_covariance, _ = _single_edge_model(p, focal_edge, 0.0)
    subgroup_covariance, _ = _single_edge_model(p, focal_edge, subgroup_partial)
    indices = tuple(sorted(rng.choice(n, size=subgroup_size, replace=False).tolist()))
    X = rng.multivariate_normal(np.zeros(p), base_covariance, size=n)
    X[list(indices)] = rng.multivariate_normal(
        np.zeros(p), subgroup_covariance, size=subgroup_size
    )
    subgroup_weight = subgroup_size / n
    mixture_covariance = (
        (1.0 - subgroup_weight) * base_covariance
        + subgroup_weight * subgroup_covariance
    )
    return _dataset(X, mixture_covariance, focal_edge, indices)


def heavy_tails(
    n: int,
    p: int,
    rng: np.random.Generator,
    degrees_of_freedom: float = 5.0,
    focal_edge: tuple[int, int] = (0, 1),
) -> SimulatedDataset:
    """Generate continuous multivariate t-like observations without labels."""
    _validate_dimensions(n, p, focal_edge)
    if degrees_of_freedom <= 2.0:
        raise ValueError("degrees_of_freedom must exceed 2")
    covariance, _ = _single_edge_model(p, focal_edge, 0.4)
    normal = rng.multivariate_normal(np.zeros(p), covariance, size=n)
    scales = np.sqrt(rng.chisquare(degrees_of_freedom, size=n) / degrees_of_freedom)
    return _dataset(normal / scales[:, None], covariance, focal_edge)


def collinearity_stress(
    n: int,
    p: int,
    rng: np.random.Generator,
    adjacent_correlation: float = 0.95,
    focal_edge: tuple[int, int] = (0, 1),
) -> SimulatedDataset:
    """Generate a valid near-collinear Gaussian covariance structure."""
    _validate_dimensions(n, p, focal_edge)
    if not 0.0 < adjacent_correlation < 1.0:
        raise ValueError("adjacent_correlation must be between 0 and 1")
    covariance = np.fromfunction(
        lambda i, j: adjacent_correlation ** np.abs(i - j), (p, p), dtype=float
    )
    return _dataset(
        rng.multivariate_normal(np.zeros(p), covariance, size=n), covariance, focal_edge
    )
