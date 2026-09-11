import numpy as np
import pytest

from sdna.estimation import fit_network
from sdna.influence import analytic_influence, exact_loo_influence


def _gaussian_data(n: int, p: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    factors = rng.normal(size=(n, 2))
    loadings = rng.normal(size=(2, p)) * 0.35
    return rng.normal(size=(n, p)) + factors @ loadings


@pytest.mark.parametrize("n,p", [(60, 8), (100, 12), (150, 15)])
def test_analytic_influence_tracks_exact_loo(n: int, p: int) -> None:
    data = _gaussian_data(n, p, seed=20260910 + n + p)
    fitted = fit_network(data)
    exact = exact_loo_influence(data, fitted).changes
    approx_result = analytic_influence(fitted)
    iu = np.triu_indices(p, 1)
    approx = approx_result.changes[:, iu[0], iu[1]].ravel()
    observed = exact[:, iu[0], iu[1]].ravel()

    assert approx_result.method == "analytic"
    assert np.corrcoef(approx, observed)[0, 1] > 0.995


def test_analytic_influence_uses_deletion_effect_sign(gaussian_data: np.ndarray) -> None:
    fitted = fit_network(gaussian_data)
    result = analytic_influence(fitted)
    exact = exact_loo_influence(gaussian_data, fitted)
    iu = np.triu_indices(gaussian_data.shape[1], 1)
    approx = result.changes[:, iu[0], iu[1]].ravel()
    observed = exact.changes[:, iu[0], iu[1]].ravel()

    assert np.corrcoef(approx, observed)[0, 1] > 0.0


def test_exact_loo_remains_authoritative_for_high_leverage_case() -> None:
    rng = np.random.default_rng(20260910)
    data = rng.normal(size=(30, 4))
    data[0] = np.array([20.0, -20.0, 20.0, -20.0])
    fitted = fit_network(data)

    exact = exact_loo_influence(data, fitted)
    approx = analytic_influence(fitted)

    assert exact.method == "exact_loo"
    assert approx.method == "analytic"
    assert not np.allclose(exact.changes, approx.changes)
