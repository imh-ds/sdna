import numpy as np
import pytest

from simulations.composite_dgp_v2 import (
    CONDITIONS,
    CONTAMINATIONS,
    composite_truth,
    edge_threshold,
    generate_composite_dataset,
)

DRAWS = 40_000


def _make(contamination: str, condition: str = "moderate_ceiling", seed: int = 4):
    return generate_composite_dataset(60, 6, "strong", condition, contamination, seed, DRAWS)


def test_contaminated_cases_are_shared_across_conditions_and_types() -> None:
    cases = {
        (c, k): _make(k, c).contaminated_cases
        for c in CONDITIONS
        for k in CONTAMINATIONS
        if k != "none"
    }

    assert len(set(cases.values())) == 1
    assert _make("none").contaminated_cases == ()


def test_clean_rows_are_identical_across_contamination_types() -> None:
    clean = _make("none")
    for kind in CONTAMINATIONS[1:]:
        dirty = _make(kind)
        rows = list(dirty.contaminated_cases)
        other = np.setdiff1d(np.arange(60), rows)
        np.testing.assert_array_equal(dirty.X[other], clean.X[other])


def test_straight_top_and_discordant_values() -> None:
    top = _make("straight_top")
    rows = list(top.contaminated_cases)
    assert np.all(top.X[rows] == 5.0)

    discordant = _make("focal_discordant")
    rows = list(discordant.contaminated_cases)
    assert np.all(discordant.X[rows, 0] == 1.0)
    assert np.all(discordant.X[rows, 1] == 5.0)
    clean = _make("none")
    np.testing.assert_array_equal(discordant.X[rows, 2:], clean.X[rows, 2:])


def test_random_responders_use_the_full_category_range_and_match_across_conditions() -> None:
    first = _make("random_responder", "symmetric")
    second = _make("random_responder", "severe_ceiling")
    rows = list(first.contaminated_cases)

    np.testing.assert_array_equal(first.X[rows], second.X[rows])
    assert first.X[rows].min() >= 1.0 and first.X[rows].max() <= 5.0


def test_continuous_control_uses_latent_extremes() -> None:
    data = _make("focal_discordant", "continuous_control")
    rows = list(data.contaminated_cases)

    assert np.allclose(data.X[rows, 0], -2.0) and np.allclose(data.X[rows, 1], 2.0)


def test_truth_and_edge_rule_separate_ring_pairs_from_other_pairs() -> None:
    for strength in ("strong", "weak"):
        _, precision, partial = composite_truth(6, strength, "severe_ceiling", DRAWS)
        assert edge_threshold(partial) is not None
        np.testing.assert_allclose(precision @ composite_truth(6, strength, "severe_ceiling", DRAWS)[0], np.eye(6), atol=1e-7)


def test_edge_rule_reports_unclassifiable_truth() -> None:
    partial = np.eye(4)
    partial[0, 1] = partial[1, 0] = 0.05
    partial[0, 2] = partial[2, 0] = 0.04
    partial[1, 2] = partial[2, 1] = 0.05
    partial[2, 3] = partial[3, 2] = 0.05
    partial[0, 3] = partial[3, 0] = 0.05

    assert edge_threshold(partial) is None


def test_validation() -> None:
    with pytest.raises(ValueError, match="strength"):
        generate_composite_dataset(60, 6, "huge", "symmetric", "none", 1, DRAWS)
    with pytest.raises(ValueError, match="contamination"):
        generate_composite_dataset(60, 6, "strong", "symmetric", "weird", 1, DRAWS)
    with pytest.raises(ValueError, match="unknown composite condition"):
        generate_composite_dataset(60, 6, "strong", "bogus", "none", 1, DRAWS)
