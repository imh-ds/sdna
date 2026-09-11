import numpy as np
import pytest

from sdna.estimation import fit_network


@pytest.mark.parametrize(
    "bad",
    [
        np.array([[1.0, np.nan], [2.0, 3.0]]),
        np.array([[1.0, np.inf], [2.0, 3.0]]),
    ],
)
def test_fit_rejects_nonfinite(bad: np.ndarray) -> None:
    with pytest.raises(ValueError, match="finite"):
        fit_network(bad)


def test_fit_rejects_constant_column() -> None:
    x = np.column_stack([np.arange(10.0), np.ones(10)])
    with pytest.raises(ValueError, match="zero variance"):
        fit_network(x)


def test_fit_rejects_invalid_shape() -> None:
    with pytest.raises(ValueError, match="2-D"):
        fit_network(np.ones(10))


def test_fit_rejects_too_few_rows() -> None:
    with pytest.raises(ValueError, match="at least 3 rows"):
        fit_network(np.ones((2, 2)))


def test_fit_network_invariants(gaussian_data: np.ndarray) -> None:
    fitted = fit_network(gaussian_data)

    assert 0.0 <= fitted.shrinkage <= 1.0
    np.testing.assert_allclose(fitted.correlation, fitted.correlation.T, atol=1e-12)
    np.testing.assert_allclose(fitted.shrunk_correlation, fitted.shrunk_correlation.T, atol=1e-12)
    np.testing.assert_allclose(fitted.precision, fitted.precision.T, atol=1e-12)
    np.testing.assert_allclose(fitted.partial_correlation, fitted.partial_correlation.T, atol=1e-12)
    np.testing.assert_allclose(np.diag(fitted.correlation), 1.0, atol=1e-12)
    np.testing.assert_allclose(np.diag(fitted.shrunk_correlation), 1.0, atol=1e-12)
    np.testing.assert_allclose(np.diag(fitted.partial_correlation), 1.0, atol=1e-12)
    np.testing.assert_allclose(
        fitted.precision @ fitted.shrunk_correlation,
        np.eye(fitted.partial_correlation.shape[0]),
        atol=1e-10,
    )


def test_fit_accepts_fixed_shrinkage(gaussian_data: np.ndarray) -> None:
    fitted = fit_network(gaussian_data, shrinkage=0.25)

    assert fitted.shrinkage == 0.25


def test_fit_rejects_invalid_shrinkage(gaussian_data: np.ndarray) -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        fit_network(gaussian_data, shrinkage=1.1)
