"""Configuration-driven, reproducible SDNA simulation runner."""

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from sdna import __version__
from sdna.calibration import calibrate_fragility
from sdna.estimation import fit_network
from sdna.fragility import FragilityTarget, certify_fragility, greedy_fragility
from sdna.influence import exact_loo_influence
from simulations.comparators.bootstrap import shrinkage_bootstrap
from simulations.comparators.wald import wald_partial_correlation
from simulations.dgp import clean_planted_edge, coalition_contamination

FIELDNAMES = [
    "scenario", "replication", "seed", "N", "p", "fragility_target", "true_rho",
    "observed_rho", "lambda",
    "contamination_count", "greedy_fragility_50", "exact_fragility_50", "certified", "reached",
    "reference_tail_probability", "wald_z", "bootstrap_ci_excludes_zero", "influence_top_k_recall",
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


def _run(config: dict[str, Any], smoke: bool) -> list[dict[str, Any]]:
    replications = min(int(config["replications"]), 10) if smoke else int(config["replications"])
    calibration_simulations = int(config.get("calibration_simulations", 100))
    bootstrap_samples = int(config.get("bootstrap_samples", 1000))
    bootstrap_confidence = float(config.get("bootstrap_confidence", 0.95))
    if calibration_simulations < 1:
        raise ValueError("calibration_simulations must be positive")
    if bootstrap_samples < 1:
        raise ValueError("bootstrap_samples must be positive")
    if not 0.0 < bootstrap_confidence < 1.0:
        raise ValueError("bootstrap_confidence must be between 0 and 1")
    if smoke:
        calibration_simulations = min(calibration_simulations, 10)
        bootstrap_samples = min(bootstrap_samples, 25)
    combinations_count = (
        len(config["n_values"])
        * len(config["p_values"])
        * len(config["population_partial_r"])
        * len(config["contamination_cases"])
    )
    seeds = replication_seeds(int(config["seed"]), replications * combinations_count)
    rows: list[dict[str, Any]] = []
    seed_index = 0
    target_values = tuple(float(value) for value in config["fragility_targets"])
    if 0.5 not in target_values:
        raise ValueError("fragility_targets must include 0.5 for the *_50 output fields")
    target_value = 0.5
    target = FragilityTarget("relative", target_value)
    for n in config["n_values"]:
        for p in config["p_values"]:
            for rho in config["population_partial_r"]:
                for contamination_count in config["contamination_cases"]:
                    for replication in range(replications):
                        row_seed = seeds[seed_index]
                        seed_index += 1
                        rng = np.random.default_rng(row_seed)
                        if contamination_count:
                            simulated = coalition_contamination(
                                int(n), int(p), rng, n_contaminated=int(contamination_count)
                            )
                            scenario = "coalition_contamination"
                        else:
                            simulated = clean_planted_edge(
                                int(n), int(p), rng, partial=float(rho)
                            )
                            scenario = "clean_planted_edge"
                        fitted = fit_network(simulated.X)
                        edge = simulated.focal_edge
                        observed_rho = float(fitted.partial_correlation[edge])
                        greedy = greedy_fragility(
                            simulated.X,
                            edge=edge,
                            target=target,
                            shrinkage=fitted.shrinkage,
                            search_cap=config.get("search_cap"),
                        )
                        certified = certify_fragility(
                            simulated.X,
                            greedy,
                            shrinkage=fitted.shrinkage,
                            max_combinations=int(config["certification_combination_budget"]),
                        ) if greedy.reached else None
                        calibration_seed, bootstrap_seed = np.random.SeedSequence(row_seed).spawn(2)
                        calibration = calibrate_fragility(
                            simulated.X,
                            edge=edge,
                            target=target,
                            n_sim=calibration_simulations,
                            rng=np.random.default_rng(calibration_seed),
                            shrinkage=fitted.shrinkage,
                            search_cap=config.get("search_cap"),
                            require_reached=False,
                        )
                        wald = wald_partial_correlation(
                            simulated.X, edge=edge, confidence=bootstrap_confidence
                        )
                        bootstrap = shrinkage_bootstrap(
                            simulated.X,
                            edge=edge,
                            n_boot=bootstrap_samples,
                            rng=np.random.default_rng(bootstrap_seed),
                            shrinkage=fitted.shrinkage,
                            confidence=bootstrap_confidence,
                        )
                        recall = None
                        if simulated.contaminated_cases:
                            influence = exact_loo_influence(simulated.X, fitted).changes[
                                :, edge[0], edge[1]
                            ]
                            order = np.argsort(-np.sign(observed_rho) * influence)
                            top = set(order[: len(simulated.contaminated_cases)].tolist())
                            recall = len(top.intersection(simulated.contaminated_cases)) / len(top)
                        rows.append({
                            "scenario": scenario,
                            "replication": replication,
                            "seed": row_seed,
                            "N": n,
                            "p": p,
                            "fragility_target": target_value,
                            "true_rho": float(simulated.partial_correlation[edge]),
                            "observed_rho": observed_rho,
                            "lambda": fitted.shrinkage,
                            "contamination_count": len(simulated.contaminated_cases),
                            "greedy_fragility_50": greedy.greedy_count,
                            "exact_fragility_50": (
                                None if certified is None else certified.exact_minimum
                            ),
                            "certified": False if certified is None else certified.certified,
                            "reached": greedy.reached,
                            "reference_tail_probability": calibration.reference_tail_probability,
                            "wald_z": wald.z,
                            "bootstrap_ci_excludes_zero": (
                                bootstrap.confidence_interval[0] > 0.0
                                or bootstrap.confidence_interval[1] < 0.0
                            ),
                            "influence_top_k_recall": recall,
                        })
    return rows


def run_simulation(config_path: str | Path, output_path: str | Path, smoke: bool = False) -> None:
    """Run a JSON configuration and write CSV rows plus adjacent metadata."""
    config_file = Path(config_path)
    output_file = Path(output_path)
    config = json.loads(config_file.read_text(encoding="utf-8"))
    started = datetime.now(UTC)
    rows = _run(config, smoke=smoke)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
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
    }
    metadata_path = output_file.with_suffix(".metadata.json")
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    run_simulation(args.config, args.output, smoke=args.smoke)


if __name__ == "__main__":
    main()
