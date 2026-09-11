import numpy as np
import pytest

from sdna.calibration import _reference_tail_probability, _validated_generator_correlation
from sdna.estimation import fit_network
from sdna.fragility import FragilityTarget, criterion_met, greedy_fragility
from sdna.influence import analytic_influence, exact_loo_influence


def test_analytic_and_exact_influence_use_the_same_deletion_sign(
    gaussian_data: np.ndarray,
) -> None:
    fitted = fit_network(gaussian_data)
    exact = exact_loo_influence(gaussian_data, fitted).changes
    analytic = analytic_influence(fitted).changes
    upper = np.triu_indices(gaussian_data.shape[1], 1)

    correlation = np.corrcoef(
        exact[:, upper[0], upper[1]].ravel(), analytic[:, upper[0], upper[1]].ravel()
    )[0, 1]
    assert correlation > 0


def test_sign_reversal_is_not_numeric_zero() -> None:
    assert criterion_met(-0.02, 0.4, FragilityTarget("sign_reversal"))
    assert not criterion_met(0.02, 0.4, FragilityTarget("sign_reversal"))


def test_unreached_fragility_cap_is_censored(gaussian_data: np.ndarray) -> None:
    result = greedy_fragility(
        gaussian_data,
        edge=(0, 1),
        target=FragilityTarget("absolute", 0.0),
        search_cap=1,
    )

    assert not result.reached
    assert result.greedy_count is None
    assert len(result.cases) == 1


def test_calibration_generator_uses_unshrunk_empirical_correlation(
    gaussian_data: np.ndarray,
) -> None:
    fitted = fit_network(gaussian_data, shrinkage=0.25)
    generator = _validated_generator_correlation(fitted.correlation)

    np.testing.assert_allclose(generator, fitted.correlation, atol=1e-12)
    assert not np.allclose(generator, fitted.shrunk_correlation)


def test_reference_tail_uses_plus_one_correction() -> None:
    assert _reference_tail_probability(2, [1, 2, 4]) == pytest.approx(0.75)


def test_genuine_edge_simulation_checks_population_precision_matrix() -> None:
    covariance = np.eye(3)
    covariance[0, 1] = covariance[1, 0] = 0.4
    precision = np.linalg.inv(covariance)

    assert precision[0, 1] != pytest.approx(0.0)
