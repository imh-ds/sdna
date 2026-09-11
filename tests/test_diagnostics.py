"""Tests for descriptive exact-LOO influence diagnostics."""

import numpy as np
import pytest

from sdna.diagnostics import case_leverage, edge_concentration
from sdna.results import InfluenceResult


def _influence(edge_values: np.ndarray, method: str = "exact_loo") -> InfluenceResult:
    """Build symmetric influence matrices from upper-triangle edge values."""
    n, edge_count = edge_values.shape
    changes = np.zeros((n, 3, 3), dtype=float)
    upper = np.triu_indices(3, 1)
    if edge_count != len(upper[0]):
        raise ValueError("test fixture must provide all three edges")
    changes[:, upper[0], upper[1]] = edge_values
    changes[:, upper[1], upper[0]] = edge_values
    return InfluenceResult(changes=changes, method=method)


def test_case_leverage_sums_absolute_unique_edge_changes() -> None:
    influence = _influence(np.array([[1.0, -2.0, 3.0], [4.0, 0.5, -1.0]]))

    np.testing.assert_allclose(case_leverage(influence), [6.0, 5.5])


def test_edge_concentration_uses_top_fraction_of_absolute_changes() -> None:
    influence = _influence(
        np.array([[1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [7.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
    )

    assert edge_concentration(influence, (0, 1), top_fraction=0.5) == pytest.approx(0.9)


def test_edge_concentration_rounds_top_case_count_up() -> None:
    values = np.arange(1.0, 21.0)[:, None]
    influence = _influence(np.hstack([values, np.zeros((20, 2))]))

    assert edge_concentration(influence, (0, 1)) == pytest.approx(20.0 / sum(range(1, 21)))


def test_diagnostics_require_exact_loo() -> None:
    influence = _influence(np.ones((2, 3)), method="analytic")

    with pytest.raises(ValueError, match="exact LOO"):
        case_leverage(influence)
    with pytest.raises(ValueError, match="exact LOO"):
        edge_concentration(influence, (0, 1))


def test_edge_concentration_validates_edge_and_fraction() -> None:
    influence = _influence(np.ones((2, 3)))

    with pytest.raises(ValueError, match="edge"):
        edge_concentration(influence, (0, 3))
    with pytest.raises(ValueError, match="top_fraction"):
        edge_concentration(influence, (0, 1), top_fraction=0.0)
    with pytest.raises(ValueError, match="top_fraction"):
        edge_concentration(influence, (0, 1), top_fraction=1.1)


def test_edge_concentration_is_zero_when_edge_has_no_change() -> None:
    influence = _influence(np.zeros((4, 3)))

    assert edge_concentration(influence, (1, 2)) == 0.0
