import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import simulations.run_simulation as simulation_runner
from simulations.run_simulation import replication_seeds, run_simulation
from tools.validate_smoke import validate_smoke


def test_runner_dispatches_all_falsification_scenarios() -> None:
    config = {
        "seed": 123,
        "replications": 1,
        "n_values": [8],
        "p_values": [3],
        "population_partial_r": [0.2],
        "scenarios": [
            "clean_planted_edge",
            "single_influential_case",
            "coalition_contamination",
            "mixture_subgroup",
            "heavy_tails",
            "collinearity_stress",
        ],
        "contamination_cases": [1],
        "fragility_targets": [0.5],
        "certification_combination_budget": 20,
        "calibration_simulations": 1,
        "bootstrap_samples": 2,
    }

    rows = simulation_runner._run(config, smoke=False)

    assert {row["scenario"] for row in rows} == set(config["scenarios"])


def test_smoke_workload_uses_benchmark_derived_limits() -> None:
    config = {
        "replications": 20,
        "calibration_simulations": 100,
        "bootstrap_samples": 200,
    }

    assert simulation_runner.workload_settings(config, smoke=True) == (5, 10, 25)
    assert simulation_runner.workload_settings(config, smoke=False) == (20, 100, 200)


def test_falsification_pilot_declares_bounded_certification_limits() -> None:
    config = json.loads(
        Path("simulations/configs/falsification_pilot.json").read_text(encoding="utf-8")
    )

    assert config["search_cap"] == 2
    assert config["certification_combination_budget"] == 1000


def test_legacy_runner_rejects_ambiguous_multi_contamination_contrast_config() -> None:
    config = {
        "seed": 123,
        "replications": 1,
        "n_values": [8],
        "p_values": [3],
        "population_partial_r": [0.2],
        "contamination_cases": [0, 1, 3],
        "fragility_targets": [0.5],
        "certification_combination_budget": 20,
        "calibration_simulations": 1,
        "bootstrap_samples": 2,
    }

    with pytest.raises(ValueError, match="explicit scenarios"):
        simulation_runner._run(config, smoke=False)


def test_runner_records_full_influence_and_reach_measurements() -> None:
    config = {
        "seed": 123,
        "replications": 1,
        "n_values": [8],
        "p_values": [3],
        "population_partial_r": [0.2],
        "scenarios": ["single_influential_case"],
        "contamination_cases": [1],
        "fragility_targets": [0.5],
        "certification_combination_budget": 20,
        "calibration_simulations": 1,
        "bootstrap_samples": 2,
    }

    row = simulation_runner._run(config, smoke=True)[0]

    assert row["contamination_status"] == 1
    assert row["influence_top_k_precision"] is not None
    assert row["first_planted_reciprocal_rank"] is not None
    assert row["reference_reached_fraction"] is not None
    assert row["bootstrap_rejected_resamples"] >= 0


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
        "calibration_simulations": 1,
        "bootstrap_samples": 2,
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
    with output_path.open(newline="", encoding="utf-8") as handle:
        result_rows = list(csv.DictReader(handle))
    assert all(float(row["elapsed_seconds"]) >= 0.0 for row in result_rows)
    timing = metadata["timing"]
    assert timing["scenario_rows"] == {"clean_planted_edge": 2}
    assert timing["scenario_elapsed_seconds"]["clean_planted_edge"] >= 0.0
    assert timing["elapsed_seconds"] >= timing["scenario_elapsed_seconds"]["clean_planted_edge"]


def test_runner_populates_calibration_and_comparator_outputs(tmp_path, monkeypatch) -> None:
    config = {
        "seed": 7,
        "replications": 1,
        "n_values": [12],
        "p_values": [3],
        "population_partial_r": [0.0],
        "contamination_cases": [0],
        "fragility_targets": [0.5],
        "certification_combination_budget": 100,
        "calibration_simulations": 1,
        "bootstrap_samples": 2,
    }
    monkeypatch.setattr(
        simulation_runner,
        "calibrate_fragility",
        lambda *args, **kwargs: SimpleNamespace(
            reference_tail_probability=0.25,
            reference_reached=(True,),
        ),
    )
    monkeypatch.setattr(
        simulation_runner,
        "wald_partial_correlation",
        lambda *args, **kwargs: SimpleNamespace(z=2.0),
    )
    monkeypatch.setattr(
        simulation_runner,
        "shrinkage_bootstrap",
        lambda *args, **kwargs: SimpleNamespace(
            confidence_interval=(0.1, 0.2),
            rejected_resamples=0,
        ),
    )

    config_path = tmp_path / "config.json"
    output_path = tmp_path / "results.csv"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    run_simulation(config_path, output_path, smoke=False)

    row = output_path.read_text(encoding="utf-8").splitlines()[1].split(",")
    header = output_path.read_text(encoding="utf-8").splitlines()[0].split(",")
    values = dict(zip(header, row))
    assert values["reference_tail_probability"] == "0.25"
    assert values["wald_z"] == "2.0"
    assert values["bootstrap_ci_excludes_zero"] == "True"


def test_smoke_validator_requires_falsification_fields(tmp_path) -> None:
    config = {
        "seed": 7,
        "replications": 1,
        "n_values": [12],
        "p_values": [3],
        "population_partial_r": [0.0],
        "contamination_cases": [0],
        "fragility_targets": [0.5],
    }
    config_path = tmp_path / "config.json"
    results_path = tmp_path / "results.csv"
    metadata_path = tmp_path / "results.metadata.json"
    summary_path = tmp_path / "summary.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    fields = [field for field in simulation_runner.FIELDNAMES if field != "reference_reached_fraction"]
    results_path.write_text(",".join(fields) + "\n", encoding="utf-8")
    metadata_path.write_text("{}", encoding="utf-8")
    summary_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="reference_reached_fraction"):
        validate_smoke(results_path, metadata_path, summary_path, config_path)
