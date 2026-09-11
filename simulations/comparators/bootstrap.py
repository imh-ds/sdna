"""Nonparametric shrinkage-bootstrap comparator."""

from dataclasses import dataclass

import numpy as np

from sdna.estimation import fit_network
from sdna.validation import validate_data


@dataclass(frozen=True)
class BootstrapResult:
    """Percentile interval and draws from a shrinkage bootstrap."""

    estimate: float
    samples: np.ndarray
    confidence_interval: tuple[float, float]
    standard_error: float
    method: str
    shrinkage_mode: str
    rejected_resamples: int = 0


def shrinkage_bootstrap(
    X: np.ndarray,
    edge: tuple[int, int],
    *,
    n_boot: int = 1000,
    rng: np.random.Generator | None = None,
    shrinkage: float | None = None,
    reestimate_shrinkage: bool = False,
    confidence: float = 0.95,
) -> BootstrapResult:
    """Bootstrap rows using the same shrinkage partial-correlation estimator.

    By default the observed full-sample lambda is held fixed. This is a
    shrinkage-bootstrap comparator, not a bootnet implementation.
    """
    if n_boot < 1:
        raise ValueError("n_boot must be positive")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1")
    data = validate_data(X)
    n, p = data.shape
    i, j = edge
    if i == j or not (0 <= i < p and 0 <= j < p):
        raise ValueError("edge must contain distinct valid column indices")
    fitted = fit_network(data, shrinkage=shrinkage)
    fixed_lambda = fitted.shrinkage
    random = np.random.default_rng() if rng is None else rng
    samples = np.empty(n_boot, dtype=float)
    accepted = 0
    rejected = 0
    attempts = 0
    max_attempts = max(100, 100 * n_boot)
    while accepted < n_boot:
        attempts += 1
        if attempts > max_attempts:
            raise RuntimeError(
                "unable to obtain enough nondegenerate bootstrap resamples; "
                "check that each variable has sufficient variation"
            )
        selected = random.integers(0, n, size=n)
        if np.any(np.std(data[selected], axis=0, ddof=1) == 0.0):
            rejected += 1
            continue
        bootstrap_fit = fit_network(
            data[selected], shrinkage=None if reestimate_shrinkage else fixed_lambda
        )
        samples[accepted] = bootstrap_fit.partial_correlation[i, j]
        accepted += 1
    alpha = (1.0 - confidence) * 100.0
    interval = (
        float(np.percentile(samples, alpha / 2.0)),
        float(np.percentile(samples, 100.0 - alpha / 2.0)),
    )
    standard_error = float(np.std(samples, ddof=1)) if n_boot > 1 else 0.0
    return BootstrapResult(
        estimate=float(fitted.partial_correlation[i, j]),
        samples=samples,
        confidence_interval=interval,
        standard_error=standard_error,
        method="shrinkage_bootstrap",
        shrinkage_mode="reestimated_lambda" if reestimate_shrinkage else "fixed_lambda",
        rejected_resamples=rejected,
    )
