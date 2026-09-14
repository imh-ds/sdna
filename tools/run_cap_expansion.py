"""Run the paired full-workflow search-cap expansion study."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from sdna import __version__
from sdna.fragility import FragilityTarget
from simulations.full_workflow import (
    dataset_digest,
    derive_workflow_seeds,
    run_full_workflow,
)
from simulations.run_simulation import generate_scenario, replication_seeds
from tools.cap_expansion_manifest import (
    CAP_ARM_NAMES,
    PAIRING_FIELDS,
    expand_cap_expansion_jobs,
    load_cap_expansion_manifest,
    manifest_checksum,
)

CAP_EXPANSION_FIELDNAMES = [
    "arm",
    "scenario",
    "parameter_id",
    "parameter",
    "replication",
    "N",
    "p",
    "data_seed",
    "calibration_seed",
    "bootstrap_seed",
    "dataset_digest",
    "fragility_target",
    "search_cap",
    "calibration_require_reached",
    "true_rho",
    "observed_rho",
    "lambda",
    "contamination_count",
    "contamination_status",
    "greedy_fragility_50",
    "exact_fragility_50",
    "certified",
    "reached",
    "reference_tail_probability",
    "reference_reached_fraction",
    "wald_z",
    "bootstrap_ci_excludes_zero",
    "bootstrap_rejected_resamples",
    "influence_top_k_precision",
    "influence_top_k_recall",
    "first_planted_reciprocal_rank",
    "planted_absolute_influence_share",
    "fragility_status",
    "certification_status",
    "calibration_status",
    "wald_status",
    "bootstrap_status",
    "workflow_status",
    "error_stage",
    "error_type",
    "error_message",
    "elapsed_seconds",
]


def pairing_key(job: dict[str, Any]) -> tuple[Any, ...]:
    """Return the immutable key shared across cap arms."""
    return tuple(job[field] for field in PAIRING_FIELDS)


def _key_order(key: tuple[Any, ...]) -> tuple[Any, ...]:
    scenario, n, p, parameter_id, replication = key
    return n, p, scenario, parameter_id, replication


def _pairing_seed_map(
    manifest: dict[str, Any], jobs: list[dict[str, Any]]
) -> dict[tuple[Any, ...], int]:
    keys = sorted({pairing_key(job) for job in jobs}, key=_key_order)
    seeds = replication_seeds(int(manifest["seed"]), len(keys))
    return dict(zip(keys, seeds, strict=True))


def generate_cap_expansion_dataset(
    job: dict[str, Any], seed: int, manifest: dict[str, Any]
) -> Any:
    """Generate the one DGP dataset shared by a paired key."""
    scenario_config = dict(manifest)
    scenario = str(job["scenario"])
    if scenario == "clean_planted_edge":
        scenario_config["population_partial"] = job["parameter"]
    if scenario == "coalition_contamination":
        scenario_config["contamination_count"] = job["parameter"]
    return generate_scenario(
        scenario,
        int(job["N"]),
        int(job["p"]),
        np.random.default_rng(seed),
        scenario_config,
    )


def _error_row(
    job: dict[str, Any],
    data_seed: int,
    calibration_seed: int,
    bootstrap_seed: int,
    *,
    error_type: str,
    error_message: str,
) -> dict[str, Any]:
    row = {field: None for field in CAP_EXPANSION_FIELDNAMES}
    row.update(
        {
            "arm": job["arm"],
            "scenario": job["scenario"],
            "parameter_id": job["parameter_id"],
            "parameter": job["parameter"],
            "replication": job["replication"],
            "N": job["N"],
            "p": job["p"],
            "data_seed": data_seed,
            "calibration_seed": calibration_seed,
            "bootstrap_seed": bootstrap_seed,
            "fragility_target": job["target"],
            "search_cap": job["search_cap"],
            "calibration_require_reached": False,
            "fragility_status": "error",
            "certification_status": "error",
            "calibration_status": "error",
            "wald_status": "error",
            "bootstrap_status": "error",
            "workflow_status": "error",
            "error_stage": "data",
            "error_type": error_type,
            "error_message": error_message,
            "elapsed_seconds": 0.0,
        }
    )
    return row


def _run_job(
    job: dict[str, Any],
    data_seed: int,
    dataset: Any,
    calibration_simulations: int,
    bootstrap_samples: int,
    bootstrap_confidence: float,
    certification_combination_budget: int,
    calibration_require_reached: bool,
) -> dict[str, Any]:
    started = perf_counter()
    seeds = derive_workflow_seeds(data_seed)
    workflow = run_full_workflow(
        dataset,
        target=FragilityTarget("relative", float(job["target"])),
        search_cap=int(job["search_cap"]),
        calibration_simulations=calibration_simulations,
        bootstrap_samples=bootstrap_samples,
        bootstrap_confidence=bootstrap_confidence,
        certification_combination_budget=certification_combination_budget,
        seeds=seeds,
        calibration_require_reached=calibration_require_reached,
    )
    row = {
        "arm": job["arm"],
        "scenario": job["scenario"],
        "parameter_id": job["parameter_id"],
        "parameter": job["parameter"],
        "replication": job["replication"],
        "N": job["N"],
        "p": job["p"],
        "data_seed": data_seed,
        "calibration_seed": seeds.calibration,
        "bootstrap_seed": seeds.bootstrap,
        "dataset_digest": dataset_digest(dataset),
        "fragility_target": job["target"],
        "search_cap": job["search_cap"],
        "calibration_require_reached": calibration_require_reached,
        **workflow,
        "elapsed_seconds": perf_counter() - started,
    }
    return {field: row.get(field) for field in CAP_EXPANSION_FIELDNAMES}


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _metadata(
    manifest: dict[str, Any], rows: list[dict[str, Any]], elapsed: float
) -> dict[str, Any]:
    arm_elapsed = {
        arm: sum(
            float(row["elapsed_seconds"])
            for row in rows
            if row["arm"] == arm
        )
        for arm in CAP_ARM_NAMES
    }
    stage_fields = (
        "fragility_status",
        "certification_status",
        "calibration_status",
        "wald_status",
        "bootstrap_status",
        "workflow_status",
    )
    return {
        "git_commit": _git_commit(),
        "python_version": sys.version,
        "numpy_version": np.__version__,
        "package_version": __version__,
        "manifest_checksum": manifest_checksum(manifest),
        "rows": len(rows),
        "arm_rows": dict(Counter(str(row["arm"]) for row in rows)),
        "status_counts": {
            field: dict(Counter(str(row[field]) for row in rows)) for field in stage_fields
        },
        "timing": {
            "elapsed_seconds": elapsed,
            "arm_elapsed_seconds": arm_elapsed,
            "runtime_ceiling_seconds": manifest["operational_runtime_ceiling_seconds"],
            "budget_exceeded": elapsed > manifest["operational_runtime_ceiling_seconds"],
        },
    }


def run_cap_expansion(config_path: str | Path, output_path: str | Path) -> None:
    """Run all declared paired jobs and write CSV plus adjacent metadata."""
    manifest = load_cap_expansion_manifest(config_path)
    jobs = expand_cap_expansion_jobs(manifest)
    seeds = _pairing_seed_map(manifest, jobs)
    datasets: dict[tuple[Any, ...], Any] = {}
    rows: list[dict[str, Any]] = []
    started_at = datetime.now(UTC)
    started = perf_counter()
    for job in jobs:
        key = pairing_key(job)
        data_seed = seeds[key]
        child_seeds = derive_workflow_seeds(data_seed)
        if key not in datasets:
            try:
                datasets[key] = generate_cap_expansion_dataset(job, data_seed, manifest)
            except (FloatingPointError, np.linalg.LinAlgError, RuntimeError, ValueError) as error:
                rows.append(
                    _error_row(
                        job,
                        data_seed,
                        child_seeds.calibration,
                        child_seeds.bootstrap,
                        error_type=type(error).__name__,
                        error_message=str(error),
                    )
                )
                continue
        rows.append(
            _run_job(
                job,
                data_seed,
                datasets[key],
                int(manifest["calibration_simulations"]),
                int(manifest["bootstrap_samples"]),
                float(manifest["bootstrap_confidence"]),
                int(manifest["certification_combination_budget"]),
                bool(manifest["calibration_require_reached"]),
            )
        )

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CAP_EXPANSION_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    metadata = _metadata(manifest, rows, perf_counter() - started)
    metadata.update(
        {
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
        }
    )
    output_file.with_suffix(".metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    run_cap_expansion(args.config, args.output)


if __name__ == "__main__":
    main()
