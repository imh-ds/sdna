import numpy as np
import pytest

from sdna.fragility import FragilityTarget, criterion_met, greedy_fragility


def test_relative_target_checks_absolute_attenuation() -> None:
    target = FragilityTarget("relative", 0.5)

    assert criterion_met(0.49, 1.0, target)
    assert criterion_met(-0.49, 1.0, target)
    assert not criterion_met(0.51, 1.0, target)


def test_absolute_target_checks_absolute_threshold() -> None:
    target = FragilityTarget("absolute", 0.1)

    assert criterion_met(-0.1, 0.8, target)
    assert not criterion_met(0.11, 0.8, target)


def test_sign_reversal_does_not_require_exact_zero() -> None:
    target = FragilityTarget("sign_reversal")

    assert criterion_met(-0.01, 0.4, target)
    assert criterion_met(0.01, -0.4, target)
    assert not criterion_met(0.01, 0.4, target)


@pytest.mark.parametrize(
    "kind,value",
    [
        ("relative", 0.0),
        ("relative", 1.0),
        ("absolute", -0.1),
    ],
)
def test_target_values_are_validated(kind: str, value: float) -> None:
    with pytest.raises(ValueError, match="must be"):
        FragilityTarget(kind, value)


def test_sign_reversal_rejects_a_value() -> None:
    with pytest.raises(ValueError, match="value must be None"):
        FragilityTarget("sign_reversal", 0.5)


def test_capped_search_is_censored(gaussian_data: np.ndarray) -> None:
    result = greedy_fragility(
        gaussian_data,
        edge=(0, 1),
        target=FragilityTarget("absolute", 0.0),
        search_cap=2,
    )

    assert not result.reached
    assert result.greedy_count is None
    assert len(result.cases) == 2
    assert result.trajectory.shape == (3,)
    assert not result.certified
