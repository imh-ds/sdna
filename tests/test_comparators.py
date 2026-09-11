from typing import cast

import numpy as np
import pytest

from simulations.comparators.bootstrap import shrinkage_bootstrap
from simulations.comparators.wald import wald_partial_correlation


def test_shrinkage_bootstrap_is_deterministic(gaussian_data: np.ndarray) -> None:
    first = shrinkage_bootstrap(
        gaussian_data, edge=(0, 1), n_boot=5, rng=np.random.default_rng(13)
    )
    second = shrinkage_bootstrap(
        gaussian_data, edge=(0, 1), n_boot=5, rng=np.random.default_rng(13)
    )

    assert first.method == "shrinkage_bootstrap"
    assert first.shrinkage_mode == "fixed_lambda"
    assert first.samples.shape == (5,)
    np.testing.assert_array_equal(first.samples, second.samples)
    assert first.confidence_interval == second.confidence_interval


def test_bootstrap_can_reestimate_lambda(gaussian_data: np.ndarray) -> None:
    result = shrinkage_bootstrap(
        gaussian_data,
        edge=(0, 1),
        n_boot=3,
        rng=np.random.default_rng(14),
        reestimate_shrinkage=True,
    )

    assert result.shrinkage_mode == "reestimated_lambda"


def test_bootstrap_redraws_degenerate_resamples(gaussian_data: np.ndarray) -> None:
    class DegenerateFirstRng:
        def __init__(self) -> None:
            self.calls = 0

        def integers(self, low: int, high: int, size: int) -> np.ndarray:
            del low
            self.calls += 1
            if self.calls == 1:
                return np.zeros(size, dtype=int)
            return np.arange(size, dtype=int) % high

    result = shrinkage_bootstrap(
        gaussian_data,
        edge=(0, 1),
        n_boot=2,
        rng=cast(np.random.Generator, DegenerateFirstRng()),
    )

    assert result.rejected_resamples == 1
    assert result.samples.shape == (2,)


def test_wald_benchmark_labels_ordinary_partial_assumption(gaussian_data: np.ndarray) -> None:
    result = wald_partial_correlation(gaussian_data, edge=(0, 1))

    assert result.method == "wald_like"
    assert result.standard_error > 0.0
    assert result.assumption == "ordinary_partial_correlation"
    assert result.confidence_interval[0] < result.estimate < result.confidence_interval[1]


def test_comparators_validate_bootstrap_count(gaussian_data: np.ndarray) -> None:
    with pytest.raises(ValueError, match="positive"):
        shrinkage_bootstrap(gaussian_data, edge=(0, 1), n_boot=0)
