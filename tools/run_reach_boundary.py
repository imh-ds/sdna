"""Run the pre-specified reach-boundary diagnostic study."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from sdna import __version__
from sdna.estimation import fit_network
from sdna.fragility import FragilityTarget, greedy_fragility
from sdna.results import FragilityResult
from simulations.dgp import (
    SimulatedDataset,
    clean_planted_edge,
    coalition_contamination,
    collinearity_stress,
    heavy_tails,
    mixture_subgroup,
    single_influential_case,
)
from simulations.run_simulation import replication_seeds

from tools.reach_boundary_manifest import (
    expand_reach_boundary_jobs,
    load_reach_boundary_manifest,
)

PAIRING_FIELDS = ("scenario", "N", "p", "parameter_id", "replication")
PAIRED_DATA_ARMS = frozenset({"baseline_cap2", "cap3", "cap4", "target07_cap2"})
FIELDNAMES = [
    "arm",
    "scenario",
    "parameter_id",
    "parameter",
    "replication",
    "seed",
    "N",
    "p",
    "fragility_target",
    "search_cap",
    "reached",
    "greedy_count",
    "cap_exhausted",
    "full_value",
    "final_value",
    "trajectory",
    "shrinkage",
    "rank",
    "min_eigenvalue_correlation",
    "min_eigenvalue_shrunk_correlation",
    "condition_number",
    "elapsed_seconds",
    "status",
    "error_type",
    "error_message",
]


def _checksum(manifest: dict[str, Any]) -> str:
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _pairing_key(job: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(job[field] for field in PAIRING_FIELDS)


def _job_order(manifest: dict[str, Any]) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    return (
        {str(value): index for index, value in enumerate(manifest["n_values"])},
        {str(value): index for index, value in enumerate(manifest["p_values"])},
        {str(value): index for index, value in enumerate(manifest["scenarios"])},
    )


def _baseline_seed_map(
    manifest: dict[str, Any], jobs: list[dict[str, Any]]
) -> dict[tuple[Any, ...], int]:
    """Match primary row seeds using the primary N/p/scenario loop order."""
    n_order, p_order, scenario_order = _job_order(manifest)
    baseline_jobs = sorted(
        (job for job in jobs if job["arm"] == "baseline_cap2"),
        key=lambda job: (
            n_order[str(job["N"])],
            p_order[str(job["p"])],
            scenario_order[str(job["scenario"])],
            int(job["parameter_id"]),
            int(job["replication"]),
        ),
    )
    seeds = replication_seeds(int(manifest["seed"]), len(baseline_jobs))
    return {_pairing_key(job): seed for job, seed in zip(baseline_jobs, seeds, strict=True)}


def generate_reach_boundary_dataset(
    job: dict[str, Any], rng: np.random.Generator, manifest: dict[str, Any]
) -> SimulatedDataset:
    """Generate one declared DGP for a reach-boundary job."""
    n = int(job["N"])
    p = int(job["p"])
    edge = tuple(int(value) for value in manifest["focal_edge"])
    scenario = str(job["scenario"])
    parameter = job["parameter"]
    overrides = dict(job["dgp_overrides"])
    if scenario == "clean_planted_edge":
        return clean_planted_edge(n, p, rng, focal_edge=edge, partial=float(parameter))
    if scenario == "single_influential_case":
        return single_influential_case(n, p, rng, focal_edge=edge)
    if scenario == "coalition_contamination":
        return coalition_contamination(
            n,
            p,
            rng,
            n_contaminated=int(parameter),
            focal_edge=edge,
        )
    if scenario == "mixture_subgroup":
        return mixture_subgroup(n, p, rng, focal_edge=edge)
    if scenario == "heavy_tails":
        return heavy_tails(
            n,
            p,
            rng,
            degrees_of_freedom=float(overrides.get("degrees_of_freedom", 5.0)),
            focal_edge=edge,
        )
    if scenario == "collinearity_stress":
        return collinearity_stress(
            n,
            p,
            rng,
            adjacent_correlation=float(overrides.get("adjacent_correlation", 0.95)),
            focal_edge=edge,
        )
    raise ValueError(f"unknown simulation scenario: {scenario}")


def _empty_row(job: dict[str, Any], seed: int) -> dict[str, Any]:
    row = {field: None for field in FIELDNAMES}
    row.update(
        {
            "arm": job["arm"],
            "scenario": job["scenario"],
            "parameter_id": job["parameter_id"],
            "parameter": job["parameter"],
            "replication": job["replication"],
            "seed": seed,
            "N": job["N"],
            "p": job["p"],
            "fragility_target": job["target"],
            "search_cap": job["search_cap"],
        }
    )
    return row


def _successful_row(
    job: dict[str, Any], seed: int, fitted: Any, result: FragilityResult
) -> dict[str, Any]:
    row = _empty_row(job, seed)
    diagnostics = fitted.diagnostics
    row.update(
        {
            "reached": result.reached,
            "greedy_count": result.greedy_count,
            "cap_exhausted": len(result.trajectory) - 1 >= int(job["search_cap"]),
            "full_value": result.full_value,
            "final_value": float(result.trajectory[-1]),
            "trajectory": json.dumps([float(value) for value in result.trajectory]),
            "shrinkage": fitted.shrinkage,
            "rank": diagnostics.rank,
            "min_eigenvalue_correlation": diagnostics.min_eigenvalue_correlation,
            "min_eigenvalue_shrunk_correlation": diagnostics.min_eigenvalue_shrunk_correlation,
            "condition_number": diagnostics.condition_number,
            "status": "ok",
            "error_type": None,
            "error_message": None,
        }
    )
    return row


def _run_job(
    job: dict[str, Any],
    seed: int,
    dataset: SimulatedDataset,
) -> dict[str, Any]:
    started = perf_counter()
    row = _empty_row(job, seed)
    try:
        fitted = fit_network(dataset.X)
        result = greedy_fragility(
            dataset.X,
            edge=dataset.focal_edge,
            target=FragilityTarget("relative", float(job["target"])),
            shrinkage=fitted.shrinkage,
            search_cap=int(job["search_cap"]),
        )
        row = _successful_row(job, seed, fitted, result)
    except (FloatingPointError, np.linalg.LinAlgError, RuntimeError, ValueError) as error:
        row.update(
            {
                "status": "error",
                "error_type": type(error).__name__,
                "error_message": str(error),
            }
        )
    row["elapsed_seconds"] = perf_counter() - started
    return row


def _data_cache_key(job: dict[str, Any]) -> tuple[Any, ...]:
    key = _pairing_key(job)
    return key if job["arm"] in PAIRED_DATA_ARMS else (job["arm"], *key)


def _metadata(manifest: dict[str, Any], rows: list[dict[str, Any]], elapsed: float) -> dict[str, Any]:
    return {
        "git_commit": _git_commit(),
        "python_version": sys.version,
        "numpy_version": np.__version__,
        "package_version": __version__,
        "manifest_checksum": _checksum(manifest),
        "rows": len(rows),
        "arm_rows": dict(Counter(str(row["arm"]) for row in rows)),
        "status_counts": dict(Counter(str(row["status"]) for row in rows)),
        "timing": {"elapsed_seconds": elapsed},
    }


def run_reach_boundary(config_path: str | Path, output_path: str | Path) -> None:
    """Run the declared reach-boundary jobs and write CSV plus metadata."""
    manifest = load_reach_boundary_manifest(config_path)
    jobs = expand_reach_boundary_jobs(manifest)
    seed_map = _baseline_seed_map(manifest, jobs)
    datasets: dict[tuple[Any, ...], SimulatedDataset] = {}
    rows: list[dict[str, Any]] = []
    started = perf_counter()
    for job in jobs:
        key = _pairing_key(job)
        if key not in seed_map:
            raise ValueError(f"job has no baseline pairing key: {key}")
        seed = seed_map[key]
        cache_key = _data_cache_key(job)
        if cache_key not in datasets:
            datasets[cache_key] = generate_reach_boundary_dataset(
                job, np.random.default_rng(seed), manifest
            )
        rows.append(_run_job(job, seed, datasets[cache_key]))

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    metadata_path = output_file.with_suffix(".metadata.json")
    metadata_path.write_text(
        json.dumps(_metadata(manifest, rows, perf_counter() - started), indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    run_reach_boundary(args.config, args.output)


if __name__ == "__main__":
    main()
