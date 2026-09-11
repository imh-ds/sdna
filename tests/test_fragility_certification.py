import numpy as np
import pytest

from sdna.fragility import FragilityTarget, certify_fragility, greedy_fragility
from sdna.results import FragilityResult


def test_certification_can_improve_greedy_upper_bound(
    greedy_failure_data: np.ndarray,
) -> None:
    fit = fit_network(greedy_failure_data)
    greedy = greedy_fragility(
        greedy_failure_data,
        edge=(0, 1),
        target=FragilityTarget("relative", 0.5),
        shrinkage=fit.shrinkage,
        search_cap=4,
    )

    assert greedy.reached
    assert greedy.greedy_count == 4
    certified = certify_fragility(
        greedy_failure_data,
        greedy,
        shrinkage=fit.shrinkage,
        max_combinations=200_000,
    )

    assert certified.certified
    assert certified.exact_minimum == 3


def test_certification_reuses_greedy_shrinkage_by_default(
    gaussian_data: np.ndarray, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = FragilityResult(
        edge=(0, 1),
        target=FragilityTarget("relative", 0.5),
        full_value=0.5,
        reached=True,
        greedy_count=3,
        cases=(0, 1, 2),
        trajectory=np.array([0.5, 0.4, 0.3, 0.2]),
        shrinkage=0.25,
    )
    seen: list[float | None] = []
    from sdna import fragility as fragility_module

    original_fit_network = fragility_module.fit_network

    def recording_fit(data: np.ndarray, shrinkage: float | None = None):
        seen.append(shrinkage)
        return original_fit_network(data, shrinkage=shrinkage)

    monkeypatch.setattr(fragility_module, "fit_network", recording_fit)
    certify_fragility(gaussian_data, result, max_combinations=1)

    assert seen[0] == 0.25


def test_certification_requires_reached_greedy_result(gaussian_data: np.ndarray) -> None:
    result = greedy_fragility(
        gaussian_data,
        edge=(0, 1),
        target=FragilityTarget("absolute", 0.0),
        search_cap=1,
    )
    if result.reached:
        pytest.skip("fixture reached the threshold within one deletion")

    with pytest.raises(ValueError, match="reached"):
        certify_fragility(gaussian_data, result, max_combinations=100)


def test_certification_records_exact_minimum_for_already_minimal_result(
    gaussian_data: np.ndarray,
) -> None:
    target = FragilityTarget("relative", 0.99)
    result = greedy_fragility(gaussian_data, edge=(0, 1), target=target, search_cap=1)
    if not result.reached or result.greedy_count != 1:
        pytest.skip("fixture did not produce a one-deletion reached result")

    certified = certify_fragility(gaussian_data, result, max_combinations=100)

    assert certified.certified
    assert certified.exact_minimum == 1
    assert certified.combinations_checked == 0


def test_certification_rejects_nonpositive_budget(gaussian_data: np.ndarray) -> None:
    result = greedy_fragility(
        gaussian_data,
        edge=(0, 1),
        target=FragilityTarget("relative", 0.99),
        search_cap=1,
    )
    if not result.reached:
        pytest.skip("fixture did not reach the threshold")

    with pytest.raises(ValueError, match="positive"):
        certify_fragility(gaussian_data, result, max_combinations=0)


def test_certification_stops_before_exceeding_budget(gaussian_data: np.ndarray) -> None:
    result = FragilityResult(
        edge=(0, 1),
        target=FragilityTarget("relative", 0.5),
        full_value=0.5,
        reached=True,
        greedy_count=3,
        cases=(0, 1, 2),
        trajectory=np.array([0.5, 0.4, 0.3, 0.2]),
        shrinkage=0.25,
    )

    certified = certify_fragility(gaussian_data, result, max_combinations=1)

    assert not certified.certified
    assert certified.exact_minimum is None
    assert certified.combinations_checked == 0
