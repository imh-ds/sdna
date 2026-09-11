import numpy as np
import pytest

from sdna.fragility import FragilityTarget, criterion_met, fragility_profile


def test_fragility_profile_returns_one_result_per_fraction(gaussian_data: np.ndarray) -> None:
    fractions = (0.9, 0.7, 0.5)
    profile = fragility_profile(gaussian_data, edge=(0, 1), fractions=fractions, search_cap=1)

    assert tuple(profile) == fractions
    assert tuple(result.target.value for result in profile.values()) == fractions
    assert all(result.target.kind == "relative" for result in profile.values())


def test_profile_entries_have_independent_trajectories(gaussian_data: np.ndarray) -> None:
    profile = fragility_profile(gaussian_data, edge=(0, 1), fractions=(0.8, 0.4), search_cap=1)

    assert profile[0.8] is not profile[0.4]
    profile[0.8].trajectory[0] = -999.0
    assert profile[0.4].trajectory[0] != -999.0


def test_fragility_criterion_supports_monotone_relative_targets() -> None:
    rho_full = 0.8
    rho_after = 0.3
    assert criterion_met(rho_after, rho_full, FragilityTarget("relative", 0.5))
    assert not criterion_met(rho_after, rho_full, FragilityTarget("relative", 0.3))


def test_profile_rejects_empty_or_invalid_fractions(gaussian_data: np.ndarray) -> None:
    with pytest.raises(ValueError, match="at least one"):
        fragility_profile(gaussian_data, edge=(0, 1), fractions=())
    with pytest.raises(ValueError, match="between 0 and 1"):
        fragility_profile(gaussian_data, edge=(0, 1), fractions=(1.0,))
