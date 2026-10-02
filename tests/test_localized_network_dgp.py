from __future__ import annotations

import numpy as np
import pytest

from simulations.dgp import SimulatedDataset
from simulations.localized_network_dgp import (
    LocalizedNetworkPopulation,
    build_localized_population,
    generate_localized_dataset,
)


P_VALUES = (20, 40, 60)
FOCAL_EDGES = {
    "within_community": (1, 2),
    "hub_adjacent": (0, 2),
    "bridge": (4, 5),
}


def _expected_edges(p: int) -> set[tuple[int, int]]:
    edges: set[tuple[int, int]] = set()
    for module_start in range(0, p, 5):
        edges.update(
            tuple(sorted((module_start + i, module_start + (i + 1) % 5)))
            for i in range(5)
        )
        edges.update((module_start, node) for node in range(module_start + 1, module_start + 5))
    for module_start in range(0, p - 5, 5):
        edges.add((module_start + 4, module_start + 5))
    return edges


@pytest.mark.parametrize(("p", "module_count"), [(20, 4), (40, 8), (60, 12)])
def test_population_has_fixed_five_node_modules_and_exact_sparse_edges(
    p: int, module_count: int
) -> None:
    population = build_localized_population(p)
    actual_edges = {
        (i, j)
        for i in range(p)
        for j in range(i + 1, p)
        if population.precision[i, j] != 0.0
    }

    assert population.module_count == module_count
    assert [tuple(range(start, start + 5)) for start in range(0, p, 5)] == [
        tuple(range(module * 5, module * 5 + 5)) for module in range(module_count)
    ]
    assert actual_edges == _expected_edges(p)
    assert max(np.count_nonzero(population.precision[i]) - 1 for i in range(p)) <= 5
    assert np.allclose(population.precision, population.precision.T, atol=0.0)
    np.testing.assert_array_equal(np.diag(population.precision), np.ones(p))
    assert np.min(np.linalg.eigvalsh(population.precision)) > 0.0
    np.testing.assert_allclose(
        population.precision @ population.covariance, np.eye(p), atol=1e-12
    )
    for edge in population.focal_edges.values():
        assert population.partial_correlation[edge] == pytest.approx(0.05, abs=1e-12)


@pytest.mark.parametrize("p", P_VALUES)
def test_population_exposes_exact_focal_edge_indices(p: int) -> None:
    population = build_localized_population(p)

    assert population.focal_edges == FOCAL_EDGES


@pytest.mark.parametrize("p", [10, 25, 30, 80])
def test_population_rejects_unsupported_dimensions(p: int) -> None:
    with pytest.raises(ValueError, match="p must be one of"):
        build_localized_population(p)


@pytest.mark.parametrize("focal_context", ["within_community", "hub_adjacent", "bridge"])
def test_matched_contexts_share_clean_data_and_planted_case_indices(
    focal_context: str,
) -> None:
    reference = generate_localized_dataset(50, 20, focal_context, "clean", seed=183)
    for context in FOCAL_EDGES:
        matched_clean = generate_localized_dataset(50, 20, context, "clean", seed=183)
        matched_coalition = generate_localized_dataset(50, 20, context, "coalition", seed=183)
        np.testing.assert_array_equal(matched_clean.X, reference.X)
        assert matched_coalition.contaminated_cases == generate_localized_dataset(
            50, 20, focal_context, "coalition", seed=183
        ).contaminated_cases


@pytest.mark.parametrize(
    ("condition", "expected_count"), [("single_case", 1), ("coalition", 3)]
)
@pytest.mark.parametrize("focal_context", list(FOCAL_EDGES))
def test_condition_shifts_only_its_focal_columns_by_four(
    condition: str, expected_count: int, focal_context: str
) -> None:
    clean = generate_localized_dataset(50, 20, focal_context, "clean", seed=283)
    contaminated = generate_localized_dataset(50, 20, focal_context, condition, seed=283)
    changed = contaminated.X - clean.X
    focal_columns = set(contaminated.focal_edge)

    assert len(contaminated.contaminated_cases) == expected_count
    assert len(set(contaminated.contaminated_cases)) == expected_count
    assert all(0 <= case < 50 for case in contaminated.contaminated_cases)
    for case in contaminated.contaminated_cases:
        for column in range(20):
            expected = 4.0 if column in focal_columns else 0.0
            assert changed[case, column] == pytest.approx(expected, abs=1e-14)
    unchanged_rows = set(range(50)) - set(contaminated.contaminated_cases)
    np.testing.assert_array_equal(changed[list(unchanged_rows)], 0.0)


def test_generator_returns_existing_dataset_type_and_correct_shapes() -> None:
    dataset = generate_localized_dataset(50, 20, "bridge", "clean", seed=9)

    assert isinstance(dataset, SimulatedDataset)
    assert dataset.X.shape == (50, 20)
    assert dataset.covariance.shape == (20, 20)
    assert dataset.precision.shape == (20, 20)
    assert dataset.partial_correlation.shape == (20, 20)
    assert dataset.focal_edge == (4, 5)
    assert dataset.contaminated_cases == ()


@pytest.mark.parametrize("focal_context", ["invalid", "within-community", ""])
def test_generator_rejects_unsupported_focal_context(focal_context: str) -> None:
    with pytest.raises(ValueError, match="focal_context"):
        generate_localized_dataset(50, 20, focal_context, "clean", seed=1)


@pytest.mark.parametrize("condition", ["invalid", "single", "cleaned"])
def test_generator_rejects_unsupported_condition(condition: str) -> None:
    with pytest.raises(ValueError, match="condition"):
        generate_localized_dataset(50, 20, "bridge", condition, seed=1)


@pytest.mark.parametrize("n", [-1, 0, 1, 2, 2.5])
def test_generator_rejects_invalid_sample_size(n: int | float) -> None:
    with pytest.raises(ValueError, match="n must be an integer of at least 3"):
        generate_localized_dataset(n, 20, "bridge", "clean", seed=1)


def test_population_value_is_frozen() -> None:
    population = build_localized_population(20)

    assert isinstance(population, LocalizedNetworkPopulation)
    with pytest.raises((AttributeError, TypeError)):
        population.module_count = 99  # type: ignore[misc]
