"""Model-based reference calibration for edge fragility."""

import numpy as np

from sdna.estimation import fit_network
from sdna.exceptions import CalibrationError
from sdna.fragility import greedy_fragility
from sdna.results import CalibrationResult, FragilityTarget
from sdna.validation import validate_data

__all__ = ["calibrate_fragility"]


def _reference_tail_probability(
    observed_count: int | None, reference_counts: list[int | None]
) -> float | None:
    if observed_count is None or any(count is None for count in reference_counts):
        return None
    counts = np.asarray(reference_counts, dtype=int)
    return float((1 + np.count_nonzero(counts <= observed_count)) / (len(counts) + 1))


def _validated_generator_correlation(correlation: np.ndarray) -> np.ndarray:
    symmetric = (correlation + correlation.T) / 2.0
    eigenvalues = np.linalg.eigvalsh(symmetric)
    tolerance = 1e-10
    if float(np.min(eigenvalues)) < -tolerance:
        raise CalibrationError("generator correlation must be positive semidefinite")
    if np.min(eigenvalues) < 0.0:
        values, vectors = np.linalg.eigh(symmetric)
        symmetric = vectors @ np.diag(np.clip(values, 0.0, None)) @ vectors.T
        diagonal = np.sqrt(np.diag(symmetric))
        symmetric = symmetric / np.outer(diagonal, diagonal)
    return symmetric


def calibrate_fragility(
    X: np.ndarray,
    edge: tuple[int, int],
    target: FragilityTarget,
    n_sim: int = 200,
    rng: np.random.Generator | None = None,
    shrinkage: float | None = None,
    search_cap: int | None = None,
    require_reached: bool = True,
) -> CalibrationResult:
    """Calibrate observed fragility against clean matched reference data."""
    if n_sim < 1:
        raise ValueError("n_sim must be positive")
    data = validate_data(X)
    fitted = fit_network(data, shrinkage=shrinkage)
    generator = _validated_generator_correlation(fitted.correlation)
    random = np.random.default_rng() if rng is None else rng
    i, j = edge
    observed = greedy_fragility(
        data, edge=edge, target=target, shrinkage=fitted.shrinkage, search_cap=search_cap
    )
    reference_counts: list[int | None] = []
    reference_reached: list[bool] = []
    reference_edge_estimates = np.empty(n_sim, dtype=float)
    for index in range(n_sim):
        simulated = random.multivariate_normal(np.zeros(data.shape[1]), generator, size=len(data))
        simulated_fit = fit_network(simulated, shrinkage=fitted.shrinkage)
        reference_edge_estimates[index] = simulated_fit.partial_correlation[i, j]
        reference = greedy_fragility(
            simulated,
            edge=edge,
            target=target,
            shrinkage=fitted.shrinkage,
            search_cap=search_cap,
        )
        reference_counts.append(reference.greedy_count)
        reference_reached.append(reference.reached)

    if require_reached and (not observed.reached or not all(reference_reached)):
        raise CalibrationError(
            "calibration requires observed and reference fragility searches to reach the target"
        )
    probability = _reference_tail_probability(observed.greedy_count, reference_counts)
    return CalibrationResult(
        edge=edge,
        target=target,
        observed_count=observed.greedy_count,
        observed_reached=observed.reached,
        reference_counts=tuple(reference_counts),
        reference_reached=tuple(reference_reached),
        reference_edge_estimates=reference_edge_estimates,
        reference_tail_probability=probability,
    )
