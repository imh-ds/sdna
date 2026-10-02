"""Run paired, checkpointed Task 27 localized-network shards."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from sdna import __version__
from sdna.fragility import FragilityTarget
from simulations.full_workflow import (
    dataset_digest,
    derive_workflow_seeds,
    run_full_workflow,
)
from simulations.localized_network_dgp import FOCAL_EDGES, generate_localized_dataset
from tools.localized_network_manifest import (
    LOCALIZED_PAIRING_FIELDS,
    expand_localized_jobs,
    load_localized_manifest,
    localized_data_seed,
    localized_data_seed_key,
    localized_manifest_checksum,
)

RESULT_FIELDNAMES = [
    "arm", "N", "p", "focal_context", "condition", "replication", "data_seed",
    "calibration_seed", "bootstrap_seed", "dataset_digest", "focal_i", "focal_j",
    "planted_case_indices", "module_count", "true_rho", "observed_rho", "lambda",
    "contamination_count", "contamination_status", "fragility_target", "search_cap",
    "calibration_require_reached", "greedy_fragility_50", "exact_fragility_50",
    "certified", "reached", "certification_combinations_checked",
    "certification_combination_budget", "certification_budget_exhausted",
    "certification_failure_reason", "reference_tail_probability",
    "reference_reached_fraction", "wald_z", "bootstrap_ci_excludes_zero",
    "bootstrap_rejected_resamples", "influence_top_k_precision", "influence_top_k_recall",
    "first_planted_reciprocal_rank", "planted_absolute_influence_share", "fragility_status",
    "certification_status", "calibration_status", "wald_status", "bootstrap_status",
    "workflow_status", "error_stage", "error_type", "error_message", "elapsed_seconds",
]
_ROW_KEY_FIELDS = (*LOCALIZED_PAIRING_FIELDS, "arm")


def _atomic_write_text(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8", newline="")
    os.replace(temporary, path)


def _atomic_write_json(path: Path, value: Any) -> None:
    _atomic_write_text(path, json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def _atomic_write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=RESULT_FIELDNAMES, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _row_identity(row: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(
        int(row[field]) if field in {"N", "p", "replication"} else row[field]
        for field in _ROW_KEY_FIELDS
    )


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _validate_resume_provenance(
    output_dir: Path,
    manifest: dict[str, Any],
    p_shard: int | None,
    git_commit: str | None,
) -> None:
    """Reject persisted rows that cannot be tied to this exact run contract."""
    metadata_path = output_dir / "results.metadata.json"
    if not metadata_path.is_file():
        raise ValueError("existing results.csv has no provenance metadata")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("existing results metadata is unreadable") from error
    expected_metadata = {
        "study": manifest["study"],
        "manifest_checksum": localized_manifest_checksum(manifest),
        "git_commit": git_commit,
        "package_version": __version__,
        "python_version": sys.version.split()[0],
        "numpy_version": np.__version__,
        "p_shard": p_shard,
    }
    if not isinstance(metadata, dict) or any(
        field not in metadata or metadata[field] != expected
        for field, expected in expected_metadata.items()
    ):
        raise ValueError("existing results have incompatible run provenance")
    file_hashes = metadata.get("files")
    if not isinstance(file_hashes, dict):
        raise ValueError("existing results metadata has no file checksums")
    for name in ("results.csv", "shard_status.json"):
        path = output_dir / name
        expected_hash = file_hashes.get(name)
        if not isinstance(expected_hash, str) or not path.is_file():
            raise ValueError(f"existing checkpoint is missing {name} or its checksum")
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise ValueError(f"existing checkpoint {name} checksum mismatch")


def _base_row(job: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    edge = FOCAL_EDGES[job["focal_context"]]
    return {
        **job,
        "calibration_seed": None,
        "bootstrap_seed": None,
        "dataset_digest": None,
        "focal_i": edge[0],
        "focal_j": edge[1],
        "planted_case_indices": "[]",
        "module_count": job["p"] // manifest["modules"]["nodes_per_module"],
        "true_rho": manifest["population"]["focal_partial_correlation"],
        "observed_rho": None,
        "lambda": None,
        "contamination_count": manifest["condition_settings"][job["condition"]][
            "planted_case_count"
        ],
        "contamination_status": int(job["condition"] != "clean"),
        "fragility_target": job["target"],
        "calibration_require_reached": False,
        "greedy_fragility_50": None,
        "exact_fragility_50": None,
        "certified": None,
        "reached": None,
        "certification_combinations_checked": None,
        "certification_combination_budget": manifest["certification_combination_budget"],
        "certification_budget_exhausted": None,
        "certification_failure_reason": None,
        "reference_tail_probability": None,
        "reference_reached_fraction": None,
        "wald_z": None,
        "bootstrap_ci_excludes_zero": None,
        "bootstrap_rejected_resamples": None,
        "influence_top_k_precision": None,
        "influence_top_k_recall": None,
        "first_planted_reciprocal_rank": None,
        "planted_absolute_influence_share": None,
        "fragility_status": "error",
        "certification_status": "error",
        "calibration_status": "error",
        "wald_status": "error",
        "bootstrap_status": "error",
        "workflow_status": "error",
        "error_stage": None,
        "error_type": None,
        "error_message": None,
        "elapsed_seconds": None,
    }


def _csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return ""
    if isinstance(value, float) and not np.isfinite(value):
        return ""
    return value


def _checkpoint(
    output_dir: Path,
    rows: list[dict[str, Any]],
    status: dict[str, Any],
    manifest: dict[str, Any],
    p_shard: int | None,
    started_at: str,
    git_commit: str | None,
) -> None:
    csv_rows = [{key: _csv_value(row.get(key)) for key in RESULT_FIELDNAMES} for row in rows]
    _atomic_write_csv(output_dir / "results.csv", csv_rows)
    _atomic_write_json(output_dir / "shard_status.json", status)
    data = (output_dir / "results.csv").read_bytes()
    metadata = {
        "study": manifest["study"],
        "manifest_checksum": localized_manifest_checksum(manifest),
        "git_commit": git_commit,
        "package_version": __version__,
        "python_version": sys.version.split()[0],
        "numpy_version": np.__version__,
        "p_shard": p_shard,
        "started_at_utc": started_at,
        "updated_at_utc": datetime.now(UTC).isoformat(),
        "files": {
            "results.csv": hashlib.sha256(data).hexdigest(),
            "shard_status.json": hashlib.sha256(
                (output_dir / "shard_status.json").read_bytes()
            ).hexdigest(),
        },
    }
    _atomic_write_json(output_dir / "results.metadata.json", metadata)


def _error_row(
    job: dict[str, Any],
    manifest: dict[str, Any],
    workflow_seeds: Any,
    stage: str,
    error: Exception,
    elapsed: float,
    digest: str | None = None,
    contaminated_cases: tuple[int, ...] = (),
) -> dict[str, Any]:
    row = _base_row(job, manifest)
    row.update(
        {
            "calibration_seed": workflow_seeds.calibration,
            "bootstrap_seed": workflow_seeds.bootstrap,
            "dataset_digest": digest,
            "planted_case_indices": json.dumps(
                list(contaminated_cases), separators=(",", ":")
            ),
            "error_stage": stage,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "elapsed_seconds": elapsed,
        }
    )
    if stage == "generation":
        row["planted_case_indices"] = ""
        row["contamination_count"] = None
        row["contamination_status"] = None
    return row


def run_localized_network(
    config_path: str | Path,
    output_dir: str | Path,
    p_shard: int | None = None,
) -> dict[str, Any]:
    """Run a frozen Task 27 matrix or one ``p`` shard with row checkpoints.

    Existing valid rows in ``results.csv`` are retained and skipped, allowing
    an incomplete shard to resume after interruption.
    """
    manifest = load_localized_manifest(config_path)
    jobs = expand_localized_jobs(manifest, p_shard=p_shard)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    results_path = output / "results.csv"
    git_commit = _git_commit()
    if git_commit is None:
        raise ValueError("Git commit provenance is required to run the localized study")
    rows: list[dict[str, Any]] = []
    if results_path.exists():
        _validate_resume_provenance(output, manifest, p_shard, git_commit)
        with results_path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != RESULT_FIELDNAMES:
                raise ValueError("existing results.csv has an incompatible schema")
            rows = list(reader)
        expected_identities = {_row_identity(job) for job in jobs}
        identities = [_row_identity(row) for row in rows]
        if len(identities) != len(set(identities)) or not set(identities) <= expected_identities:
            raise ValueError("existing results.csv has duplicate or unexpected rows")

    completed = {_row_identity(row) for row in rows}
    expected_rows = len(jobs)
    started_at = datetime.now(UTC).isoformat()
    start = time.monotonic()
    runtime_ceiling = float(manifest["operational_runtime_ceiling_seconds"])
    status: dict[str, Any] = {
        "status": "running",
        "p_shard": p_shard,
        "expected_rows": expected_rows,
        "completed_rows": len(rows),
        "runtime_ceiling_seconds": runtime_ceiling,
        "runtime_ceiling_exceeded": False,
        "elapsed_seconds": 0.0,
        "started_at_utc": started_at,
    }
    _checkpoint(output, rows, status, manifest, p_shard, started_at, git_commit)

    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for job in jobs:
        grouped[tuple(job[field] for field in LOCALIZED_PAIRING_FIELDS)].append(job)

    runtime_exceeded = False
    try:
        for pairing_key in sorted(grouped):
            pair_jobs = grouped[pairing_key]
            missing_jobs = [job for job in pair_jobs if _row_identity(job) not in completed]
            if not missing_jobs:
                continue
            now = time.monotonic()
            if now - start >= runtime_ceiling:
                runtime_exceeded = True
                break
            first = pair_jobs[0]
            data_seed = localized_data_seed(
                manifest["seed"], localized_data_seed_key(first)
            )
            workflow_seeds = derive_workflow_seeds(data_seed)
            dataset = None
            generation_error: Exception | None = None
            try:
                dataset = generate_localized_dataset(
                    first["N"], first["p"], first["focal_context"],
                    first["condition"], data_seed,
                )
                digest = dataset_digest(dataset)
            except Exception as error:  # preserve generation failures as scheduled rows
                generation_error = error
                digest = None
            for job in missing_jobs:
                row_started = time.monotonic()
                try:
                    if generation_error is not None:
                        raise generation_error
                    assert dataset is not None
                    result = run_full_workflow(
                        dataset,
                        target=FragilityTarget("relative", float(job["target"])),
                        search_cap=int(job["search_cap"]),
                        calibration_simulations=int(manifest["calibration_simulations"]),
                        bootstrap_samples=int(manifest["bootstrap_draws"]),
                        bootstrap_confidence=float(manifest["bootstrap_confidence"]),
                        certification_combination_budget=int(
                            manifest["certification_combination_budget"]
                        ),
                        seeds=workflow_seeds,
                        calibration_require_reached=(
                            False if manifest["reference_tail_treatment"] == "right_censored"
                            else bool(manifest["calibration_require_reached"])
                        ),
                    )
                    row = _base_row(job, manifest)
                    row.update(result)
                    row["calibration_seed"] = workflow_seeds.calibration
                    row["bootstrap_seed"] = workflow_seeds.bootstrap
                    row["dataset_digest"] = digest
                    row["planted_case_indices"] = json.dumps(
                        list(dataset.contaminated_cases), separators=(",", ":")
                    )
                except Exception as error:
                    row = _error_row(
                        job, manifest, workflow_seeds,
                        "generation" if generation_error is not None else "workflow",
                        error, time.monotonic() - row_started, digest,
                        () if dataset is None else dataset.contaminated_cases,
                    )
                row["elapsed_seconds"] = time.monotonic() - row_started
                rows.append(row)
                completed.add(_row_identity(job))
                elapsed = time.monotonic() - start
                status.update(
                    {
                        "status": "running",
                        "completed_rows": len(rows),
                        "elapsed_seconds": elapsed,
                    }
                )
                _checkpoint(
                    output, rows, status, manifest, p_shard, started_at, git_commit
                )
                if elapsed >= runtime_ceiling:
                    runtime_exceeded = True
                    break
            if runtime_exceeded:
                break
    except BaseException:
        status.update(
            {
                "status": "incomplete",
                "completed_rows": len(rows),
                "elapsed_seconds": time.monotonic() - start,
            }
        )
        _checkpoint(output, rows, status, manifest, p_shard, started_at, git_commit)
        raise

    elapsed = time.monotonic() - start
    status.update(
        {
            "status": "runtime_ceiling_exceeded" if runtime_exceeded else (
                "complete" if len(rows) == expected_rows else "incomplete"
            ),
            "completed_rows": len(rows),
            "runtime_ceiling_exceeded": runtime_exceeded,
            "elapsed_seconds": elapsed,
        }
    )
    _checkpoint(output, rows, status, manifest, p_shard, started_at, git_commit)
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", default="simulations/configs/localized_network_v1.json",
        help="frozen Task 27 manifest path",
    )
    parser.add_argument("--output-dir", required=True, help="directory for shard artifacts")
    parser.add_argument("--p-shard", type=int, choices=(20, 40, 60))
    args = parser.parse_args(argv)
    status = run_localized_network(args.config, args.output_dir, args.p_shard)
    print(json.dumps(status, sort_keys=True))
    return 0 if status["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
