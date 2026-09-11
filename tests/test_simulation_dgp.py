import numpy as np
import pytest

from simulations.dgp import (
    clean_planted_edge,
    collinearity_stress,
    coalition_contamination,
    construct_precision,
    heavy_tails,
    mixture_subgroup,
    single_influential_case,
)


def test_precision_constructor_guarantees_positive_definiteness() -> None:
    precision = construct_precision(4, {(0, 1): 0.4, (1, 2): -0.3})

    assert np.min(np.linalg.eigvalsh(precision)) > 0.0


def test_clean_generator_has_positive_definite_population_precision() -> None:
    simulated = clean_planted_edge(
        80, 5, np.random.default_rng(1), focal_edge=(0, 1), partial=0.4
    )

    assert np.min(np.linalg.eigvalsh(simulated.precision)) > 0.0
    assert simulated.partial_correlation[0, 1] == pytest.approx(0.4)
    assert simulated.contaminated_cases == ()


def test_single_contamination_labels_are_reproducible() -> None:
    first = single_influential_case(50, 4, np.random.default_rng(2), focal_edge=(0, 1))
    second = single_influential_case(50, 4, np.random.default_rng(2), focal_edge=(0, 1))

    assert first.contaminated_cases == second.contaminated_cases
    np.testing.assert_array_equal(first.X, second.X)
    assert len(first.contaminated_cases) == 1


def test_coalition_and_subgroup_return_exact_case_indices() -> None:
    coalition = coalition_contamination(60, 5, np.random.default_rng(3), n_contaminated=4)
    subgroup = mixture_subgroup(60, 5, np.random.default_rng(4), subgroup_fraction=0.2)

    assert len(coalition.contaminated_cases) == 4
    assert len(subgroup.contaminated_cases) == 12
    assert len(set(subgroup.contaminated_cases)) == 12


def test_mixture_truth_metadata_describes_the_overall_mixture() -> None:
    simulated = mixture_subgroup(
        100,
        5,
        np.random.default_rng(8),
        subgroup_fraction=0.2,
        subgroup_partial=0.6,
    )

    assert simulated.covariance[0, 1] == pytest.approx(0.12)
    assert simulated.partial_correlation[0, 1] == pytest.approx(0.12)
    np.testing.assert_allclose(
        simulated.precision @ simulated.covariance, np.eye(5), atol=1e-8
    )


def test_all_dgps_return_truth_matrices() -> None:
    datasets = [
        heavy_tails(40, 4, np.random.default_rng(5)),
        collinearity_stress(40, 4, np.random.default_rng(6)),
    ]

    for simulated in datasets:
        assert simulated.X.shape == (40, 4)
        assert simulated.covariance.shape == (4, 4)
        assert simulated.precision.shape == (4, 4)
        assert simulated.partial_correlation.shape == (4, 4)
        np.testing.assert_allclose(
            simulated.precision @ simulated.covariance, np.eye(4), atol=1e-8
        )
