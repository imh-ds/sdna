"""Sparse modular data generator for the Task 27 operating-envelope study."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

import numpy as np
from numpy.typing import NDArray

from simulations.dgp import SimulatedDataset

FloatMatrix = NDArray[np.float64]

SUPPORTED_P = (20, 40, 60)
FOCAL_CONTEXTS = ("within_community", "hub_adjacent", "bridge")
CONDITIONS = ("clean", "single_case", "coalition")
FOCAL_EDGES: Mapping[str, tuple[int, int]] = MappingProxyType(
    {
        "within_community": (1, 2),
        "hub_adjacent": (0, 2),
        "bridge": (4, 5),
    }
)
EDGE_PRECISION = -0.05
CONTAMINATION_SHIFT = 4.0


@dataclass(frozen=True)
class LocalizedNetworkPopulation:
    """Population matrices and fixed focal-edge truth for one network size."""

    covariance: FloatMatrix
    precision: FloatMatrix
    partial_correlation: FloatMatrix
    focal_edges: Mapping[str, tuple[int, int]]
    module_count: int


def _validate_p(p: int) -> None:
    if isinstance(p, bool) or not isinstance(p, (int, np.integer)) or p not in SUPPORTED_P:
        raise ValueError(f"p must be one of {SUPPORTED_P}")


def build_localized_population(p: int) -> LocalizedNetworkPopulation:
    """Build the fixed five-node modular graph and its Gaussian population."""
    _validate_p(p)
    p = int(p)
    module_count = p // 5
    precision = np.eye(p, dtype=float)

    for module_start in range(0, p, 5):
        # A five-node ring, followed by spokes from node zero to every other node.
        for offset in range(5):
            left = module_start + offset
            right = module_start + (offset + 1) % 5
            precision[left, right] = precision[right, left] = EDGE_PRECISION
        for node in range(module_start + 1, module_start + 5):
            precision[module_start, node] = precision[node, module_start] = EDGE_PRECISION

    # Each adjacent pair of modules gets one bridge from the earlier module's
    # last node to the next module's designated hub.
    for module_start in range(0, p - 5, 5):
        left, right = module_start + 4, module_start + 5
        precision[left, right] = precision[right, left] = EDGE_PRECISION

    covariance = np.linalg.inv(precision)
    partial_correlation = -precision.copy()
    scale = np.sqrt(np.outer(np.diag(precision), np.diag(precision)))
    partial_correlation /= scale
    np.fill_diagonal(partial_correlation, 1.0)

    return LocalizedNetworkPopulation(
        covariance=covariance,
        precision=precision,
        partial_correlation=partial_correlation,
        focal_edges=FOCAL_EDGES,
        module_count=module_count,
    )


def _validate_generation_inputs(
    n: int, p: int, focal_context: str, condition: str, seed: int
) -> tuple[int, int]:
    if isinstance(n, bool) or not isinstance(n, (int, np.integer)) or n < 3:
        raise ValueError("n must be an integer of at least 3")
    _validate_p(p)
    if focal_context not in FOCAL_EDGES:
        raise ValueError(f"focal_context must be one of {FOCAL_CONTEXTS}")
    if condition not in CONDITIONS:
        raise ValueError(f"condition must be one of {CONDITIONS}")
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    return int(n), int(p)


def generate_localized_dataset(
    n: int,
    p: int,
    focal_context: str,
    condition: str,
    seed: int,
) -> SimulatedDataset:
    """Generate shared clean observations and apply context-specific case shifts.

    The clean-data and case-selection streams are independent children of the
    supplied data/case seed. As a result, changing only ``focal_context`` leaves
    both the unshifted observations and planted-case indices unchanged.
    """
    n, p = _validate_generation_inputs(n, p, focal_context, condition, seed)
    population = build_localized_population(p)
    data_sequence, case_sequence = np.random.SeedSequence(int(seed)).spawn(2)
    data_rng = np.random.default_rng(data_sequence)
    case_rng = np.random.default_rng(case_sequence)

    X = data_rng.multivariate_normal(np.zeros(p), population.covariance, size=n)
    contamination_count = {"clean": 0, "single_case": 1, "coalition": 3}[condition]
    if contamination_count:
        cases = tuple(
            sorted(
                int(case)
                for case in case_rng.choice(n, size=contamination_count, replace=False)
            )
        )
        focal_i, focal_j = population.focal_edges[focal_context]
        X[np.ix_(cases, [focal_i, focal_j])] += CONTAMINATION_SHIFT
    else:
        cases = ()

    return SimulatedDataset(
        X=X,
        covariance=population.covariance,
        precision=population.precision,
        partial_correlation=population.partial_correlation,
        contaminated_cases=cases,
        focal_edge=population.focal_edges[focal_context],
    )
