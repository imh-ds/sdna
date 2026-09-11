import numpy as np
import pytest

from sdna.estimation import fit_network
from sdna.influence import exact_loo_influence


def test_exact_loo_is_rho_without_case_minus_full(gaussian_data: np.ndarray) -> None:
    fitted = fit_network(gaussian_data)
    result = exact_loo_influence(gaussian_data, fitted)
    k, i, j = 2, 0, 1
    keep = np.arange(len(gaussian_data)) != k
    refit = fit_network(gaussian_data[keep], shrinkage=fitted.shrinkage)
    expected = refit.partial_correlation[i, j] - fitted.partial_correlation[i, j]

    assert result.method == "exact_loo"
    assert result.changes[k, i, j] == pytest.approx(expected)


def test_exact_loo_refits_use_full_sample_shrinkage(
    gaussian_data: np.ndarray, monkeypatch: pytest.MonkeyPatch
) -> None:
    fitted = fit_network(gaussian_data)
    seen: list[float | None] = []
    original_fit_network = fit_network

    def recording_fit(data: np.ndarray, shrinkage: float | None = None):
        seen.append(shrinkage)
        return original_fit_network(data, shrinkage=shrinkage)

    monkeypatch.setattr("sdna.influence.fit_network", recording_fit)
    exact_loo_influence(gaussian_data, fitted)

    assert seen == [fitted.shrinkage] * len(gaussian_data)


def test_exact_loo_changes_are_symmetric_with_zero_diagonal(
    gaussian_data: np.ndarray,
) -> None:
    result = exact_loo_influence(gaussian_data, fit_network(gaussian_data))

    np.testing.assert_allclose(result.changes, np.swapaxes(result.changes, 1, 2), atol=1e-12)
    np.testing.assert_allclose(np.diagonal(result.changes, axis1=1, axis2=2), 0.0, atol=1e-12)
