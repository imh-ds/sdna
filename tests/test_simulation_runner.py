import json

import numpy as np

from simulations.run_simulation import replication_seeds, run_simulation


def test_replication_seeds_are_deterministic_and_independent() -> None:
    first = replication_seeds(20260910, 4)
    second = replication_seeds(20260910, 4)

    assert first == second
    assert len(set(first)) == 4


def test_smoke_runner_writes_rows_and_metadata(tmp_path) -> None:
    config = {
        "seed": 7,
        "replications": 2,
        "n_values": [12],
        "p_values": [3],
        "population_partial_r": [0.0],
        "contamination_cases": [0],
        "fragility_targets": [0.5],
        "certification_combination_budget": 100,
    }
    config_path = tmp_path / "config.json"
    output_path = tmp_path / "results.csv"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    run_simulation(config_path, output_path, smoke=True)

    rows = output_path.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 3
    assert "replication" in rows[0]
    assert "true_rho" in rows[0]
    metadata = json.loads((tmp_path / "results.metadata.json").read_text(encoding="utf-8"))
    assert metadata["config_checksum"]
    assert metadata["numpy_version"]
