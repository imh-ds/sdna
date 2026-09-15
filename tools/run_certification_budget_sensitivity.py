"""Run one deterministic certification-budget sensitivity arm."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from sdna import __version__
from sdna.exceptions import CalibrationError
from sdna.fragility import FragilityTarget
from simulations.full_workflow import dataset_digest, derive_workflow_seeds, run_full_workflow
from tools.cap_expansion_manifest import (
    PAIRING_FIELDS,
    load_cap_expansion_manifest,
    manifest_checksum,
)
from tools.certification_budget_sensitivity_manifest import (
    certification_budget_sensitivity_manifest_checksum,
    load_certification_budget_sensitivity_manifest,
)
from tools.prepare_certification_budget_sensitivity import load_selection_manifest
from tools.run_cap_expansion import (
    CAP_EXPANSION_FIELDNAMES,
    CERTIFICATION_DIAGNOSTIC_FIELDNAMES,
    generate_cap_expansion_dataset,
)

__all__ = ["SENSITIVITY_FIELDNAMES", "run_certification_budget_arm"]

SENSITIVITY_FIELDNAMES = CAP_EXPANSION_FIELDNAMES + CERTIFICATION_DIAGNOSTIC_FIELDNAMES

_ROW_ERRORS = (
    CalibrationError,
    FloatingPointError,
    np.linalg.LinAlgError,
    RuntimeError,
    ValueError,
)
_PROVENANCE_FIELDS = (
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
)
_STAGE_STATUS_FIELDS = (
    "fragility_status",
    "certification_status",
    "calibration_status",
    "wald_status",
    "bootstrap_status",
)


def _canonical_job(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "arm": str(candidate["arm"]),
        "scenario": str(candidate["scenario"]),
        "parameter_id": int(candidate["parameter_id"]),
        "parameter": float(candidate["parameter"]),
        "replication": int(candidate["replication"]),
        "N": int(candidate["N"]),
        "p": int(candidate["p"]),
        "target": float(candidate["fragility_target"]),
        "search_cap": int(candidate["search_cap"]),
    }


def _pairing_key(job: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(job[field] for field in PAIRING_FIELDS)


def _completed_key(job: dict[str, Any]) -> dict[str, Any]:
    return {"arm": job["arm"], **{field: job[field] for field in PAIRING_FIELDS}}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(path)


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _environment() -> dict[str, Any]:
    return {
        "git_commit": _git_commit(),
        "python_version": sys.version,
        "numpy_version": np.__version__,
        "package_version": __version__,
        "platform": platform.platform(),
    }


def _source_checksums(
    study_manifest: dict[str, Any] | None,
    source_manifest: dict[str, Any] | None,
    selection: dict[str, Any] | None,
) -> dict[str, Any]:
    if study_manifest is None:
        return {}
    return {
        "study_manifest": certification_budget_sensitivity_manifest_checksum(
            study_manifest
        ),
        "selection_manifest": (
            selection["selection_checksum"] if selection is not None else None
        ),
        "source_manifest": (
            manifest_checksum(source_manifest) if source_manifest is not None else None
        ),
        "source_task25_results": study_manifest["source_task25_results_sha256"],
        "source_task25_manifest": study_manifest[
            "source_task25_manifest_checksum"
        ],
        "source_task24_results": study_manifest["source_task24_results_sha256"],
        "source_task24_manifest": study_manifest[
            "source_task24_manifest_checksum"
        ],
    }


def _error_row(
    candidate: dict[str, Any],
    budget: int,
    error: Exception,
    *,
    stage: str,
    elapsed_seconds: float,
) -> dict[str, Any]:
    row = {field: None for field in SENSITIVITY_FIELDNAMES}
    row.update({field: candidate.get(field) for field in _PROVENANCE_FIELDS})
    row.update(
        {
            **{field: "error" for field in _STAGE_STATUS_FIELDS},
            "workflow_status": "error",
            "error_stage": stage,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "elapsed_seconds": elapsed_seconds,
            "certification_combinations_checked": None,
            "certification_combination_budget": budget,
            "certification_budget_exhausted": False,
            "certification_failure_reason": (
                "not_applicable_prior_error" if stage == "data" else "error"
            ),
        }
    )
    return row


def _status_record(
    *,
    arm_status: str,
    budget: int,
    expected_rows: int,
    rows: list[dict[str, Any]],
    completed_keys: list[dict[str, Any]],
    elapsed_seconds: float,
    runtime_ceiling_seconds: float,
    started_at: str,
    source_checksums: dict[str, Any],
    environment: dict[str, Any],
    error: Exception | None = None,
) -> dict[str, Any]:
    cap_counts = Counter(str(row["arm"]) for row in rows)
    arm_rows = {
        "cap3": cap_counts.get("cap3", 0),
        "cap4": cap_counts.get("cap4", 0),
    }
    return {
        "schema_version": 1,
        "study": "certification_budget_sensitivity",
        "arm_status": arm_status,
        "budget": budget,
        "expected_rows": expected_rows,
        "rows": len(rows),
        "completed_rows": len(rows),
        "arm_rows": arm_rows,
        "observed_cap_rows": arm_rows,
        "certification_budget_exhausted_rows": sum(
            str(row.get("certification_budget_exhausted", "")).lower() == "true"
            for row in rows
        ),
        "completed_keys": completed_keys,
        "last_completed_key": completed_keys[-1] if completed_keys else None,
        "elapsed_seconds": elapsed_seconds,
        "runtime_ceiling_seconds": runtime_ceiling_seconds,
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "source_checksums": source_checksums,
        "environment": environment,
        "error_type": type(error).__name__ if error is not None else None,
        "error_message": str(error) if error is not None else None,
    }


def _checkpoint(
    output_path: Path,
    results_path: Path,
    *,
    arm_status: str,
    budget: int,
    expected_rows: int,
    rows: list[dict[str, Any]],
    completed_keys: list[dict[str, Any]],
    elapsed_seconds: float,
    runtime_ceiling_seconds: float,
    started_at: str,
    source_checksums: dict[str, Any],
    environment: dict[str, Any],
    error: Exception | None = None,
) -> dict[str, Any]:
    status = _status_record(
        arm_status=arm_status,
        budget=budget,
        expected_rows=expected_rows,
        rows=rows,
        completed_keys=completed_keys,
        elapsed_seconds=elapsed_seconds,
        runtime_ceiling_seconds=runtime_ceiling_seconds,
        started_at=started_at,
        source_checksums=source_checksums,
        environment=environment,
        error=error,
    )
    results_checksum = _sha256_file(results_path)
    metadata = {**status, "artifact_checksums": {"results.csv": results_checksum}}
    metadata_path = output_path / "results.metadata.json"
    _atomic_write_json(metadata_path, metadata)
    status["artifact_checksums"] = {
        "results.csv": results_checksum,
        "results.metadata.json": _sha256_file(metadata_path),
    }
    _atomic_write_json(output_path / "arm_status.json", status)
    return status


def _workflow_row(
    candidate: dict[str, Any],
    job: dict[str, Any],
    dataset: Any,
    study_manifest: dict[str, Any],
    budget: int,
) -> dict[str, Any]:
    row_started = perf_counter()
    seeds = derive_workflow_seeds(int(candidate["data_seed"]))
    workflow = run_full_workflow(
        dataset,
        target=FragilityTarget("relative", job["target"]),
        search_cap=job["search_cap"],
        calibration_simulations=int(study_manifest["calibration_simulations"]),
        bootstrap_samples=int(study_manifest["bootstrap_samples"]),
        bootstrap_confidence=float(study_manifest["bootstrap_confidence"]),
        certification_combination_budget=budget,
        seeds=seeds,
        calibration_require_reached=bool(study_manifest["calibration_require_reached"]),
    )

    row = dict(candidate)
    row.update(workflow)
    row.update({field: candidate[field] for field in _PROVENANCE_FIELDS})
    row["certification_combination_budget"] = budget
    row["elapsed_seconds"] = perf_counter() - row_started
    return {field: row.get(field) for field in SENSITIVITY_FIELDNAMES}


def run_certification_budget_arm(
    selection_manifest_path: str | Path,
    source_manifest_path: str | Path,
    study_manifest_path: str | Path,
    budget: int,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Run one fixed budget arm and return its persisted status mapping."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    results_path = output_path / "results.csv"
    rows: list[dict[str, Any]] = []
    completed_keys: list[dict[str, Any]] = []
    datasets: dict[
        tuple[Any, ...], tuple[Any | None, Exception | None, float]
    ] = {}
    study_manifest: dict[str, Any] | None = None
    source_manifest: dict[str, Any] | None = None
    selection: dict[str, Any] | None = None
    expected_rows = 0
    runtime_ceiling_seconds = 1800.0
    environment = _environment()
    started_at = datetime.now(UTC).isoformat()
    started = perf_counter()

    with results_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SENSITIVITY_FIELDNAMES)
        writer.writeheader()
        handle.flush()

        try:
            study_manifest = load_certification_budget_sensitivity_manifest(
                study_manifest_path
            )
            expected_rows = int(study_manifest["expected_rows_per_budget"])
            runtime_ceiling_seconds = float(study_manifest["runtime_ceiling_seconds"])
            if budget not in study_manifest["budget_grid"]:
                raise ValueError(
                    "budget is not in the certification-budget sensitivity grid"
                )
            source_manifest = load_cap_expansion_manifest(source_manifest_path)
            if manifest_checksum(source_manifest) != study_manifest[
                "source_task24_manifest_checksum"
            ]:
                raise ValueError("Task 24 source manifest checksum does not match")
            selection = load_selection_manifest(selection_manifest_path, study_manifest)
            checksums = _source_checksums(study_manifest, source_manifest, selection)
            _checkpoint(
                output_path,
                results_path,
                arm_status="incomplete",
                budget=budget,
                expected_rows=expected_rows,
                rows=rows,
                completed_keys=completed_keys,
                elapsed_seconds=perf_counter() - started,
                runtime_ceiling_seconds=runtime_ceiling_seconds,
                started_at=started_at,
                source_checksums=checksums,
                environment=environment,
            )

            entries = [
                entry
                for cap in ("cap3", "cap4")
                for entry in selection["populations"][cap]
            ]
            for entry in entries:
                elapsed = perf_counter() - started
                if elapsed >= runtime_ceiling_seconds:
                    return _checkpoint(
                        output_path,
                        results_path,
                        arm_status="timeout",
                        budget=budget,
                        expected_rows=expected_rows,
                        rows=rows,
                        completed_keys=completed_keys,
                        elapsed_seconds=elapsed,
                        runtime_ceiling_seconds=runtime_ceiling_seconds,
                        started_at=started_at,
                        source_checksums=checksums,
                        environment=environment,
                    )

                candidate = dict(entry["candidate"])
                job = _canonical_job(candidate)
                key = _pairing_key(job)
                data_seed = int(candidate["data_seed"])
                seeds = derive_workflow_seeds(data_seed)
                if seeds.calibration != int(candidate["calibration_seed"]):
                    raise ValueError("calibration child seed does not match Task 25")
                if seeds.bootstrap != int(candidate["bootstrap_seed"]):
                    raise ValueError("bootstrap child seed does not match Task 25")

                if key not in datasets:
                    generation_started = perf_counter()
                    try:
                        dataset = generate_cap_expansion_dataset(
                            job, data_seed, source_manifest
                        )
                        datasets[key] = (
                            dataset,
                            None,
                            perf_counter() - generation_started,
                        )
                    except _ROW_ERRORS as error:
                        datasets[key] = (
                            None,
                            error,
                            perf_counter() - generation_started,
                        )
                dataset, generation_error, generation_elapsed = datasets[key]
                if generation_error is not None:
                    row = _error_row(
                        candidate,
                        budget,
                        generation_error,
                        stage="data",
                        elapsed_seconds=generation_elapsed,
                    )
                else:
                    assert dataset is not None
                    if dataset_digest(dataset) != str(candidate["dataset_digest"]):
                        raise ValueError(
                            "regenerated dataset digest does not match Task 25"
                        )
                    row = _workflow_row(candidate, job, dataset, study_manifest, budget)

                writer.writerow(row)
                handle.flush()
                rows.append(row)
                completed_keys.append(_completed_key(job))
                _checkpoint(
                    output_path,
                    results_path,
                    arm_status="incomplete",
                    budget=budget,
                    expected_rows=expected_rows,
                    rows=rows,
                    completed_keys=completed_keys,
                    elapsed_seconds=perf_counter() - started,
                    runtime_ceiling_seconds=runtime_ceiling_seconds,
                    started_at=started_at,
                    source_checksums=checksums,
                    environment=environment,
                )

            final_status = "complete" if len(rows) == expected_rows else "incomplete"
            return _checkpoint(
                output_path,
                results_path,
                arm_status=final_status,
                budget=budget,
                expected_rows=expected_rows,
                rows=rows,
                completed_keys=completed_keys,
                elapsed_seconds=perf_counter() - started,
                runtime_ceiling_seconds=runtime_ceiling_seconds,
                started_at=started_at,
                source_checksums=checksums,
                environment=environment,
            )
        except Exception as error:  # noqa: BLE001 - persist unexpected arm failures
            handle.flush()
            return _checkpoint(
                output_path,
                results_path,
                arm_status="failed",
                budget=budget,
                expected_rows=expected_rows,
                rows=rows,
                completed_keys=completed_keys,
                elapsed_seconds=perf_counter() - started,
                runtime_ceiling_seconds=runtime_ceiling_seconds,
                started_at=started_at,
                source_checksums=_source_checksums(
                    study_manifest, source_manifest, selection
                ),
                environment=environment,
                error=error,
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("selection_manifest_path", type=Path)
    parser.add_argument("source_manifest_path", type=Path)
    parser.add_argument("study_manifest_path", type=Path)
    parser.add_argument("budget", type=int)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    status = run_certification_budget_arm(**vars(args))
    raise SystemExit(0 if status["arm_status"] == "complete" else 1)


if __name__ == "__main__":
    main()
