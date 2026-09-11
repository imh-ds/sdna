from dataclasses import replace

import numpy as np
import pytest

from sdna.calibration import _reference_tail_probability, calibrate_fragility
from sdna.exceptions import CalibrationError
from sdna.fragility import FragilityTarget


def test_calibration_is_reproducible_and_records_reference_edges(
    gaussian_data: np.ndarray,
) -> None:
    target = FragilityTarget("relative", 0.9)
    first = calibrate_fragility(
        gaussian_data,
        edge=(0, 1),
        target=target,
        n_sim=3,
        rng=np.random.default_rng(7),
        search_cap=3,
        require_reached=False,
    )
    second = calibrate_fragility(
        gaussian_data,
        edge=(0, 1),
        target=target,
        n_sim=3,
        rng=np.random.default_rng(7),
        search_cap=3,
        require_reached=False,
    )

    assert len(first.reference_counts) == 3
    assert first.reference_edge_estimates.shape == (3,)
    np.testing.assert_array_equal(first.reference_counts, second.reference_counts)
    np.testing.assert_allclose(first.reference_edge_estimates, second.reference_edge_estimates)


def test_calibration_rejects_non_psd_generator(gaussian_data: np.ndarray, monkeypatch) -> None:
    from sdna.estimation import fit_network

    fitted = fit_network(gaussian_data)
    bad = fitted.correlation.copy()
    bad[0, 1] = bad[1, 0] = 1.5
    monkeypatch.setattr(
        "sdna.calibration.fit_network", lambda *args, **kwargs: replace(fitted, correlation=bad)
    )

    with pytest.raises(CalibrationError, match="positive semidefinite"):
        calibrate_fragility(gaussian_data, edge=(0, 1), target=FragilityTarget("relative", 0.5))


def test_reference_tail_probability_uses_plus_one_correction() -> None:
    assert _reference_tail_probability(2, [1, 2, 4]) == pytest.approx(0.75)
    assert _reference_tail_probability(None, [1, 2]) is None
    assert _reference_tail_probability(2, [1, None]) is None
