"""Descriptive diagnostics for exact leave-one-out influence results."""

from math import ceil

import numpy as np

from sdna.results import InfluenceResult

__all__ = ["case_leverage", "edge_concentration"]


def _exact_changes(influence: InfluenceResult) -> np.ndarray:
    """Validate and return the changes from an exact-LOO result."""
    if influence.method != "exact_loo":
        raise ValueError("diagnostics require exact LOO influence results")
    changes = np.asarray(influence.changes, dtype=float)
    if changes.ndim != 3 or changes.shape[1] != changes.shape[2]:
        raise ValueError("influence changes must have shape (n_cases, n_nodes, n_nodes)")
    return changes


def _validate_edge(edge: tuple[int, int], node_count: int) -> tuple[int, int]:
    """Validate an undirected edge and return its ordered indices."""
    if len(edge) != 2:
        raise ValueError("edge must contain exactly two node indices")
    i, j = edge
    if not isinstance(i, (int, np.integer)) or not isinstance(j, (int, np.integer)):
        raise TypeError("edge indices must be integers")
    if i < 0 or j < 0 or i >= node_count or j >= node_count or i == j:
        raise ValueError("edge must contain two distinct valid node indices")
    return int(i), int(j)


def case_leverage(influence: InfluenceResult) -> np.ndarray:
    """Summarize each case's total absolute exact-LOO edge displacement.

    The sum uses each undirected edge once, so symmetric matrix entries are not
    double-counted. This is descriptive and is not an inferential statistic.
    """
    changes = _exact_changes(influence)
    upper = np.triu_indices(changes.shape[1], k=1)
    return np.asarray(np.sum(np.abs(changes[:, upper[0], upper[1]]), axis=1), dtype=float)


def edge_concentration(
    influence: InfluenceResult,
    edge: tuple[int, int],
    top_fraction: float = 0.05,
) -> float:
    """Return the share of an edge's change held by its largest cases.

    The numerator contains the largest ``ceil(n_cases * top_fraction)``
    absolute exact-LOO changes. A zero-change edge has concentration zero.
    """
    changes = _exact_changes(influence)
    if not 0.0 < top_fraction <= 1.0:
        raise ValueError("top_fraction must be greater than 0 and at most 1")
    i, j = _validate_edge(edge, changes.shape[1])

    absolute_changes = np.abs(changes[:, i, j])
    total = float(np.sum(absolute_changes))
    if total == 0.0:
        return 0.0
    top_count = ceil(len(absolute_changes) * top_fraction)
    largest = np.partition(absolute_changes, -top_count)[-top_count:]
    return float(np.sum(largest) / total)
