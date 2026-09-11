import numpy as np
import pytest

from sdna.analysis import analyze_edges
from sdna.fragility import FragilityTarget


def test_analyze_edges_requires_explicit_edges(gaussian_data: np.ndarray) -> None:
    with pytest.raises(TypeError):
        analyze_edges(  # type: ignore[call-arg]
            gaussian_data, target=FragilityTarget("relative", 0.5)
        )


def test_analyze_edges_returns_exact_influence_and_fragility(gaussian_data: np.ndarray) -> None:
    results = analyze_edges(
        gaussian_data,
        edges=[(0, 1), (1, 2)],
        target=FragilityTarget("relative", 0.5),
        search_cap=1,
    )

    assert [result.edge for result in results] == [(0, 1), (1, 2)]
    for result in results:
        assert result.influence.method == "exact_loo"
        assert result.influence.changes.shape == (len(gaussian_data), 5, 5)
        assert result.fragility.target.kind == "relative"
        assert result.fragility.edge == result.edge
        assert result.calibration is None


def test_analyze_edges_calibration_is_reproducible(gaussian_data: np.ndarray) -> None:
    target = FragilityTarget("relative", 0.9)
    first = analyze_edges(
        gaussian_data,
        edges=[(0, 1)],
        target=target,
        calibrate=True,
        n_sim=2,
        rng=np.random.default_rng(11),
        search_cap=1,
        require_reached=False,
    )[0]
    second = analyze_edges(
        gaussian_data,
        edges=[(0, 1)],
        target=target,
        calibrate=True,
        n_sim=2,
        rng=np.random.default_rng(11),
        search_cap=1,
        require_reached=False,
    )[0]

    assert first.calibration is not None
    assert second.calibration is not None
    np.testing.assert_array_equal(
        first.calibration.reference_counts, second.calibration.reference_counts
    )
    np.testing.assert_allclose(
        first.calibration.reference_edge_estimates,
        second.calibration.reference_edge_estimates,
    )
