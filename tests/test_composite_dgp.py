import numpy as np
import pytest

from simulations.composite_dgp import (
    CONDITIONS,
    composite_truth,
    generate_composite_dataset,
)

DRAWS = 40_000


def test_ordinal_composites_are_bounded_multiples_of_one_fifth() -> None:
    data = generate_composite_dataset(60, "moderate_ceiling", 0, 1, DRAWS)

    assert data.X.min() >= 1.0 and data.X.max() <= 5.0
    np.testing.assert_allclose(data.X * 5, np.round(data.X * 5), atol=1e-9)
    assert data.contaminated_cases == ()


def test_ceiling_conditions_increase_top_category_pileup() -> None:
    shares = {}
    for condition in ("symmetric", "moderate_ceiling", "severe_ceiling"):
        X = generate_composite_dataset(2000, condition, 0, 2, DRAWS).X
        shares[condition] = float(np.mean(X > 4.0))

    assert shares["symmetric"] < shares["moderate_ceiling"] < shares["severe_ceiling"]


def test_conditions_are_matched_and_share_careless_cases() -> None:
    cases = {
        c: generate_composite_dataset(50, c, 3, 7, DRAWS).contaminated_cases
        for c in CONDITIONS
    }
    control = generate_composite_dataset(50, "continuous_control", 0, 7, DRAWS).X
    ordinal = generate_composite_dataset(50, "symmetric", 0, 7, DRAWS).X

    assert len(set(cases.values())) == 1 and len(next(iter(cases.values()))) == 3
    assert np.corrcoef(control[:, 0], ordinal[:, 0])[0, 1] > 0.9


def test_straight_liners_replace_exactly_the_planted_rows() -> None:
    clean = generate_composite_dataset(50, "severe_ceiling", 0, 3, DRAWS).X
    dirty = generate_composite_dataset(50, "severe_ceiling", 3, 3, DRAWS)
    rows = list(dirty.contaminated_cases)

    assert np.all(dirty.X[rows] == 5.0)
    other = np.setdiff1d(np.arange(50), rows)
    np.testing.assert_array_equal(dirty.X[other], clean[other])


def test_truth_is_valid_and_focal_edge_is_positive() -> None:
    covariance, precision, partial = composite_truth("moderate_ceiling", DRAWS)

    assert np.min(np.linalg.eigvalsh(covariance)) > 0.0
    np.testing.assert_allclose(precision @ covariance, np.eye(6), atol=1e-8)
    assert partial[0, 1] > 0.05 > abs(partial[0, 3])


def test_generation_is_deterministic_and_validates_inputs() -> None:
    first = generate_composite_dataset(50, "symmetric", 3, 9, DRAWS)
    second = generate_composite_dataset(50, "symmetric", 3, 9, DRAWS)
    np.testing.assert_array_equal(first.X, second.X)
    with pytest.raises(ValueError, match="careless"):
        generate_composite_dataset(50, "symmetric", 1, 9, DRAWS)
    with pytest.raises(ValueError, match="unknown"):
        generate_composite_dataset(50, "bogus", 0, 9, DRAWS)
