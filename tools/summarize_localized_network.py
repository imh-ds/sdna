"""Validate and summarize Task 27 localized-network shard artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from simulations.full_workflow import derive_workflow_seeds
from simulations.localized_network_dgp import build_localized_population
from tools.localized_network_manifest import (
    expand_localized_jobs,
    load_localized_manifest,
    localized_manifest_checksum,
)

FIELDNAMES = (
    "arm,N,p,focal_context,condition,replication,data_seed,calibration_seed,"
    "bootstrap_seed,dataset_digest,focal_i,focal_j,planted_case_indices,"
    "module_count,true_rho,observed_rho,lambda,condition_number,contamination_count,"
    "contamination_status,fragility_target,search_cap,calibration_require_reached,"
    "greedy_fragility_50,exact_fragility_50,certified,reached,"
    "certification_combinations_checked,certification_combination_budget,"
    "certification_budget_exhausted,certification_failure_reason,"
    "reference_tail_probability,reference_reached_fraction,wald_z,"
    "bootstrap_ci_excludes_zero,bootstrap_rejected_resamples,"
    "influence_top_k_precision,influence_top_k_recall,"
    "first_planted_reciprocal_rank,planted_absolute_influence_share,"
    "fragility_status,certification_status,calibration_status,wald_status,"
    "bootstrap_status,workflow_status,error_stage,error_type,error_message,"
    "elapsed_seconds"
).split(",")
_ARM_NAMES = {"baseline_cap2", "diagnostic_cap4"}
_ROW_KEY_FIELDS = ("arm", "N", "p", "focal_context", "condition", "replication")
_STATUS_VALUES = {
    "fragility_status": {"reached", "unreached", "error"},
    "certification_status": {"certified", "not_certified", "skipped_unreached", "error"},
    "calibration_status": {"finite", "right_censored", "observed_unreached", "error"},
    "wald_status": {"ok", "error"},
    "bootstrap_status": {"ok", "error"},
    "workflow_status": {"ok", "partial", "error"},
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _integer(value: Any, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be an integer") from error
    if str(value).strip() not in {str(number), f"+{number}"} or number < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return number


def _number(value: Any, name: str, *, optional: bool = False) -> float | None:
    if optional and (value is None or str(value).strip() == ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a finite number") from error
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    return number


def _boolean(value: Any, name: str, *, optional: bool = False) -> bool | None:
    if optional and (value is None or str(value).strip() == ""):
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise ValueError(f"{name} must be Boolean")


def _json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is missing or malformed: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != FIELDNAMES:
                raise ValueError("results CSV fields do not match the frozen Task 27 schema")
            rows = list(reader)
    except OSError as error:
        raise ValueError(f"results.csv is missing or unreadable: {error}") from error
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError("results.csv contains malformed rows")
    return rows


def _load_shard(
    shard_dir: Path, manifest: Mapping[str, Any], expected_by_key: Mapping[tuple[Any, ...], Mapping[str, Any]]
) -> tuple[int, list[dict[str, Any]], dict[str, Any], str | None]:
    status_path = shard_dir / "shard_status.json"
    metadata_path = shard_dir / "results.metadata.json"
    try:
        status = _json_object(status_path, "shard_status.json")
        metadata = _json_object(metadata_path, "results.metadata.json")
        expected_status_fields = {
            "status", "p_shard", "expected_rows", "completed_rows",
            "runtime_ceiling_seconds", "runtime_ceiling_exceeded",
            "elapsed_seconds", "started_at_utc",
        }
        if set(status) != expected_status_fields:
            raise ValueError("shard_status.json fields do not match the Task 3 runner contract")
        expected_metadata_fields = {
            "study", "manifest_checksum", "git_commit", "package_version",
            "python_version", "numpy_version", "p_shard", "started_at_utc",
            "updated_at_utc", "files",
        }
        if set(metadata) != expected_metadata_fields:
            raise ValueError("results.metadata.json fields do not match the Task 3 runner contract")
        p = _integer(status.get("p_shard"), "p_shard", minimum=1)
        if p not in manifest["p_values"] or metadata.get("p_shard") != p:
            raise ValueError("shard p provenance does not match the frozen manifest")
        if metadata.get("study") != manifest["study"]:
            raise ValueError("shard study provenance does not match the manifest")
        manifest_digest = localized_manifest_checksum(manifest)
        if metadata.get("manifest_checksum") != manifest_digest:
            raise ValueError("shard manifest checksum does not match the frozen configuration")
        required_metadata = {
            "git_commit", "package_version", "python_version", "numpy_version",
            "started_at_utc", "updated_at_utc", "files",
        }
        if not required_metadata.issubset(metadata):
            raise ValueError("results metadata is missing runner provenance fields")
        if not isinstance(metadata["git_commit"], str) or not metadata["git_commit"]:
            raise ValueError("metadata git_commit must identify the source commit")
        if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", metadata["git_commit"]):
            raise ValueError("metadata git_commit must be a full hexadecimal Git object ID")
        for field in ("package_version", "python_version", "numpy_version"):
            if not isinstance(metadata[field], str) or not metadata[field]:
                raise ValueError(f"metadata {field} must be a nonempty string")
        results_path = shard_dir / "results.csv"
        rows = _read_csv(results_path)
        files = metadata.get("files")
        expected_files = {
            "results.csv": _sha256(results_path),
            "shard_status.json": _sha256(status_path),
        }
        if files != expected_files:
            raise ValueError("artifact checksums do not match results metadata")
        if status.get("started_at_utc") != metadata["started_at_utc"]:
            raise ValueError("shard start time does not match results metadata")
        if status.get("expected_rows") != manifest["expected_rows_per_p"]:
            raise ValueError("shard expected row count does not match manifest")
        if status.get("completed_rows") != len(rows):
            raise ValueError("shard completed row count does not match results.csv")
        shard_status = status.get("status")
        if shard_status not in {"complete", "incomplete", "running", "runtime_ceiling_exceeded"}:
            raise ValueError("shard status is not a runner status")
        elapsed = _number(status.get("elapsed_seconds"), "shard elapsed_seconds")
        runtime_ceiling = _number(status.get("runtime_ceiling_seconds"), "runtime_ceiling_seconds")
        if runtime_ceiling != manifest["operational_runtime_ceiling_seconds"]:
            raise ValueError("shard runtime ceiling does not match the frozen manifest")
        ceiling_exceeded = _boolean(status.get("runtime_ceiling_exceeded"), "runtime_ceiling_exceeded")
        if ceiling_exceeded != (shard_status == "runtime_ceiling_exceeded"):
            raise ValueError("shard runtime ceiling status is inconsistent")
        if shard_status == "complete" and len(rows) != manifest["expected_rows_per_p"]:
            raise ValueError("complete shard does not contain all expected rows")
        if elapsed < 0:
            raise ValueError("shard elapsed_seconds must be nonnegative")
        accepted, row_issue, duplicate_count = _validate_rows(rows, p, expected_by_key)
        if shard_status != "complete":
            row_issue = row_issue or f"shard reported {shard_status}"
        metadata["_shard_status"] = shard_status
        metadata["_duplicate_rows"] = duplicate_count
        return p, accepted, metadata, row_issue
    except (ValueError, OSError, TypeError, KeyError) as error:
        p_value = None
        try:
            p_value = _integer(status.get("p_shard"), "p_shard", minimum=1)
        except (UnboundLocalError, AttributeError, ValueError):
            # The directory name is intentionally not treated as authoritative provenance.
            pass
        if p_value is None:
            raise ValueError(f"{shard_dir}: {error}") from error
        return p_value, [], {}, str(error)


def _validate_rows(
    rows: Sequence[Mapping[str, Any]],
    p_shard: int,
    expected_by_key: Mapping[tuple[Any, ...], Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], str | None, int]:
    seen: set[tuple[Any, ...]] = set()
    valid: list[dict[str, Any]] = []
    issue: str | None = None
    pair_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    context_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    invalid_pair_keys: set[tuple[Any, ...]] = set()
    duplicate_count = 0
    population = build_localized_population(p_shard)
    for source in rows:
        row = dict(source)
        try:
            arm = row["arm"]
            if arm not in _ARM_NAMES:
                raise ValueError("unknown arm")
            key = (
                arm,
                _integer(row["N"], "N", minimum=1),
                _integer(row["p"], "p", minimum=1),
                row["focal_context"],
                row["condition"],
                _integer(row["replication"], "replication"),
            )
            generation_failed = row["error_stage"] == "generation" and row["workflow_status"] == "error"
            if key in seen:
                duplicate_count += 1
                raise ValueError("duplicate arm/pairing key")
            seen.add(key)
            job = expected_by_key.get(key)
            if job is None or job["p"] != p_shard:
                raise ValueError("row key is not in this frozen p shard")
            for field in (
                "N", "p", "replication", "data_seed", "focal_i", "focal_j",
                "module_count", "search_cap",
                "certification_combination_budget",
            ):
                row[field] = _integer(row[field], field)
            if generation_failed and not str(row["contamination_count"]).strip():
                row["contamination_count"] = None
            else:
                row["contamination_count"] = _integer(
                    row["contamination_count"], "contamination_count"
                )
            for field in ("calibration_seed", "bootstrap_seed", "certification_combinations_checked"):
                row[field] = _integer(row[field], field) if str(row[field]).strip() else None
            if row["data_seed"] != job["data_seed"]:
                raise ValueError("data_seed does not match deterministic manifest seed")
            streams = derive_workflow_seeds(int(job["data_seed"]))
            if row["calibration_seed"] != streams.calibration or row["bootstrap_seed"] != streams.bootstrap:
                raise ValueError("paired workflow seed metadata is inconsistent")
            if row["search_cap"] != job["search_cap"] or _number(row["fragility_target"], "fragility_target") != job["target"]:
                raise ValueError("arm target or search cap does not match manifest")
            if _boolean(row["calibration_require_reached"], "calibration_require_reached") is not False:
                raise ValueError("calibration requirement does not match manifest")
            digest_value = str(row["dataset_digest"]).strip()
            digest = digest_value or None
            if generation_failed and digest is not None:
                raise ValueError("generation errors must not claim a dataset digest")
            if digest is None and not generation_failed:
                raise ValueError("dataset_digest is missing outside a generation error")
            if digest is not None and (
                len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest)
            ):
                raise ValueError("dataset_digest must be a lowercase SHA-256 hex digest")
            row["dataset_digest"] = digest
            focal_context, condition = row["focal_context"], row["condition"]
            focal_i, focal_j = population.focal_edges[focal_context]
            if (row["focal_i"], row["focal_j"]) != (focal_i, focal_j):
                raise ValueError("focal edge indices do not match the DGP truth")
            if row["module_count"] != p_shard // 5:
                raise ValueError("module_count does not match the DGP")
            true_rho = _number(row["true_rho"], "true_rho")
            expected_rho = float(population.partial_correlation[focal_i, focal_j])
            if not math.isclose(true_rho, expected_rho, rel_tol=0.0, abs_tol=1e-12):
                raise ValueError("true_rho does not match the DGP focal edge")
            if generation_failed and not str(row["planted_case_indices"]).strip():
                case_indices = []
            else:
                try:
                    case_indices = json.loads(row["planted_case_indices"])
                except json.JSONDecodeError as error:
                    raise ValueError("planted_case_indices is malformed JSON") from error
            if not isinstance(case_indices, list) or any(isinstance(i, bool) or not isinstance(i, int) for i in case_indices):
                raise ValueError("planted_case_indices must be a JSON integer array")
            expected_case_count = {"clean": 0, "single_case": 1, "coalition": 3}[condition]
            if (
                not (generation_failed and digest is None and not case_indices)
                and len(case_indices) != expected_case_count
            ) or len(set(case_indices)) != len(case_indices) or any(
                i < 0 or i >= row["N"] for i in case_indices
            ) or case_indices != sorted(case_indices):
                raise ValueError("planted case indices do not match the condition or N")
            if generation_failed and row["contamination_count"] is not None:
                raise ValueError("generation errors must leave contamination_count unavailable")
            if not generation_failed and row["contamination_count"] != expected_case_count:
                raise ValueError("contamination_count does not match the condition")
            for field, allowed in _STATUS_VALUES.items():
                if row[field] not in allowed:
                    raise ValueError(f"invalid {field}: {row[field]}")
            for field in ("certified", "reached", "certification_budget_exhausted"):
                row[field] = _boolean(row[field], field, optional=True)
            for field in (
                "observed_rho", "lambda", "condition_number", "greedy_fragility_50", "exact_fragility_50",
                "reference_reached_fraction", "wald_z", "influence_top_k_precision",
                "influence_top_k_recall", "first_planted_reciprocal_rank",
                "planted_absolute_influence_share",
            ):
                row[field] = _number(row[field], field, optional=True)
            if condition == "clean":
                try:
                    row["reference_tail_probability"] = _number(
                        row["reference_tail_probability"], "reference_tail_probability", optional=True
                    )
                except ValueError:
                    row["reference_tail_probability"] = None
                if row["reference_tail_probability"] is not None and not 0.0 <= row["reference_tail_probability"] <= 1.0:
                    row["reference_tail_probability"] = None
            else:
                row["reference_tail_probability"] = _number(
                    row["reference_tail_probability"], "reference_tail_probability", optional=True
                )
            row["bootstrap_ci_excludes_zero"] = _boolean(row["bootstrap_ci_excludes_zero"], "bootstrap_ci_excludes_zero", optional=True)
            for field in ("reference_tail_probability", "reference_reached_fraction", "influence_top_k_precision", "influence_top_k_recall", "first_planted_reciprocal_rank", "planted_absolute_influence_share"):
                value = row[field]
                if value is not None and not 0.0 <= value <= 1.0:
                    raise ValueError(f"{field} must be within [0, 1]")
            if row["condition_number"] is not None and row["condition_number"] <= 0.0:
                raise ValueError("condition_number must be positive")
            row["elapsed_seconds"] = _number(row["elapsed_seconds"], "elapsed_seconds")
            if row["elapsed_seconds"] < 0:
                raise ValueError("elapsed_seconds must be nonnegative")
            if generation_failed and str(row["contamination_status"]).strip():
                raise ValueError("generation errors must leave contamination_status unavailable")
            if not generation_failed and _integer(row["contamination_status"], "contamination_status") != int(expected_case_count > 0):
                raise ValueError("contamination_status does not match condition")
            if row["fragility_status"] == "reached" and row["reached"] is not True:
                raise ValueError("reached status requires reached=true")
            if row["fragility_status"] == "unreached" and row["reached"] is not False:
                raise ValueError("unreached status requires reached=false")
            if row["fragility_status"] == "error" and row["reached"] is not None:
                raise ValueError("fragility errors must not claim a reached outcome")
            if row["certification_status"] == "certified" and row["certified"] is not True:
                raise ValueError("certified status requires certified=true")
            if row["certification_status"] == "not_certified" and row["certified"] is not False:
                raise ValueError("not_certified status requires certified=false")
            if row["certification_status"] == "skipped_unreached" and row["reached"] is not False:
                raise ValueError("skipped certification requires an unreached row")
            if row["certification_status"] == "not_certified" and row["certification_budget_exhausted"] is not True:
                raise ValueError("not_certified status requires exhausted budget")
            has_stage_error = any(
                row[field] == "error"
                for field in (
                    "fragility_status", "certification_status", "calibration_status",
                    "wald_status", "bootstrap_status",
                )
            )
            influence_error = row["error_stage"] == "influence"
            if influence_error and condition == "clean":
                raise ValueError("influence errors are only valid for contaminated rows")
            if (has_stage_error or influence_error) != (row["workflow_status"] == "error"):
                raise ValueError("workflow_status does not match stage outcomes")
            expected_workflow_status = (
                "partial"
                if row["fragility_status"] == "unreached"
                or row["calibration_status"] == "observed_unreached"
                else "ok"
            )
            if not has_stage_error and not influence_error and row["workflow_status"] != expected_workflow_status:
                raise ValueError("workflow_status does not match completed stages")
            if row["workflow_status"] == "error":
                if not row["error_stage"] or not row["error_type"]:
                    raise ValueError("workflow errors require stage and type")
                if row["error_stage"] not in {"generation", "fit", "fragility", "certification", "calibration", "wald", "bootstrap", "influence", "workflow"}:
                    raise ValueError("error_stage is not recognized")
            elif any(str(row[field]).strip() for field in ("error_stage", "error_type", "error_message")):
                raise ValueError("non-error workflow rows cannot contain error metadata")
            if str(row["bootstrap_rejected_resamples"]).strip():
                row["bootstrap_rejected_resamples"] = _integer(
                    row["bootstrap_rejected_resamples"], "bootstrap_rejected_resamples"
                )
            else:
                row["bootstrap_rejected_resamples"] = None
            pair_groups[tuple(key[1:])].append(row)
            context_groups[(row["N"], row["p"], condition, row["replication"])].append(row)
            valid.append(row)
        except (KeyError, ValueError, TypeError, IndexError) as error:
            issue = issue or str(error)
    for key, paired in pair_groups.items():
        if len(paired) != 2 or {row["arm"] for row in paired} != _ARM_NAMES:
            issue = issue or f"pair {key} is missing a cap arm member"
            continue
        for field in ("data_seed", "calibration_seed", "bootstrap_seed", "dataset_digest", "planted_case_indices", "true_rho", "focal_i", "focal_j"):
            if len({str(row[field]) for row in paired}) != 1:
                issue = issue or f"paired rows disagree on {field} for {key}"
                invalid_pair_keys.add(key)
    for key, contexts in context_groups.items():
        if len(contexts) != 6:
            issue = issue or f"context group {key} does not contain three paired focal contexts"
            continue
        shared_context_fields = ["data_seed", "planted_case_indices"]
        if key[2] == "clean":
            shared_context_fields.append("dataset_digest")
        for field in shared_context_fields:
            if len({str(row[field]) for row in contexts}) != 1:
                issue = issue or f"focal contexts disagree on {field} for {key}"
                invalid_pair_keys.update(
                    tuple(row[name] for name in ("N", "p", "focal_context", "condition", "replication"))
                    for row in contexts
                )
    if invalid_pair_keys:
        valid = [
            row for row in valid
            if tuple(row[name] for name in ("N", "p", "focal_context", "condition", "replication"))
            not in invalid_pair_keys
        ]
    return valid, issue, duplicate_count


def wilson_interval(successes: int, total: int, confidence: float = 0.95) -> list[float] | None:
    """Return a two-sided Wilson score interval (95% by default)."""
    if total == 0:
        return None
    # 1.959963984540054 is the two-sided 95% normal quantile.
    if confidence != 0.95:
        raise ValueError("Task 27 reports fixed 95% Wilson intervals")
    z = 1.959963984540054
    proportion = successes / total
    scale = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / scale
    margin = z * math.sqrt(proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total)) / scale
    return [max(0.0, center - margin), min(1.0, center + margin)]


def _proportion(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "estimate": numerator / denominator if denominator else None,
        "wilson_95": wilson_interval(numerator, denominator),
    }


def _mean_metric(values: Sequence[float | None], scheduled: int) -> dict[str, Any]:
    finite = [value for value in values if value is not None and math.isfinite(value)]
    return {
        "mean": sum(finite) / len(finite) if finite else None,
        "valid_rows": len(finite),
        "scheduled_rows": scheduled,
    }


def _numeric_range(values: Sequence[float | None], scheduled: int) -> dict[str, Any]:
    finite = [value for value in values if value is not None and math.isfinite(value)]
    return {
        "mean": sum(finite) / len(finite) if finite else None,
        "minimum": min(finite) if finite else None,
        "maximum": max(finite) if finite else None,
        "valid_rows": len(finite),
        "scheduled_rows": scheduled,
    }


def _cell_summary(
    rows: Sequence[Mapping[str, Any]],
    *,
    N: int,
    p: int,
    focal_context: str,
    condition: str,
    arm: str,
    scheduled: int,
) -> dict[str, Any]:
    fragility_complete = [row for row in rows if row["fragility_status"] != "error"]
    reached_rows = [row for row in rows if row["fragility_status"] == "reached"]
    certified_rows = [row for row in reached_rows if row["certification_status"] == "certified"]
    clean_rows = list(rows) if condition == "clean" else []
    clean_valid = [row for row in clean_rows if row["reference_tail_probability"] is not None]
    contaminated = list(rows) if condition != "clean" else []
    influence_valid = [
        row for row in contaminated
        if row["influence_top_k_precision"] is not None
        and row["influence_top_k_recall"] is not None
    ]
    metrics = {
        "reached_rate": _proportion(len(reached_rows), len(fragility_complete)),
        "fragility_stage_failure_rate": _proportion(sum(row["fragility_status"] == "error" for row in rows), scheduled),
        "certification_rate_given_reach": _proportion(len(certified_rows), len(reached_rows)),
        "certified_yield": _proportion(len(certified_rows), scheduled),
        "budget_exhaustion_rate_given_reach": _proportion(sum(row["certification_budget_exhausted"] is True for row in reached_rows), len(reached_rows)),
        "clean_false_flag_rate": _proportion(sum(row["reference_tail_probability"] <= 0.05 for row in clean_valid), len(clean_valid)),
        "influence_top_k_precision": _mean_metric([row["influence_top_k_precision"] for row in influence_valid], scheduled if condition != "clean" else 0),
        "influence_top_k_recall": _mean_metric([row["influence_top_k_recall"] for row in influence_valid], scheduled if condition != "clean" else 0),
    }
    result = {
        "N": N,
        "p": p,
        "focal_context": focal_context,
        "condition": condition,
        "arm": arm,
        "scheduled_rows": scheduled,
        "available_rows": len(rows),
        "replication_count": len({row["replication"] for row in rows}),
        **metrics,
        "shrinkage": _numeric_range([row["lambda"] for row in rows], scheduled),
        "condition_number": _numeric_range([row["condition_number"] for row in rows], scheduled),
        "clean_invalid_reference_rows": len(clean_rows) - len(clean_valid) if condition == "clean" else 0,
        "unreached_rows": sum(row["fragility_status"] == "unreached" for row in rows),
        "fragility_error_rows": sum(row["fragility_status"] == "error" for row in rows),
        "certification_error_rows": sum(row["certification_status"] == "error" for row in rows),
        "uncertified_rows": sum(row["certification_status"] == "not_certified" for row in rows),
        "certification_budget_exhausted_rows": sum(row["certification_budget_exhausted"] is True for row in rows),
        "workflow_status_counts": dict(sorted(Counter(row["workflow_status"] for row in rows).items())),
        "elapsed_seconds": _mean_metric([row["elapsed_seconds"] for row in rows], scheduled),
    }
    return result


def compare_localized_network_rerun(
    primary_shard_dirs: Sequence[str | Path],
    rerun_shard_dirs: Sequence[str | Path],
    config_path: str | Path,
) -> dict[str, Any]:
    """Compare deterministic row fields from two complete matched runs."""
    manifest = load_localized_manifest(config_path)
    expected_by_key = {
        (job["arm"], job["N"], job["p"], job["focal_context"], job["condition"], job["replication"]): job
        for job in expand_localized_jobs(manifest)
    }
    primary_paths = {Path(path).resolve() for path in primary_shard_dirs}
    rerun_paths = {Path(path).resolve() for path in rerun_shard_dirs}
    if not primary_paths or not rerun_paths or primary_paths & rerun_paths:
        return {
            "status": "invalid", "compared_rows": 0, "mismatch_count": 0,
            "mismatches": [], "issues": ["two distinct, nonempty shard sets are required"],
        }

    def load_run(
        paths: Sequence[str | Path], label: str
    ) -> tuple[dict[tuple[Any, ...], dict[str, Any]], list[dict[str, Any]], list[str]]:
        row_map: dict[tuple[Any, ...], dict[str, Any]] = {}
        metadata_records: list[dict[str, Any]] = []
        issues: list[str] = []
        observed_p: set[int] = set()
        for path in paths:
            try:
                p, rows, metadata, issue = _load_shard(Path(path), manifest, expected_by_key)
            except (ValueError, OSError) as error:
                issues.append(f"{label}: {error}")
                continue
            if p in observed_p:
                issues.append(f"{label}: duplicate p={p} shard")
                continue
            observed_p.add(p)
            if issue:
                issues.append(f"{label} p={p}: {issue}")
            metadata_records.append(metadata)
            for row in rows:
                key = tuple(row[field] for field in _ROW_KEY_FIELDS)
                if key in row_map:
                    issues.append(f"{label}: duplicate row key {key}")
                row_map[key] = row
        if observed_p != set(manifest["p_values"]):
            issues.append(f"{label}: expected p shards {manifest['p_values']}, observed {sorted(observed_p)}")
        if len(row_map) != manifest["expected_rows"]:
            issues.append(f"{label}: expected {manifest['expected_rows']} valid unique rows, found {len(row_map)}")
        provenance_fields = (
            "git_commit", "package_version", "python_version", "numpy_version", "manifest_checksum"
        )
        identities = {
            tuple(metadata.get(field) for field in provenance_fields)
            for metadata in metadata_records
        }
        if len(identities) != 1:
            issues.append(f"{label}: shard provenance is incomplete or inconsistent")
        return row_map, metadata_records, issues

    primary_rows, primary_metadata, primary_issues = load_run(primary_shard_dirs, "primary")
    rerun_rows, rerun_metadata, rerun_issues = load_run(rerun_shard_dirs, "matched rerun")
    issues = [*primary_issues, *rerun_issues]
    if not issues:
        provenance_fields = (
            "git_commit", "package_version", "python_version", "numpy_version", "manifest_checksum"
        )
        primary_provenance = tuple(primary_metadata[0].get(field) for field in provenance_fields)
        rerun_provenance = tuple(rerun_metadata[0].get(field) for field in provenance_fields)
        if primary_provenance != rerun_provenance:
            issues.append("matched runs differ in Git, software, or manifest provenance")
    mismatches: list[dict[str, Any]] = []
    mismatch_count = 0
    if not issues:
        deterministic_fields = [field for field in FIELDNAMES if field != "elapsed_seconds"]
        for key in sorted(primary_rows):
            left, right = primary_rows[key], rerun_rows.get(key)
            if right is None:
                mismatch_count += 1
                if len(mismatches) < 100:
                    mismatches.append({"row_key": list(key), "field": "missing_row"})
                continue
            for field in deterministic_fields:
                if left[field] != right[field]:
                    mismatch_count += 1
                    if len(mismatches) < 100:
                        mismatches.append({"row_key": list(key), "field": field})
    return {
        "status": "invalid" if issues else ("matched" if mismatch_count == 0 else "mismatch"),
        "compared_rows": len(primary_rows) if not issues else 0,
        "mismatch_count": mismatch_count,
        "mismatches": mismatches,
        "issues": issues,
        "excluded_from_comparison": ["elapsed_seconds"],
    }


def _markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Task 27 localized-network operating-envelope summary",
        "",
        f"Acceptance status: **{report['acceptance_status']}**",
        f"Valid rows: {report['valid_rows']} / {report['expected_rows']}",
        f"Available rows: {report['available_rows']}",
        "",
        "Cap 2 is the primary operating workflow; cap 4 is diagnostic sensitivity evidence.",
        "Incomplete shards and invalid rows are retained in the acceptance accounting.",
        f"Matched rerun: {report['matched_rerun']['status']} ({report['matched_rerun']['compared_rows']} rows; elapsed_seconds excluded).",
        "",
        "## Cell summaries",
        "",
        "| N | p | Context | Condition | Arm | Scheduled | Reached | Certified | Clean false flags | Shrinkage mean (valid/scheduled) | Condition number mean [min, max] (valid/scheduled) |",
        "|---:|---:|---|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for cell in report["cells"]:
        reached, certified, false_flags = (cell[name] for name in ("reached_rate", "certified_yield", "clean_false_flag_rate"))
        shrinkage = cell["shrinkage"]
        condition_number = cell["condition_number"]
        lines.append(
            f"| {cell['N']} | {cell['p']} | {cell['focal_context']} | {cell['condition']} | {cell['arm']} | "
            f"{cell['scheduled_rows']} | {reached['numerator']}/{reached['denominator']} | "
            f"{certified['numerator']}/{certified['denominator']} | {false_flags['numerator']}/{false_flags['denominator']} | "
            f"{shrinkage['mean']} ({shrinkage['valid_rows']}/{shrinkage['scheduled_rows']}) | "
            f"{condition_number['mean']} [{condition_number['minimum']}, {condition_number['maximum']}] "
            f"({condition_number['valid_rows']}/{condition_number['scheduled_rows']}) |"
        )
    lines.extend(["", "## Shard issues", ""])
    lines.extend(f"- p={item['p']}: {item['reason']}" for item in report["shard_issues"])
    if not report["shard_issues"]:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def summarize_localized_network(
    shard_dirs: Sequence[str | Path],
    config_path: str | Path,
    output_dir: str | Path,
    validate: bool = True,
    matched_rerun_shard_dirs: Sequence[str | Path] | None = None,
) -> dict[str, Any]:
    """Validate shard artifacts and write aggregate JSON and Markdown summaries."""
    manifest = load_localized_manifest(config_path)
    jobs = expand_localized_jobs(manifest)
    expected_by_key = {
        (job["arm"], job["N"], job["p"], job["focal_context"], job["condition"], job["replication"]): job
        for job in jobs
    }
    rows: list[dict[str, Any]] = []
    shard_issues: list[dict[str, Any]] = []
    metadata_records: list[dict[str, Any]] = []
    observed_p: set[int] = set()
    for shard_value in shard_dirs:
        directory = Path(shard_value)
        try:
            p, shard_rows, metadata, issue = _load_shard(directory, manifest, expected_by_key)
        except ValueError as error:
            # Preserve the failure boundary even when status provenance is unusable.
            shard_issues.append({"p": None, "directory": str(directory), "reason": str(error)})
            continue
        if p in observed_p:
            shard_issues.append({"p": p, "directory": str(directory), "reason": "duplicate p shard"})
            continue
        observed_p.add(p)
        rows.extend(shard_rows)
        if metadata:
            metadata_records.append(metadata)
        if issue:
            shard_issues.append({"p": p, "directory": str(directory), "reason": issue})
    for p in manifest["p_values"]:
        if p not in observed_p:
            shard_issues.append({"p": p, "directory": None, "reason": "missing p shard"})
    provenance_fields = (
        "git_commit", "python_version", "numpy_version", "package_version", "manifest_checksum"
    )
    provenance_identities = {
        tuple(metadata.get(field) for field in provenance_fields)
        for metadata in metadata_records
    }
    if len(provenance_identities) > 1:
        shard_issues.append({
            "p": None,
            "directory": None,
            "reason": "shard provenance differs across Git commit or software versions",
        })
    counts = Counter((row["arm"], row["N"], row["p"], row["focal_context"], row["condition"], row["replication"]) for row in rows)
    expected_keys = set(expected_by_key)
    observed_keys = set(counts)
    missing_keys = len(expected_keys - observed_keys)
    duplicate_rows = sum(metadata.get("_duplicate_rows", 0) for metadata in metadata_records)
    duplicate_rows += sum(count - 1 for count in counts.values() if count > 1)
    if missing_keys:
        shard_issues.append({"p": None, "directory": None, "reason": f"{missing_keys} expected arm/pairing rows are missing"})
    if duplicate_rows:
        shard_issues.append({"p": None, "directory": None, "reason": f"{duplicate_rows} duplicate arm/pairing rows are present"})
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["N"], row["p"], row["focal_context"], row["condition"], row["arm"])].append(row)
    scheduled_by_cell: Counter[tuple[Any, ...]] = Counter(
        (job["N"], job["p"], job["focal_context"], job["condition"], job["arm"])
        for job in jobs
    )
    cells = [
        _cell_summary(
            groups[key],
            N=key[0],
            p=key[1],
            focal_context=key[2],
            condition=key[3],
            arm=key[4],
            scheduled=scheduled_by_cell[key],
        )
        for key in sorted(scheduled_by_cell)
    ]
    matrix_complete = (
        len(rows) == manifest["expected_rows"]
        and len(observed_keys) == manifest["expected_rows"]
        and not shard_issues
        and len(observed_p) == len(manifest["p_values"])
    )
    matched_rerun = (
        compare_localized_network_rerun(shard_dirs, matched_rerun_shard_dirs, config_path)
        if matched_rerun_shard_dirs is not None
        else {
            "status": "not_provided", "compared_rows": 0, "mismatch_count": 0,
            "mismatches": [], "issues": [],
        }
    )
    complete = matrix_complete and matched_rerun["status"] == "matched"
    report: dict[str, Any] = {
        "schema_version": 2,
        "study": manifest["study"],
        "acceptance_status": (
            "complete" if complete else
            "awaiting_matched_rerun" if matrix_complete and matched_rerun["status"] == "not_provided" else
            "incomplete"
        ),
        "matched_rerun": matched_rerun,
        "expected_rows": manifest["expected_rows"],
        "expected_pairing_keys": manifest["expected_pairing_keys"],
        "valid_rows": len(rows),
        "available_rows": len(rows),
        "expected_shards": list(manifest["p_values"]),
        "observed_shards": sorted(observed_p),
        "incomplete_shards": sorted({item["p"] for item in shard_issues if item["p"] is not None}),
        "missing_arm_pairing_rows": missing_keys,
        "duplicate_arm_pairing_rows": duplicate_rows,
        "shard_issues": shard_issues,
        "cells": cells,
        "provenance": {
            "manifest_checksum": localized_manifest_checksum(manifest),
            "shards": [
                {key: metadata.get(key) for key in ("p_shard", "git_commit", "python_version", "numpy_version", "package_version")}
                for metadata in metadata_records
            ],
        },
        "shard_status_counts": dict(sorted(Counter(
            metadata.get("_shard_status", "invalid") for metadata in metadata_records
        ).items())),
        "overall": {
            "elapsed_seconds": _mean_metric([row["elapsed_seconds"] for row in rows], len(rows)),
            "workflow_status_counts": dict(sorted(Counter(row["workflow_status"] for row in rows).items())),
            "fragility_status_counts": dict(sorted(Counter(row["fragility_status"] for row in rows).items())),
            "certification_status_counts": dict(sorted(Counter(row["certification_status"] for row in rows).items())),
            "certification_budget_exhausted_rows": sum(row["certification_budget_exhausted"] is True for row in rows),
        },
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "summary.json"
    markdown_path = output / "summary.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    if validate:
        decoded = json.loads(json_path.read_text(encoding="utf-8"))
        if decoded != report or not markdown_path.is_file():
            raise ValueError("written summary artifacts failed their read-back check")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--shard", type=Path, action="append", required=True, dest="shard_dirs")
    parser.add_argument("--matched-rerun-shard", type=Path, action="append", dest="matched_rerun_shard_dirs")
    parser.add_argument("--no-validate", action="store_false", dest="validate")
    parser.set_defaults(validate=True)
    args = parser.parse_args()
    report = summarize_localized_network(
        args.shard_dirs,
        args.config,
        args.output_dir,
        validate=args.validate,
        matched_rerun_shard_dirs=args.matched_rerun_shard_dirs,
    )
    print(json.dumps({key: report[key] for key in ("acceptance_status", "valid_rows", "expected_rows", "incomplete_shards", "matched_rerun")}, sort_keys=True))
    if report["acceptance_status"] == "incomplete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
