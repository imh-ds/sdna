"""Wald-like ordinary partial-correlation comparator."""

from dataclasses import dataclass
from statistics import NormalDist

import numpy as np

from sdna.estimation import fit_network
from sdna.validation import validate_data


@dataclass(frozen=True)
class WaldResult:
    """Approximate estimate, uncertainty, and normal-theory interval."""

    estimate: float
    standard_error: float
    z: float
    confidence_interval: tuple[float, float]
    method: str
    assumption: str


def wald_partial_correlation(
    X: np.ndarray, edge: tuple[int, int], confidence: float = 0.95
) -> WaldResult:
    """Calculate a Wald-like interval under an ordinary-partial assumption.

    The standard error ``(1-rho**2)/sqrt(N-p)`` is a benchmark approximation;
    it does not account for shrinkage uncertainty and is not a gold standard.
    """
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1")
    data = validate_data(X)
    fitted = fit_network(data)
    i, j = edge
    if i == j or not (0 <= i < data.shape[1] and 0 <= j < data.shape[1]):
        raise ValueError("edge must contain distinct valid column indices")
    estimate = float(fitted.partial_correlation[i, j])
    degrees_of_freedom = max(data.shape[0] - data.shape[1], 1)
    standard_error = (1.0 - estimate**2) / np.sqrt(degrees_of_freedom)
    z = estimate / standard_error if standard_error > 0.0 else float(np.sign(estimate) * np.inf)
    critical = NormalDist().inv_cdf(0.5 + confidence / 2.0)
    interval = (estimate - critical * standard_error, estimate + critical * standard_error)
    return WaldResult(
        estimate=estimate,
        standard_error=float(standard_error),
        z=float(z),
        confidence_interval=(float(interval[0]), float(interval[1])),
        method="wald_like",
        assumption="ordinary_partial_correlation",
    )
