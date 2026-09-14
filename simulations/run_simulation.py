"""Configuration-driven, reproducible SDNA simulation runner."""

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from sdna import __version__
from sdna.calibration import calibrate_fragility
from sdna.fragility import FragilityTarget
from simulations.comparators.bootstrap import shrinkage_bootstrap
from simulations.comparators.wald import wald_partial_correlation
from simulations.dgp import (
    SimulatedDataset,
    clean_planted_edge,
    coalition_contamination,
    collinearity_stress,
    heavy_tails,
    mixture_subgroup,
    single_influential_case,
)
from simulations.full_workflow import derive_workflow_seeds, run_full_workflow

SCENARIO_NAMES = (
    "clean_planted_edge",
    "single_influential_case",
    "coalition_contamination",
    "mixture_subgroup",
    "heavy_tails",
    "collinearity_stress",
)

FIELDNAMES = [
    "scenario", "parameter_id", "replication", "seed", "N", "p", "fragility_target", "true_rho",
    "observed_rho", "lambda",
    "contamination_count", "contamination_status", "greedy_fragility_50", "exact_fragility_50",
    "certified", "reached", "reference_tail_probability", "reference_reached_fraction",
    "wald_z", "bootstrap_ci_excludes_zero", "bootstrap_rejected_resamples",
    "influence_top_k_precision", "influence_top_k_recall", "first_planted_reciprocal_rank",
    "planted_absolute_influence_share",
    "elapsed_seconds",
]


def replication_seeds(seed: int, count: int) -> list[int]:
    """Derive independent deterministic integer seeds for replications."""
    if count < 1:
        raise ValueError("count must be positive")
    return [int(child.generate_state(1)[0]) for child in np.random.SeedSequence(seed).spawn(count)]


def _checksum(config: dict[str, Any]) -> str:
    encoded = json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def workload_settings(
    config: dict[str, Any],
    smoke: bool,
    calibration_override: int | None = None,
    bootstrap_override: int | None = None,
) -> tuple[int, int, int]:
    """Return replications, calibration simulations, and bootstrap draws."""
    replications = int(config["replications"])
    calibration_simulations = int(
        config.get("calibration_simulations", 100)
        if calibration_override is None
        else calibration_override
    )
    bootstrap_samples = int(
        config.get("bootstrap_samples", 1000) if bootstrap_override is None else bootstrap_override
    )
    if replications < 1:
        raise ValueError("replications must be positive")
    if calibration_simulations < 1:
        raise ValueError("calibration_simulations must be positive")
    if bootstrap_samples < 1:
        raise ValueError("bootstrap_samples must be positive")
    if smoke:
        return min(replications, 5), min(calibration_simulations, 10), min(bootstrap_samples, 25)
    return replications, calibration_simulations, bootstrap_samples


def generate_scenario(
    name: str,
    n: int,
    p: int,
    rng: np.random.Generator,
    config: dict[str, Any],
) -> SimulatedDataset:
    """Generate one configured scenario from the truth-aware DGP registry."""
    if name not in SCENARIO_NAMES:
        raise ValueError(f"unknown simulation scenario: {name}")
    edge = tuple(config.get("focal_edge", (0, 1)))
    if name == "clean_planted_edge":
        return clean_planted_edge(
            n, p, rng, focal_edge=edge, partial=float(config.get("population_partial", 0.4))
        )
    if name == "single_influential_case":
        return single_influential_case(n, p, rng, focal_edge=edge)
    if name == "coalition_contamination":
        return coalition_contamination(
            n,
            p,
            rng,
            n_contaminated=int(config.get("contamination_count", 3)),
            focal_edge=edge,
        )
    if name == "mixture_subgroup":
        return mixture_subgroup(n, p, rng, focal_edge=edge)
    if name == "heavy_tails":
        return heavy_tails(n, p, rng, focal_edge=edge)
    return collinearity_stress(n, p, rng, focal_edge=edge)


def _jobs(
    config: dict[str, Any], replications: int
) -> list[tuple[int, int, str, float | int | None, int, int]]:
    """Build deterministic simulation jobs, preserving legacy config behavior."""
    jobs: list[tuple[int, int, str, float | int | None, int, int]] = []
    configured_scenarios = config.get("scenarios")
    for n in config["n_values"]:
        for p in config["p_values"]:
            if configured_scenarios is None:
                contamination_values = [int(value) for value in config["contamination_cases"]]
                positive_contamination = [value for value in contamination_values if value > 0]
                if 0 in contamination_values and len(positive_contamination) > 1:
                    raise ValueError(
                        "legacy configurations with multiple positive contamination cases "
                        "and clean rows require explicit scenarios for unambiguous contrasts"
                    )
                for parameter_id, rho in enumerate(config["population_partial_r"]):
                    for contamination_count in contamination_values:
                        scenario = (
                            "coalition_contamination"
                            if contamination_count
                            else "clean_planted_edge"
                        )
                        parameter = (
                            int(contamination_count) if contamination_count else float(rho)
                        )
                        for replication in range(replications):
                            jobs.append(
                                (int(n), int(p), scenario, parameter, parameter_id, replication)
                            )
                continue
            for scenario in configured_scenarios:
                if scenario not in SCENARIO_NAMES:
                    raise ValueError(f"unknown simulation scenario: {scenario}")
                parameters: list[int | None]
                if scenario == "clean_planted_edge":
                    parameters = [float(value) for value in config["population_partial_r"]]
                elif scenario == "coalition_contamination":
                    parameters = [
                        int(value) for value in config["contamination_cases"] if int(value) > 0
                    ]
                    if not parameters:
                        raise ValueError("coalition_contamination requires a positive count")
                else:
                    parameters = [None]
                for parameter_id, parameter in enumerate(parameters):
                    for replication in range(replications):
                        jobs.append(
                            (int(n), int(p), scenario, parameter, parameter_id, replication)
                        )
    return jobs


def _run(
    config: dict[str, Any],
    smoke: bool,
    calibration_override: int | None = None,
    bootstrap_override: int | None = None,
) -> list[dict[str, Any]]:
    replications, calibration_simulations, bootstrap_samples = workload_settings(
        config, smoke, calibration_override, bootstrap_override
    )
    bootstrap_confidence = float(config.get("bootstrap_confidence", 0.95))
    if not 0.0 < bootstrap_confidence < 1.0:
        raise ValueError("bootstrap_confidence must be between 0 and 1")
    jobs = _jobs(config, replications)
    seeds = replication_seeds(int(config["seed"]), len(jobs))
    rows: list[dict[str, Any]] = []
    target_values = tuple(float(value) for value in config["fragility_targets"])
    if 0.5 not in target_values:
        raise ValueError("fragility_targets must include 0.5 for the *_50 output fields")
    target_value = 0.5
    target = FragilityTarget("relative", target_value)
    for seed_index, (n, p, scenario, parameter, parameter_id, replication) in enumerate(jobs):
        row_started = perf_counter()
        row_seed = seeds[seed_index]
        rng = np.random.default_rng(row_seed)
        scenario_config = dict(config)
        if scenario == "clean_planted_edge":
            scenario_config["population_partial"] = parameter
        if scenario == "coalition_contamination":
            scenario_config["contamination_count"] = parameter
        simulated = generate_scenario(scenario, n, p, rng, scenario_config)
        workflow = run_full_workflow(
            simulated,
            target=target,
            search_cap=config.get("search_cap"),
            calibration_simulations=calibration_simulations,
            bootstrap_samples=bootstrap_samples,
            bootstrap_confidence=bootstrap_confidence,
            certification_combination_budget=int(config["certification_combination_budget"]),
            seeds=derive_workflow_seeds(row_seed),
            calibration_require_reached=False,
            calibration_fn=calibrate_fragility,
            wald_fn=wald_partial_correlation,
            bootstrap_fn=shrinkage_bootstrap,
        )
        row = {
            "scenario": scenario,
            "parameter_id": parameter_id,
            "replication": replication,
            "seed": row_seed,
            "N": n,
            "p": p,
            "fragility_target": target_value,
            "true_rho": workflow["true_rho"],
            "observed_rho": workflow["observed_rho"],
            "lambda": workflow["lambda"],
            "contamination_count": workflow["contamination_count"],
            "contamination_status": workflow["contamination_status"],
            "greedy_fragility_50": workflow["greedy_fragility_50"],
            "exact_fragility_50": workflow["exact_fragility_50"],
            "certified": bool(workflow["certified"]),
            "reached": workflow["reached"],
            "reference_tail_probability": workflow["reference_tail_probability"],
            "reference_reached_fraction": workflow["reference_reached_fraction"],
            "wald_z": workflow["wald_z"],
            "bootstrap_ci_excludes_zero": workflow["bootstrap_ci_excludes_zero"],
            "bootstrap_rejected_resamples": workflow["bootstrap_rejected_resamples"],
            "influence_top_k_precision": workflow["influence_top_k_precision"],
            "influence_top_k_recall": workflow["influence_top_k_recall"],
            "first_planted_reciprocal_rank": workflow["first_planted_reciprocal_rank"],
            "planted_absolute_influence_share": workflow["planted_absolute_influence_share"],
            "elapsed_seconds": perf_counter() - row_started,
        }
        rows.append(row)
    return rows


def run_simulation(
    config_path: str | Path,
    output_path: str | Path,
    smoke: bool = False,
    calibration_override: int | None = None,
    bootstrap_override: int | None = None,
) -> None:
    """Run a JSON configuration and write CSV rows plus adjacent metadata."""
    config_file = Path(config_path)
    output_file = Path(output_path)
    config = json.loads(config_file.read_text(encoding="utf-8"))
    started = datetime.now(UTC)
    run_started = perf_counter()
    rows = _run(
        config,
        smoke=smoke,
        calibration_override=calibration_override,
        bootstrap_override=bootstrap_override,
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    scenario_elapsed_seconds: dict[str, float] = {}
    scenario_rows: dict[str, int] = {}
    for row in rows:
        scenario = str(row["scenario"])
        scenario_elapsed_seconds[scenario] = scenario_elapsed_seconds.get(scenario, 0.0) + float(
            row["elapsed_seconds"]
        )
        scenario_rows[scenario] = scenario_rows.get(scenario, 0) + 1
    metadata = {
        "git_commit": _git_commit(),
        "python_version": sys.version,
        "numpy_version": np.__version__,
        "config_checksum": _checksum(config),
        "package_version": __version__,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "smoke": smoke,
        "rows": len(rows),
        "timing": {
            "elapsed_seconds": perf_counter() - run_started,
            "scenario_elapsed_seconds": scenario_elapsed_seconds,
            "scenario_rows": scenario_rows,
        },
    }
    metadata_path = output_file.with_suffix(".metadata.json")
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--calibration-simulations", type=int)
    parser.add_argument("--bootstrap-samples", type=int)
    args = parser.parse_args()
    run_simulation(
        args.config,
        args.output,
        smoke=args.smoke,
        calibration_override=args.calibration_simulations,
        bootstrap_override=args.bootstrap_samples,
    )


if __name__ == "__main__":
    main()
