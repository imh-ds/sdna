import json

import numpy as np

from benchmarks.benchmark_fragility import benchmark_row as fragility_benchmark_row
from benchmarks.benchmark_fragility import run_benchmark_matrix as run_fragility_matrix
from benchmarks.benchmark_fragility import write_results as write_fragility_results
from benchmarks.benchmark_influence import benchmark_row as influence_benchmark_row
from benchmarks.benchmark_influence import run_benchmark_matrix
from benchmarks.benchmark_influence import write_results as write_influence_results


def test_influence_benchmark_row_reports_both_influence_timings() -> None:
    row = influence_benchmark_row(12, 4, seed=123, repeats=1)

    assert row["N"] == 12
    assert row["p"] == 4
    assert row["seed"] == 123
    assert row["repeats"] == 1
    assert row["exact_loo_seconds"] >= 0.0
    assert row["analytic_influence_seconds"] >= 0.0
    if row["approximation_slope"] is not None:
        assert np.isfinite(row["approximation_slope"])
    if row["approximation_mae"] is not None:
        assert row["approximation_mae"] >= 0.0
    if row["approximation_max_abs_error"] is not None:
        assert row["approximation_max_abs_error"] >= 0.0


def test_influence_benchmark_matrix_covers_requested_grid() -> None:
    rows = run_benchmark_matrix((8, 10), (3,), seed=123, repeats=1)

    assert [(row["N"], row["p"]) for row in rows] == [(8, 3), (10, 3)]


def test_fragility_benchmark_row_reports_search_and_calibration_timings() -> None:
    row = fragility_benchmark_row(
        12,
        4,
        seed=123,
        calibration_simulations=2,
        search_cap=2,
    )

    assert row["N"] == 12
    assert row["p"] == 4
    assert row["seed"] == 123
    assert row["calibration_simulations"] == 2
    assert row["greedy_fragility_seconds"] >= 0.0
    assert row["calibration_seconds"] >= 0.0
    assert np.isfinite(row["greedy_count"]) or row["greedy_count"] is None


def test_fragility_benchmark_matrix_covers_requested_grid() -> None:
    rows = run_fragility_matrix((8,), (3,), seed=123, calibration_simulations=1, search_cap=1)

    assert [(row["N"], row["p"]) for row in rows] == [(8, 3)]
    assert rows[0]["calibration_simulations"] == 1


def test_benchmark_results_write_json(tmp_path) -> None:
    influence_output = tmp_path / "influence.json"
    fragility_output = tmp_path / "fragility.json"
    influence_rows = [{"N": 8, "p": 3, "exact_loo_seconds": 0.1}]
    fragility_rows = [{"N": 8, "p": 3, "calibration_seconds": 0.2}]

    write_influence_results(influence_rows, influence_output)
    write_fragility_results(fragility_rows, fragility_output)

    assert json.loads(influence_output.read_text()) == {"rows": influence_rows}
    assert json.loads(fragility_output.read_text()) == {"rows": fragility_rows}
