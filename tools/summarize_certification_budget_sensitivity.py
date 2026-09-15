"""Validate, summarize, and aggregate Task 26 budget-sensitivity evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.cap_expansion_manifest import PAIRING_FIELDS
from tools.certification_budget_sensitivity_manifest import (
    certification_budget_sensitivity_manifest_checksum,
    load_certification_budget_sensitivity_manifest,
)
from tools.prepare_certification_budget_sensitivity import load_selection_manifest
from tools.run_certification_budget_sensitivity import SENSITIVITY_FIELDNAMES
from tools.summarize_certification_usability import (
    _validate_diagnostic_row,
    compare_instrumented_rows_to_reference,
)

__all__ = [
    "aggregate_certification_budget_arms",
    "summarize_certification_budget_arm",
    "validate_certification_budget_arm",
]

_CAP_NAMES = ("cap3", "cap4")
_DOWNSTREAM_STATUS_FIELDS = (
    "calibration_status",
    "wald_status",
    "bootstrap_status",
    "workflow_status",
)
_BUDGET_DEPENDENT_SOURCE_FIELDS = {
    "exact_fragility_50",
    "certified",
    "certification_status",
}
_SEED_FIELDS = ("data_seed", "calibration_seed", "bootstrap_seed")
_STATUS_FIELDS = {
    "schema_version",
    "study",
    "arm_status",
    "budget",
    "expected_rows",
    "rows",
    "completed_rows",
    "arm_rows",
    "observed_cap_rows",
    "certification_budget_exhausted_rows",
    "completed_keys",
    "last_completed_key",
    "elapsed_seconds",
    "runtime_ceiling_seconds",
    "started_at",
    "finished_at",
    "source_checksums",
    "environment",
    "error_type",
    "error_message",
    "artifact_checksums",
}


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _read_json(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    return value


def _read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("arm CSV is missing a header")
        rows = list(reader)
    for line_number, row in enumerate(rows, start=2):
        if None in row:
            raise ValueError(f"arm CSV row {line_number} has extra cells")
        if any(value is None for value in row.values()):
            raise ValueError(f"arm CSV row {line_number} has missing cells")
    return list(reader.fieldnames), rows


def _optional_bool(value: object) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if value == "True":
        return True
    if value == "False":
        return False
    raise ValueError(f"value is not boolean: {value!r}")


def _required_nonnegative_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise TypeError(f"{field} must be a nonnegative integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be a nonnegative integer") from error
    if parsed < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return parsed


def _required_exact_nonnegative_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{field} must be a nonnegative integer")
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be a nonnegative integer") from error
    if parsed < 0 or str(value).strip() != str(parsed):
        raise ValueError(f"{field} must be a nonnegative integer")
    return parsed


def _required_finite_float(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise TypeError(f"{field} must be finite")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be finite") from error
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError(f"{field} must be finite and nonnegative")
    return parsed


def _validate_certification_outcome(row: Mapping[str, Any]) -> None:
    reason = str(row.get("certification_failure_reason", ""))
    expected = {
        "certified": ("certified", True, True),
        "combination_budget_exhausted": ("not_certified", False, False),
        "not_certified_other": ("not_certified", False, False),
        "error": ("error", None, False),
        "not_applicable_prior_error": ("error", None, False),
        "not_applicable_unreached": ("skipped_unreached", None, False),
    }.get(reason)
    if expected is None:
        return

    expected_status, expected_certified, exact_required = expected
    status = str(row.get("certification_status", ""))
    try:
        certified = _optional_bool(row.get("certified"))
    except ValueError as error:
        raise ValueError("certification outcome has an invalid certified value") from error
    exact_value = row.get("exact_fragility_50")
    exact_is_empty = exact_value in (None, "")
    if status != expected_status or certified is not expected_certified:
        raise ValueError("certification outcome does not agree with its status and reason")
    if exact_required:
        try:
            exact_minimum = _required_exact_nonnegative_int(exact_value, "exact_fragility_50")
            greedy_upper_bound = _required_exact_nonnegative_int(
                row.get("greedy_fragility_50"), "greedy_fragility_50"
            )
        except ValueError as error:
            raise ValueError(
                "certification outcome requires integer exact and greedy fragility values"
            ) from error
        if not 1 <= exact_minimum <= greedy_upper_bound:
            raise ValueError(
                "certification outcome exact_fragility_50 must be between 1 and greedy_fragility_50"
            )
    elif not exact_is_empty:
        raise ValueError("certification outcome requires exact_fragility_50 to be null")


def _pair_key(row: Mapping[str, Any]) -> tuple[str, int, int, int, int]:
    try:
        return (
            str(row["scenario"]),
            int(row["N"]),
            int(row["p"]),
            int(row["parameter_id"]),
            int(row["replication"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("row has invalid pairing key") from error


def _full_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (str(row.get("arm", "")), *_pair_key(row))


def _json_pair_key(row: Mapping[str, Any]) -> dict[str, Any]:
    key = _pair_key(row)
    return {field: value for field, value in zip(PAIRING_FIELDS, key, strict=True)}


def _completed_key(row: Mapping[str, Any]) -> dict[str, Any]:
    return {"arm": str(row["arm"]), **_json_pair_key(row)}


def _selected_candidates(selection: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(entry["candidate"]) for cap in _CAP_NAMES for entry in selection["populations"][cap]
    ]


def _counter(values: Sequence[object]) -> dict[str, int]:
    return dict(Counter(str(value) for value in values))


def _combination_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = [
        _required_nonnegative_int(
            row.get("certification_combinations_checked"),
            "certification_combinations_checked",
        )
        for row in rows
        if row.get("certification_combinations_checked") not in (None, "")
    ]
    return {
        "rows": len(values),
        "total": sum(values),
        "minimum": min(values) if values else None,
        "maximum": max(values) if values else None,
    }


def _population_summary(
    rows: Sequence[Mapping[str, Any]],
    expected_rows: int,
    arm_complete: bool,
) -> dict[str, Any]:
    certified_rows = sum(str(row.get("certification_status", "")) == "certified" for row in rows)
    return {
        "rows": len(rows),
        "expected_rows": expected_rows,
        "certified_rows": certified_rows,
        "certification_yield": (
            certified_rows / expected_rows if arm_complete and expected_rows else None
        ),
        "yield_status": ("available" if arm_complete else "unavailable_incomplete_arm"),
        "certification_status_counts": _counter(
            [row.get("certification_status", "") for row in rows]
        ),
        "reason_counts": _counter([row.get("certification_failure_reason", "") for row in rows]),
        "budget_exhausted_rows": sum(
            _optional_bool(row.get("certification_budget_exhausted")) is True for row in rows
        ),
        "combination_counts": _combination_counts(rows),
        "downstream_status_counts": {
            field: _counter([row.get(field, "") for row in rows])
            for field in _DOWNSTREAM_STATUS_FIELDS
        },
        "error_stage_counts": _counter([row.get("error_stage", "") or "none" for row in rows]),
        "pair_keys": [_json_pair_key(row) for row in rows],
    }


def summarize_certification_budget_arm(
    rows: Sequence[Mapping[str, Any]],
    selection: Mapping[str, Any],
    study_manifest: Mapping[str, Any],
    arm_status: Mapping[str, Any],
) -> dict[str, Any]:
    """Summarize observed rows without scoring an incomplete arm as zero yield."""
    status = str(arm_status.get("arm_status", ""))
    arm_complete = status == "complete" and len(rows) == int(
        study_manifest["expected_rows_per_budget"]
    )
    by_cap = {cap: [row for row in rows if str(row.get("arm", "")) == cap] for cap in _CAP_NAMES}
    return {
        "schema_version": study_manifest["output_schema_version"],
        "study": study_manifest["study"],
        "budget": arm_status.get("budget"),
        "arm_status": status,
        "complete": arm_complete,
        "rows": len(rows),
        "expected_rows": int(study_manifest["expected_rows_per_budget"]),
        "populations": {
            cap: _population_summary(
                by_cap[cap],
                int(selection["expected_population_rows"][cap]),
                arm_complete,
            )
            for cap in _CAP_NAMES
        },
    }


def _expected_source_checksums(
    study_manifest: Mapping[str, Any], selection: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "study_manifest": certification_budget_sensitivity_manifest_checksum(study_manifest),
        "selection_manifest": selection["selection_checksum"],
        "source_manifest": study_manifest["source_task24_manifest_checksum"],
        "source_task25_results": study_manifest["source_task25_results_sha256"],
        "source_task25_manifest": study_manifest["source_task25_manifest_checksum"],
        "source_task24_results": study_manifest["source_task24_results_sha256"],
        "source_task24_manifest": study_manifest["source_task24_manifest_checksum"],
    }


def _validate_status_schema(status: Mapping[str, Any], label: str) -> None:
    if set(status) != _STATUS_FIELDS:
        raise ValueError(f"{label} fields do not match the Task 2 output schema")
    if set(status["environment"]) != {
        "git_commit",
        "python_version",
        "numpy_version",
        "package_version",
        "platform",
    }:
        raise ValueError(f"{label} environment fields do not match the Task 2 schema")


def _validate_status_and_artifacts(
    arm_path: Path,
    rows: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any],
    status: Mapping[str, Any],
    selection: Mapping[str, Any],
    study_manifest: Mapping[str, Any],
) -> tuple[int, str]:
    _validate_status_schema(metadata, "results metadata")
    _validate_status_schema(status, "arm status")
    metadata_core = {key: value for key, value in metadata.items() if key != "artifact_checksums"}
    status_core = {key: value for key, value in status.items() if key != "artifact_checksums"}
    if metadata_core != status_core:
        raise ValueError("arm status does not agree with results metadata")

    results_path = arm_path / "results.csv"
    metadata_path = arm_path / "results.metadata.json"
    results_checksum = _sha256_file(results_path)
    metadata_checksum = _sha256_file(metadata_path)
    if metadata["artifact_checksums"] != {"results.csv": results_checksum}:
        raise ValueError("results metadata artifact checksum does not match")
    if status["artifact_checksums"] != {
        "results.csv": results_checksum,
        "results.metadata.json": metadata_checksum,
    }:
        raise ValueError("arm status artifact checksum does not match")

    if status["schema_version"] != study_manifest["output_schema_version"]:
        raise ValueError("arm status schema version does not match")
    if status["study"] != study_manifest["study"]:
        raise ValueError("arm status study does not match")
    arm_status = str(status["arm_status"])
    if arm_status not in {"complete", "timeout", "failed", "incomplete"}:
        raise ValueError("arm status value is invalid")
    budget = _required_nonnegative_int(status["budget"], "arm budget")
    if budget not in study_manifest["budget_grid"]:
        raise ValueError("arm budget is not declared by the study manifest")
    expected_rows = int(study_manifest["expected_rows_per_budget"])
    if status["expected_rows"] != expected_rows:
        raise ValueError("arm expected row count does not match the study manifest")
    if status["rows"] != len(rows) or status["completed_rows"] != len(rows):
        raise ValueError("arm status row count does not match results")

    cap_counts = Counter(str(row.get("arm", "")) for row in rows)
    observed_cap_rows = {cap: cap_counts[cap] for cap in _CAP_NAMES}
    if status["arm_rows"] != observed_cap_rows:
        raise ValueError("arm status cap row counts do not match results")
    if status["observed_cap_rows"] != observed_cap_rows:
        raise ValueError("arm status observed cap row counts do not match results")
    exhausted_rows = sum(
        _optional_bool(row.get("certification_budget_exhausted")) is True for row in rows
    )
    if status["certification_budget_exhausted_rows"] != exhausted_rows:
        raise ValueError("arm status budget-exhaustion count does not match results")

    completed_keys = [_completed_key(row) for row in rows]
    if status["completed_keys"] != completed_keys:
        raise ValueError("arm status completed pairing keys do not match results")
    expected_last = completed_keys[-1] if completed_keys else None
    if status["last_completed_key"] != expected_last:
        raise ValueError("arm status last completed pairing key does not match results")
    _required_finite_float(status["elapsed_seconds"], "arm elapsed_seconds")
    if float(status["runtime_ceiling_seconds"]) != float(study_manifest["runtime_ceiling_seconds"]):
        raise ValueError("arm runtime ceiling does not match the study manifest")
    if status["source_checksums"] != _expected_source_checksums(study_manifest, selection):
        raise ValueError("arm source checksums do not match the study inputs")

    expected_cap_rows = dict(study_manifest["expected_population_rows"])
    if arm_status == "complete":
        if len(rows) != expected_rows:
            raise ValueError("complete arm row count does not match expected rows")
        if observed_cap_rows != expected_cap_rows:
            raise ValueError("complete arm cap row counts do not match expected populations")
    elif len(rows) > expected_rows:
        raise ValueError("non-complete arm cannot exceed the expected row count")
    return budget, arm_status


def _validate_rows_against_selection(
    rows: Sequence[Mapping[str, Any]],
    selection: Mapping[str, Any],
    study_manifest: Mapping[str, Any],
    budget: int,
) -> None:
    expected = _selected_candidates(selection)
    observed_keys = [_full_key(row) for row in rows]
    expected_keys = [_full_key(row) for row in expected]
    if observed_keys != expected_keys[: len(rows)]:
        raise ValueError("arm rows do not match the canonical selected pairing-key prefix")

    allowed_reasons = set(study_manifest["reason_values"])
    for row in rows:
        _validate_diagnostic_row(row, allowed_reasons, budget)
        _validate_certification_outcome(row)

    references_by_key = {_full_key(row): row for row in expected}
    references = [references_by_key[key] for key in observed_keys]
    comparison_rows = [dict(row) for row in rows]
    for row, reference in zip(comparison_rows, references, strict=True):
        for field in _SEED_FIELDS:
            observed_seed = _required_exact_nonnegative_int(row.get(field), field)
            reference_seed = _required_exact_nonnegative_int(reference.get(field), field)
            if observed_seed != reference_seed:
                raise ValueError(f"{field} differs for {_full_key(row)}")
        for field in _BUDGET_DEPENDENT_SOURCE_FIELDS:
            row[field] = reference.get(field)
    compare_instrumented_rows_to_reference(comparison_rows, references)


def _success_report(
    arm_path: Path,
    rows: Sequence[Mapping[str, Any]],
    status: Mapping[str, Any],
    selection: Mapping[str, Any],
    study_manifest: Mapping[str, Any],
    budget: int,
    arm_status: str,
) -> dict[str, Any]:
    summary = summarize_certification_budget_arm(rows, selection, study_manifest, status)
    return {
        "schema_version": study_manifest["output_schema_version"],
        "study": study_manifest["study"],
        "valid": True,
        "complete": arm_status == "complete",
        "arm_status": arm_status,
        "budget": budget,
        "expected_rows": int(study_manifest["expected_rows_per_budget"]),
        "rows": len(rows),
        "observed_cap_rows": dict(status["observed_cap_rows"]),
        "source_task25": dict(selection["source_task25"]),
        "source_task24": dict(selection["source_task24"]),
        "source_checksums": dict(status["source_checksums"]),
        "artifact_checksums": dict(status["artifact_checksums"]),
        "elapsed_seconds": status["elapsed_seconds"],
        "error_type": None,
        "error_message": None,
        "arm_dir": str(arm_path),
        "summary": summary,
    }


def _failure_context(arm_path: Path) -> dict[str, Any]:
    budget: Any = None
    arm_status: Any = "invalid"
    rows = 0
    observed_cap_rows = {cap: 0 for cap in _CAP_NAMES}
    source_checksums: Any = None
    status_path = arm_path / "arm_status.json"
    results_path = arm_path / "results.csv"
    try:
        status = _read_json(status_path, "arm status")
        budget = status.get("budget")
        arm_status = status.get("arm_status", "invalid")
        rows = status.get("rows", 0)
        source_checksums = status.get("source_checksums")
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        try:
            budget = int(arm_path.name)
        except ValueError:
            budget = None
    try:
        _, observed = _read_rows(results_path)
        rows = len(observed)
        counts = Counter(str(row.get("arm", "")) for row in observed)
        observed_cap_rows = {cap: counts[cap] for cap in _CAP_NAMES}
    except (OSError, ValueError):
        pass
    return {
        "budget": budget,
        "arm_status": arm_status,
        "rows": rows,
        "observed_cap_rows": observed_cap_rows,
        "source_checksums": source_checksums,
    }


def validate_certification_budget_arm(
    arm_dir: str | Path,
    selection_manifest_path: str | Path,
    study_manifest_path: str | Path,
) -> dict[str, Any]:
    """Validate one arm and always persist a machine-readable report."""
    arm_path = Path(arm_dir)
    arm_path.mkdir(parents=True, exist_ok=True)
    study_manifest: dict[str, Any] | None = None
    selection: dict[str, Any] | None = None
    try:
        study_manifest = load_certification_budget_sensitivity_manifest(study_manifest_path)
        selection = load_selection_manifest(selection_manifest_path, study_manifest)
        fields, rows = _read_rows(arm_path / "results.csv")
        if fields != SENSITIVITY_FIELDNAMES:
            raise ValueError("arm CSV fields do not match SENSITIVITY_FIELDNAMES in order")
        metadata = _read_json(arm_path / "results.metadata.json", "results metadata")
        status = _read_json(arm_path / "arm_status.json", "arm status")
        budget, arm_status = _validate_status_and_artifacts(
            arm_path, rows, metadata, status, selection, study_manifest
        )
        _validate_rows_against_selection(rows, selection, study_manifest, budget)
        report = _success_report(
            arm_path,
            rows,
            status,
            selection,
            study_manifest,
            budget,
            arm_status,
        )
    except Exception as error:  # noqa: BLE001 - the report is the validation boundary
        context = _failure_context(arm_path)
        report = {
            "schema_version": (
                study_manifest["output_schema_version"] if study_manifest is not None else 1
            ),
            "study": "certification_budget_sensitivity",
            "valid": False,
            "complete": False,
            **context,
            "expected_rows": (
                study_manifest["expected_rows_per_budget"] if study_manifest is not None else None
            ),
            "source_task25": (dict(selection["source_task25"]) if selection is not None else None),
            "source_task24": (dict(selection["source_task24"]) if selection is not None else None),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "arm_dir": str(arm_path),
        }
    _write_json(arm_path / "arm_validation.json", report)
    return report


def _aggregate_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        int(row["certification_combination_budget"]),
        int(row["search_cap"]),
        int(row["N"]),
        int(row["p"]),
        str(row["scenario"]),
        int(row["parameter_id"]),
        int(row["replication"]),
    )


def _write_combined_results(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SENSITIVITY_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Certification-budget sensitivity summary",
        "",
        "- cap-3 and cap-4 denominators are separate and may overlap; overlap is retained in both selected populations.",
        "- incomplete arms are not zero-yield evidence.",
        "- row-level budget exhaustion differs from arm timeout.",
        "- cap 2 remains the production baseline.",
        "- any yield change is evidence only for the specified selected population and budget, not a cap-promotion or production-budget decision.",
        "",
        "## Per-cap, per-budget endpoints",
        "",
        "| Budget | Cap | Arm status | Rows | Expected | Certified | Yield | Budget exhausted | Runtime (s) |",
        "| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for budget in summary["budget_grid"]:
        status = summary["arm_statuses"][str(budget)]
        for cap in _CAP_NAMES:
            endpoint = summary["per_cap_per_budget"][cap][str(budget)]
            if endpoint is None:
                lines.append(
                    f"| {budget} | {cap[-1]} | {status['arm_status']} | 0 | "
                    f"{summary['expected_population_rows'][cap]} | 0 | unavailable | 0 | unavailable |"
                )
                continue
            yield_value = (
                endpoint["certification_yield"]
                if endpoint["certification_yield"] is not None
                else "unavailable"
            )
            runtime = status.get("elapsed_seconds")
            lines.append(
                f"| {budget} | {cap[-1]} | {status['arm_status']} | "
                f"{endpoint['rows']} | {endpoint['expected_rows']} | "
                f"{endpoint['certified_rows']} | {yield_value} | "
                f"{endpoint['budget_exhausted_rows']} | "
                f"{runtime if runtime is not None else 'unavailable'} |"
            )
    lines.extend(
        [
            "",
            f"Complete sensitivity result: `{str(summary['complete_sensitivity_result']).lower()}`.",
            "",
        ]
    )
    return "\n".join(lines)


def aggregate_certification_budget_arms(
    arm_dirs: Mapping[int, str | Path],
    selection_manifest_path: str | Path,
    study_manifest_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Validate available arms and write a complete or diagnostic aggregate."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    study_manifest = load_certification_budget_sensitivity_manifest(study_manifest_path)
    selection = load_selection_manifest(selection_manifest_path, study_manifest)
    _write_json(output_path / "selection_manifest.json", selection)

    combined_rows: list[dict[str, str]] = []
    arm_statuses: dict[str, dict[str, Any]] = {}
    per_cap_per_budget: dict[str, dict[str, Any]] = {cap: {} for cap in _CAP_NAMES}
    reports: dict[str, dict[str, Any]] = {}
    all_present = True
    for budget in study_manifest["budget_grid"]:
        key = str(budget)
        arm_dir = arm_dirs.get(int(budget))
        if arm_dir is None or not Path(arm_dir).is_dir():
            all_present = False
            missing = {
                "schema_version": study_manifest["output_schema_version"],
                "study": study_manifest["study"],
                "arm_status": "missing",
                "budget": budget,
                "valid": False,
                "complete": False,
                "expected_rows": int(study_manifest["expected_rows_per_budget"]),
                "rows": 0,
                "observed_cap_rows": {cap: 0 for cap in _CAP_NAMES},
                "elapsed_seconds": None,
                "error_type": "FileNotFoundError",
                "error_message": f"budget arm directory is missing for {budget}",
            }
            arm_statuses[key] = missing
            reports[key] = missing
            for cap in _CAP_NAMES:
                per_cap_per_budget[cap][key] = None
            _write_json(output_path / f"arm_status_{budget}.json", missing)
            continue

        arm_path = Path(arm_dir)
        report = validate_certification_budget_arm(
            arm_path, selection_manifest_path, study_manifest_path
        )
        budget_matches_slot = report.get("budget") == budget
        if not budget_matches_slot:
            observed_budget = report.get("budget")
            report = {
                **report,
                "valid": False,
                "complete": False,
                "error_type": "ValueError",
                "error_message": (
                    f"validated arm budget {observed_budget!r} does not match requested "
                    f"budget {budget}"
                ),
            }
        reports[key] = report
        arm_statuses[key] = {
            field: report.get(field)
            for field in (
                "arm_status",
                "valid",
                "complete",
                "rows",
                "elapsed_seconds",
                "error_type",
                "error_message",
            )
        }
        if report["valid"]:
            _, rows = _read_rows(arm_path / "results.csv")
            combined_rows.extend(rows)
            for cap in _CAP_NAMES:
                per_cap_per_budget[cap][key] = report["summary"]["populations"][cap]
        else:
            for cap in _CAP_NAMES:
                per_cap_per_budget[cap][key] = None
        status_path = arm_path / "arm_status.json"
        if not budget_matches_slot:
            copied_status = report
        elif status_path.is_file():
            try:
                copied_status = _read_json(status_path, "arm status")
            except (ValueError, TypeError, json.JSONDecodeError):
                copied_status = report
        else:
            copied_status = report
        _write_json(output_path / f"arm_status_{budget}.json", copied_status)

    combined_rows.sort(key=_aggregate_sort_key)
    results_path = output_path / "results.csv"
    _write_combined_results(results_path, combined_rows)

    expected_total_rows = int(study_manifest["expected_rows_per_budget"]) * len(
        study_manifest["budget_grid"]
    )
    all_valid = all(
        reports[str(budget)].get("valid") is True for budget in study_manifest["budget_grid"]
    )
    all_complete = all(
        reports[str(budget)].get("complete") is True for budget in study_manifest["budget_grid"]
    )
    expected_total_observed = len(combined_rows) == expected_total_rows
    complete_result = all_present and all_valid and all_complete and expected_total_observed
    runtime_by_budget = {
        str(budget): arm_statuses[str(budget)].get("elapsed_seconds")
        for budget in study_manifest["budget_grid"]
    }
    summary: dict[str, Any] = {
        "schema_version": study_manifest["output_schema_version"],
        "study": study_manifest["study"],
        "study_manifest_checksum": certification_budget_sensitivity_manifest_checksum(
            study_manifest
        ),
        "selection_manifest_checksum": selection["selection_checksum"],
        "source_task25": dict(selection["source_task25"]),
        "source_task24": dict(selection["source_task24"]),
        "candidate_caps": list(study_manifest["candidate_caps"]),
        "budget_grid": list(study_manifest["budget_grid"]),
        "expected_population_rows": dict(study_manifest["expected_population_rows"]),
        "expected_rows_per_budget": int(study_manifest["expected_rows_per_budget"]),
        "expected_total_rows": expected_total_rows,
        "observed_rows": len(combined_rows),
        "overlap_rows": selection["overlap_rows"],
        "unique_pair_keys": selection["unique_pair_keys"],
        "arm_statuses": arm_statuses,
        "per_cap_per_budget": per_cap_per_budget,
        "runtime": {
            "per_budget_seconds": runtime_by_budget,
            "total_observed_seconds": sum(
                float(value) for value in runtime_by_budget.values() if value is not None
            ),
            "runtime_ceiling_seconds_per_arm": study_manifest["runtime_ceiling_seconds"],
        },
        "reason_counts": _counter(
            [row.get("certification_failure_reason", "") for row in combined_rows]
        ),
        "validation_checks": {
            "all_budget_arms_present": all_present,
            "all_arms_valid": all_valid,
            "all_arms_complete": all_complete,
            "expected_total_rows_observed": expected_total_observed,
            "cap_populations_remain_separate": True,
        },
        "artifact_checksums": {
            "results.csv": _sha256_file(results_path),
            "selection_manifest.json": _sha256_file(output_path / "selection_manifest.json"),
            "arm_status": {
                str(budget): _sha256_file(output_path / f"arm_status_{budget}.json")
                for budget in study_manifest["budget_grid"]
            },
        },
        "complete_sensitivity_result": complete_result,
    }
    markdown_path = output_path / "summary.md"
    markdown_path.write_text(_markdown(summary), encoding="utf-8")
    summary["artifact_checksums"]["summary.md"] = _sha256_file(markdown_path)
    _write_json(output_path / "summary.json", summary)
    return summary


def _arm_dirs_from_root(arms_root: Path, budget_grid: Sequence[int]) -> dict[int, Path]:
    arm_dirs: dict[int, Path] = {}
    for budget in budget_grid:
        for candidate in (
            arms_root / str(budget),
            arms_root / f"budget-{budget}",
            arms_root / f"budget_{budget}",
        ):
            if candidate.is_dir():
                arm_dirs[int(budget)] = candidate
                break
    return arm_dirs


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("arm_dir", type=Path)
    validate_parser.add_argument("selection_manifest_path", type=Path)
    validate_parser.add_argument("study_manifest_path", type=Path)

    aggregate_parser = subparsers.add_parser("aggregate")
    aggregate_parser.add_argument("selection_manifest_path", type=Path)
    aggregate_parser.add_argument("arms_dir", type=Path)
    aggregate_parser.add_argument("study_manifest_path", type=Path)
    aggregate_parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    if args.command == "validate":
        report = validate_certification_budget_arm(
            args.arm_dir,
            args.selection_manifest_path,
            args.study_manifest_path,
        )
        raise SystemExit(0 if report["valid"] and report["complete"] else 1)

    study_manifest = load_certification_budget_sensitivity_manifest(args.study_manifest_path)
    summary = aggregate_certification_budget_arms(
        _arm_dirs_from_root(args.arms_dir, study_manifest["budget_grid"]),
        args.selection_manifest_path,
        args.study_manifest_path,
        args.output_dir,
    )
    raise SystemExit(0 if summary["complete_sensitivity_result"] else 1)


if __name__ == "__main__":
    main()
