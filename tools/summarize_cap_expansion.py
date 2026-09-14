"""Summarize and validate paired full-workflow cap-expansion artifacts."""

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
from simulations.run_simulation import replication_seeds
from simulations.summarize import summarize_rows
from tools.cap_expansion_manifest import (
    CAP_ARM_NAMES,
    PAIRING_FIELDS,
    cap_expansion_pairing_keys,
    expand_cap_expansion_jobs,
    load_cap_expansion_manifest,
    manifest_checksum,
)
from tools.run_cap_expansion import CAP_EXPANSION_FIELDNAMES

BASELINE_ARM = "baseline_cap2"
_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
STAGE_FIELDS = (
    "fragility_status",
    "certification_status",
    "calibration_status",
    "wald_status",
    "bootstrap_status",
    "workflow_status",
)
ALLOWED_STATUSES = {
    "fragility_status": {"reached", "unreached", "error"},
    "certification_status": {
        "certified",
        "not_certified",
        "skipped_unreached",
        "error",
    },
    "calibration_status": {
        "finite",
        "right_censored",
        "observed_unreached",
        "error",
    },
    "wald_status": {"ok", "error"},
    "bootstrap_status": {"ok", "error"},
    "workflow_status": {"ok", "partial", "error"},
}


def _finite_float(value: Any) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _optional_float(row: Mapping[str, Any], field: str) -> float | None:
    return _finite_float(row.get(field))


def _optional_bool(row: Mapping[str, Any], field: str) -> bool | None:
    value = row.get(field)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1"}:
            return True
        if normalized in {"false", "0"}:
            return False
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    return None


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _summary_provenance(metadata: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "git_commit": metadata["git_commit"],
        "python_version": metadata["python_version"],
        "numpy_version": metadata["numpy_version"],
        "package_version": metadata["package_version"],
        "timing": metadata["timing"],
    }


def _pairing_key(row: Mapping[str, Any]) -> tuple[Any, ...] | None:
    values = [_optional_float(row, field) for field in ("N", "p", "parameter_id", "replication")]
    scenario = row.get("scenario")
    if scenario is None or any(value is None for value in values):
        return None
    n, p, parameter_id, replication = values
    return str(scenario), int(n), int(p), int(parameter_id), int(replication)


def _status_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    return {
        field: dict(Counter(str(row.get(field, "")) for row in rows))
        for field in STAGE_FIELDS
    }


def _is_error(row: Mapping[str, Any]) -> bool:
    return any(row.get(field) == "error" for field in STAGE_FIELDS)


def _valid_fragility(row: Mapping[str, Any]) -> bool:
    return (
        row.get("fragility_status") == "reached"
        and _optional_bool(row, "reached") is True
        and _optional_float(row, "exact_fragility_50") is not None
        and _optional_float(row, "observed_rho") is not None
        and _optional_float(row, "wald_z") is not None
    )


def _pooled_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    converted = [dict(row) for row in rows]
    return {
        "rows": len(converted),
        "summary": summarize_rows(converted) if converted else None,
    }


def _reach_rate_interval(differences: Sequence[int]) -> dict[str, Any]:
    denominator = len(differences)
    if denominator == 0:
        return {
            "estimate": None,
            "lower": None,
            "upper": None,
            "denominator": 0,
            "interval_method": "normal_approximation_to_paired_indicator_difference",
        }
    estimate = sum(differences) / denominator
    variance = sum((value - estimate) ** 2 for value in differences) / max(denominator - 1, 1)
    standard_error = math.sqrt(variance / denominator)
    margin = 1.96 * standard_error
    return {
        "estimate": estimate,
        "lower": max(-1.0, estimate - margin),
        "upper": min(1.0, estimate + margin),
        "denominator": denominator,
        "interval_method": "normal_approximation_to_paired_indicator_difference",
    }


def _comparison_summary(
    baseline_rows: Sequence[Mapping[str, Any]],
    candidate_rows: Sequence[Mapping[str, Any]],
    candidate_arm: str,
) -> dict[str, Any]:
    baseline_by_key = {_pairing_key(row): row for row in baseline_rows if _pairing_key(row) is not None}
    candidate_by_key = {_pairing_key(row): row for row in candidate_rows if _pairing_key(row) is not None}
    common_keys = sorted(set(baseline_by_key) & set(candidate_by_key))
    pairs = [(baseline_by_key[key], candidate_by_key[key]) for key in common_keys]
    transition_counts = {
        "reached_to_reached": 0,
        "reached_to_unreached": 0,
        "unreached_to_reached": 0,
        "unreached_to_unreached": 0,
    }
    differences: list[int] = []
    comparable_pairs: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for baseline, candidate in pairs:
        if _is_error(baseline) or _is_error(candidate):
            continue
        baseline_reached = _optional_bool(baseline, "reached")
        candidate_reached = _optional_bool(candidate, "reached")
        if baseline_reached is None or candidate_reached is None:
            continue
        transition_counts[
            f"{'reached' if baseline_reached else 'unreached'}_to_"
            f"{'reached' if candidate_reached else 'unreached'}"
        ] += 1
        differences.append(int(candidate_reached) - int(baseline_reached))
        comparable_pairs.append((baseline, candidate))

    individually_valid_rows = [
        row for pair in pairs for row in pair if _valid_fragility(row)
    ]
    jointly_valid_pairs = [
        pair for pair in pairs if _valid_fragility(pair[0]) and _valid_fragility(pair[1])
    ]
    jointly_valid_rows = [row for pair in jointly_valid_pairs for row in pair]
    baseline_error_rows = sum(_is_error(row) for row in baseline_rows)
    candidate_error_rows = sum(_is_error(row) for row in candidate_rows)
    baseline_unreached_rows = sum(
        not _is_error(row) and _optional_bool(row, "reached") is False for row in baseline_rows
    )
    candidate_unreached_rows = sum(
        not _is_error(row) and _optional_bool(row, "reached") is False for row in candidate_rows
    )
    baseline_right_censored_rows = sum(
        not _is_error(row) and row.get("calibration_status") == "right_censored"
        for row in baseline_rows
    )
    candidate_right_censored_rows = sum(
        not _is_error(row) and row.get("calibration_status") == "right_censored"
        for row in candidate_rows
    )
    stratified: dict[str, Any] = {}
    by_cell: dict[tuple[str, int, int], list[int]] = defaultdict(list)
    for baseline, candidate in comparable_pairs:
        key = (
            str(baseline["scenario"]),
            int(float(baseline["N"])),
            int(float(baseline["p"])),
        )
        by_cell[key].append(
            int(_optional_bool(candidate, "reached"))
            - int(_optional_bool(baseline, "reached"))
        )
    for (scenario, n, p), cell_differences in sorted(by_cell.items()):
        stratified[f"{scenario}|N={n}|p={p}"] = _reach_rate_interval(cell_differences)
    return {
        "baseline_arm": BASELINE_ARM,
        "candidate_arm": candidate_arm,
        "matched_pairs": len(pairs),
        "comparable_pair_count": len(comparable_pairs),
        "baseline_error_rows": baseline_error_rows,
        "candidate_error_rows": candidate_error_rows,
        "baseline_unreached_rows": baseline_unreached_rows,
        "candidate_unreached_rows": candidate_unreached_rows,
        "baseline_right_censored_rows": baseline_right_censored_rows,
        "candidate_right_censored_rows": candidate_right_censored_rows,
        "transition_counts": transition_counts,
        "reach_rate_difference": _reach_rate_interval(differences),
        "stratified_reach_rate_differences": stratified,
        "individually_valid_fragility_rows": len(individually_valid_rows),
        "jointly_valid_pair_count": len(jointly_valid_pairs),
        "jointly_valid_fragility_rows": len(jointly_valid_rows),
        "pooled_metrics": _pooled_metrics(individually_valid_rows),
        "jointly_valid_pair_metrics": _pooled_metrics(jointly_valid_rows),
    }


def summarize_cap_expansion_rows(
    rows: Sequence[Mapping[str, Any]], manifest: Mapping[str, Any]
) -> dict[str, Any]:
    """Return pooled arm and paired cap-comparison summaries."""
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["arm"])].append(row)
    arm_summaries = {
        arm: {
            "rows": len(grouped.get(arm, [])),
            "status_counts": _status_counts(grouped.get(arm, [])),
            "endpoint_denominators": {
                "all_rows": len(grouped.get(arm, [])),
                "fragility_reached": sum(
                    row.get("fragility_status") == "reached" for row in grouped.get(arm, [])
                ),
                "certified": sum(
                    row.get("certification_status") == "certified"
                    for row in grouped.get(arm, [])
                ),
                "calibration_finite": sum(
                    row.get("calibration_status") == "finite"
                    for row in grouped.get(arm, [])
                ),
                "calibration_right_censored": sum(
                    row.get("calibration_status") == "right_censored"
                    for row in grouped.get(arm, [])
                ),
                "wald_ok": sum(
                    row.get("wald_status") == "ok" for row in grouped.get(arm, [])
                ),
                "bootstrap_ok": sum(
                    row.get("bootstrap_status") == "ok" for row in grouped.get(arm, [])
                ),
            },
            "bootstrap_rejections": {
                "denominator": sum(
                    row.get("bootstrap_status") == "ok"
                    for row in grouped.get(arm, [])
                ),
                "rows_with_rejections": sum(
                    (_optional_float(row, "bootstrap_rejected_resamples") or 0.0) > 0.0
                    for row in grouped.get(arm, [])
                    if row.get("bootstrap_status") == "ok"
                ),
                "total_rejected_resamples": int(
                    sum(
                        _optional_float(row, "bootstrap_rejected_resamples") or 0.0
                        for row in grouped.get(arm, [])
                        if row.get("bootstrap_status") == "ok"
                    )
                ),
            },
            "pooled_metrics": _pooled_metrics(grouped.get(arm, [])),
        }
        for arm in CAP_ARM_NAMES
    }
    baseline_rows = grouped.get(BASELINE_ARM, [])
    comparisons = {
        arm: _comparison_summary(baseline_rows, grouped.get(arm, []), arm)
        for arm in CAP_ARM_NAMES
        if arm != BASELINE_ARM
    }
    return {
        "rows": len(rows),
        "manifest_checksum": manifest_checksum(manifest),
        "primary_target": manifest["primary_target"],
        "arms": arm_summaries,
        "comparisons": comparisons,
    }


def _format_metric(value: Any, digits: int = 3) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _markdown(summary: Mapping[str, Any]) -> str:
    provenance = summary.get("provenance", {})
    timing = provenance.get("timing", {})
    lines = [
        "# Paired Cap-Expansion Evidence",
        "",
        "This is generated full-workflow evidence. It does not promote a production search cap.",
        "",
        f"Implementation commit: `{provenance.get('git_commit', 'n/a')}`  ",
        f"Manifest checksum: `{summary.get('manifest_checksum', 'n/a')}`  ",
        f"Total runtime (seconds): {_format_metric(timing.get('elapsed_seconds'), 2)}  ",
        f"Budget exceeded: `{timing.get('budget_exceeded', 'n/a')}`",
        "",
        "| Arm | Rows | Workflow errors | Fragility reached |",
        "|---|---:|---:|---:|",
    ]
    for arm, values in summary["arms"].items():
        counts = values["status_counts"]["workflow_status"]
        fragility = values["status_counts"]["fragility_status"]
        lines.append(
            f"| {arm} | {values['rows']} | {counts.get('error', 0)} | "
            f"{fragility.get('reached', 0)} |"
        )
    lines.extend(
        [
            "",
            "## Primary paired reach transitions",
            "",
            "| Comparison | Matched pairs | Comparable pairs | Unreached → reached | Difference | 95% interval |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for arm, values in summary["comparisons"].items():
        interval = values["reach_rate_difference"]
        lines.append(
            f"| {arm} | {values['matched_pairs']} | {values['comparable_pair_count']} | "
            f"{values['transition_counts']['unreached_to_reached']} | "
            f"{_format_metric(interval['estimate'])} | "
            f"[{_format_metric(interval['lower'])}, {_format_metric(interval['upper'])}] |"
        )
    lines.extend(
        [
            "",
            "Pooled and jointly-valid pair metrics are separate populations with separate denominators.",
            "Errors, unreached searches, right-censored reference tails, and rejected bootstrap resamples remain distinct states.",
            "",
        ]
    )
    return "\n".join(lines)


def summarize_cap_expansion(
    results_csv: str | Path,
    summary_json: str | Path,
    summary_markdown: str | Path,
    manifest_path: str | Path,
) -> None:
    """Write JSON and Markdown summaries for a cap-expansion CSV."""
    manifest = load_cap_expansion_manifest(manifest_path)
    results_path = Path(results_csv)
    metadata_path = results_path.with_suffix(".metadata.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    with Path(results_csv).open(newline="", encoding="utf-8") as handle:
        summary = summarize_cap_expansion_rows(list(csv.DictReader(handle)), manifest)
    summary["provenance"] = _summary_provenance(metadata)
    Path(summary_json).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    Path(summary_markdown).write_text(_markdown(summary), encoding="utf-8")
    metadata["artifact_checksums"] = {
        "results_csv": _sha256_file(results_path),
        "summary_json": _sha256_file(summary_json),
        "summary_markdown": _sha256_file(summary_markdown),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def _required_int(row: Mapping[str, Any], field: str) -> int:
    value = row.get(field)
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be an integer") from None
    if str(value).strip() != str(parsed):
        raise ValueError(f"{field} must be an integer")
    return parsed


def _validate_status_semantics(row: Mapping[str, Any]) -> None:
    fragility_status = str(row["fragility_status"])
    certification_status = str(row["certification_status"])
    calibration_status = str(row["calibration_status"])
    wald_status = str(row["wald_status"])
    bootstrap_status = str(row["bootstrap_status"])
    workflow_status = str(row["workflow_status"])
    reached = _optional_bool(row, "reached")

    if fragility_status == "reached":
        if reached is not True:
            raise ValueError("reached fragility status requires reached=true")
        if _optional_float(row, "greedy_fragility_50") is None:
            raise ValueError("reached fragility status requires a greedy fragility value")
    elif fragility_status == "unreached":
        if reached is not False:
            raise ValueError("unreached fragility status requires reached=false")
        if _optional_float(row, "greedy_fragility_50") is not None:
            raise ValueError("unreached fragility status cannot have a greedy fragility value")
    elif reached is not None:
        raise ValueError("error fragility status requires reached to be empty")

    if certification_status == "skipped_unreached":
        if fragility_status != "unreached" or _optional_bool(row, "certified") is not None:
            raise ValueError("skipped certification requires an unreached fragility result")
    elif certification_status in {"certified", "not_certified"}:
        if fragility_status != "reached":
            raise ValueError("completed certification requires reached fragility")
        certified = _optional_bool(row, "certified")
        expected_certified = certification_status == "certified"
        if certified is not expected_certified:
            raise ValueError("certification status does not match certified value")
        exact = _optional_float(row, "exact_fragility_50")
        if expected_certified and exact is None:
            raise ValueError("certified result requires an exact fragility value")
        if not expected_certified and exact is not None:
            raise ValueError("not-certified result cannot have an exact fragility value")

    reference_tail = _optional_float(row, "reference_tail_probability")
    reference_fraction = _optional_float(row, "reference_reached_fraction")
    if calibration_status == "finite":
        if reached is not True or reference_tail is None:
            raise ValueError("finite calibration requires reached data and a finite tail")
        if reference_fraction is None or not math.isclose(reference_fraction, 1.0):
            raise ValueError("finite calibration requires all reference searches to reach")
    elif calibration_status == "right_censored":
        if reached is not True or reference_tail is None:
            raise ValueError("right-censored calibration requires reached data and a finite tail")
        if reference_fraction is None or not 0.0 <= reference_fraction < 1.0:
            raise ValueError("right-censored calibration requires a partial reference fraction")
    elif calibration_status == "observed_unreached":
        if reached is not False or reference_tail is not None:
            raise ValueError("observed-unreached calibration requires no observed tail")

    if wald_status == "ok" and _optional_float(row, "wald_z") is None:
        raise ValueError("successful Wald status requires a finite Wald value")
    if bootstrap_status == "ok":
        if _optional_bool(row, "bootstrap_ci_excludes_zero") is None:
            raise ValueError("successful bootstrap status requires a Boolean result")
        rejected = _optional_float(row, "bootstrap_rejected_resamples")
        if rejected is None or rejected < 0.0 or not rejected.is_integer():
            raise ValueError("successful bootstrap status requires a nonnegative rejection count")

    stage_error = any(row[field] == "error" for field in STAGE_FIELDS)
    has_error_fields = any(str(row.get(field, "")).strip() for field in (
        "error_stage",
        "error_type",
        "error_message",
    ))
    if workflow_status == "error":
        if not stage_error and str(row.get("error_stage", "")).strip() not in {
            "data",
            "fit",
            "influence",
        }:
            raise ValueError("workflow error requires a stage error")
        if not has_error_fields:
            raise ValueError("workflow errors require error fields")
    else:
        if stage_error or has_error_fields:
            raise ValueError("stage or error fields require workflow_status=error")
        if workflow_status == "partial":
            if fragility_status != "unreached" and calibration_status != "observed_unreached":
                raise ValueError("partial workflow requires an unavailable observed endpoint")
        elif fragility_status != "reached" or calibration_status not in {"finite", "right_censored"}:
            raise ValueError("ok workflow requires reached fragility and observed calibration")


def _validate_row(
    row: Mapping[str, Any],
    expected_caps: Mapping[str, int],
    expected_job: Mapping[str, Any],
) -> None:
    arm = str(row.get("arm", ""))
    if arm not in expected_caps:
        raise ValueError(f"unknown arm: {arm}")
    for field in ("parameter_id", "replication", "N", "p", "data_seed", "calibration_seed", "bootstrap_seed", "search_cap"):
        _required_int(row, field)
    if _required_int(row, "search_cap") != expected_caps[arm]:
        raise ValueError(f"{arm} search_cap does not match manifest")
    expected_parameter = expected_job["parameter"]
    actual_parameter = str(row.get("parameter", "")).strip()
    if expected_parameter is None:
        if actual_parameter:
            raise ValueError("parameter must be empty for this scenario")
    else:
        try:
            if float(actual_parameter) != float(expected_parameter):
                raise ValueError("parameter does not match manifest")
        except ValueError:
            raise ValueError("parameter does not match manifest") from None
    if _optional_float(row, "fragility_target") != 0.5:
        raise ValueError("fragility_target must be 0.5")
    if _optional_bool(row, "calibration_require_reached") is not False:
        raise ValueError("calibration_require_reached must be false")
    for field, allowed in ALLOWED_STATUSES.items():
        value = str(row.get(field, ""))
        if value not in allowed:
            raise ValueError(f"invalid {field}: {value}")
    _validate_status_semantics(row)
    digest = str(row.get("dataset_digest", "")).strip()
    if not digest and row.get("error_stage") != "data":
        raise ValueError("dataset_digest is required for generated data")
    if digest and _DIGEST_PATTERN.fullmatch(digest) is None:
        raise ValueError("dataset_digest must be a lowercase SHA-256 hex digest")
    elapsed = _optional_float(row, "elapsed_seconds")
    if elapsed is None or elapsed < 0.0:
        raise ValueError("elapsed_seconds must be nonnegative")
    for field in (
        "reference_reached_fraction",
        "bootstrap_ci_excludes_zero",
        "contamination_status",
    ):
        if field == "bootstrap_ci_excludes_zero":
            if row.get("bootstrap_status") == "ok" and _optional_bool(row, field) is None:
                raise ValueError(f"{field} must be Boolean when bootstrap succeeds")
        else:
            value = _optional_float(row, field)
            if value is not None and not 0.0 <= value <= 1.0:
                raise ValueError(f"{field} must be between 0 and 1")


def _read_results(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != CAP_EXPANSION_FIELDNAMES:
            raise ValueError("results CSV fields do not match the cap-expansion schema")
        return list(reader)


def validate_cap_expansion(
    results_csv: str | Path,
    metadata_json: str | Path,
    summary_json: str | Path,
    manifest_path: str | Path,
) -> None:
    """Validate schema, pairing, provenance, statuses, and summary counts."""
    manifest = load_cap_expansion_manifest(manifest_path)
    rows = _read_results(results_csv)
    jobs = expand_cap_expansion_jobs(manifest)
    expected_keys = {
        (job["arm"], *(job[field] for field in PAIRING_FIELDS)) for job in jobs
    }
    actual_keys = [
        (row["arm"], *(_pairing_key(row) or ())) for row in rows
    ]
    if len(rows) != manifest["expected_rows"]:
        raise ValueError(f"results contain {len(rows)} rows, expected 1620")
    if len(set(actual_keys)) != len(actual_keys):
        raise ValueError("results contain duplicate arm/pairing keys")
    if set(actual_keys) != expected_keys:
        raise ValueError("results arm/pairing keys do not match the frozen manifest")
    expected_caps = {job["arm"]: int(job["search_cap"]) for job in jobs}
    expected_jobs = {
        (job["arm"], *(job[field] for field in PAIRING_FIELDS)): job for job in jobs
    }
    pairing_keys = cap_expansion_pairing_keys(manifest)
    expected_data_seeds = dict(
        zip(
            pairing_keys,
            replication_seeds(int(manifest["seed"]), len(pairing_keys)),
            strict=True,
        )
    )
    for row in rows:
        key = (row["arm"], *(_pairing_key(row) or ()))
        _validate_row(row, expected_caps, expected_jobs[key])
        pairing_key = _pairing_key(row)
        assert pairing_key is not None
        expected_data_seed = expected_data_seeds[pairing_key]
        if _required_int(row, "data_seed") != expected_data_seed:
            raise ValueError("data_seed does not match deterministic pairing seed")
        child_seeds = derive_workflow_seeds(expected_data_seed)
        if _required_int(row, "calibration_seed") != child_seeds.calibration:
            raise ValueError("calibration_seed does not match deterministic child seed")
        if _required_int(row, "bootstrap_seed") != child_seeds.bootstrap:
            raise ValueError("bootstrap_seed does not match deterministic child seed")

    grouped: dict[tuple[Any, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[_pairing_key(row)].append(row)
    for key, pair in grouped.items():
        if {row["arm"] for row in pair} != set(CAP_ARM_NAMES):
            raise ValueError(f"pair {key} does not contain all three arms")
        for field in ("data_seed", "calibration_seed", "bootstrap_seed"):
            if len({row[field] for row in pair}) != 1:
                raise ValueError(f"paired rows do not share {field}")
        digests = {row["dataset_digest"] for row in pair if row["dataset_digest"]}
        if len(digests) > 1:
            raise ValueError("paired rows do not share dataset_digest")

    metadata = json.loads(Path(metadata_json).read_text(encoding="utf-8"))
    required_metadata = {
        "git_commit",
        "python_version",
        "numpy_version",
        "package_version",
        "manifest_checksum",
        "rows",
        "arm_rows",
        "status_counts",
        "timing",
    }
    if not required_metadata.issubset(metadata):
        raise ValueError("metadata is missing required provenance fields")
    if metadata["manifest_checksum"] != manifest_checksum(manifest):
        raise ValueError("manifest checksum does not match metadata")
    if metadata["rows"] != len(rows):
        raise ValueError("metadata row count does not match results")
    if Counter(metadata["arm_rows"]) != Counter(row["arm"] for row in rows):
        raise ValueError("metadata arm counts do not match results")
    expected_status_counts = _status_counts(rows)
    if metadata["status_counts"] != expected_status_counts:
        raise ValueError("metadata status counts do not match results")
    elapsed = _finite_float(metadata.get("timing", {}).get("elapsed_seconds"))
    if elapsed is None or elapsed < 0.0:
        raise ValueError("metadata timing is invalid")
    if metadata["timing"].get("runtime_ceiling_seconds") != manifest[
        "operational_runtime_ceiling_seconds"
    ]:
        raise ValueError("metadata runtime ceiling does not match manifest")
    if metadata["timing"].get("budget_exceeded") != (
        elapsed > manifest["operational_runtime_ceiling_seconds"]
    ):
        raise ValueError("metadata budget status does not match timing")

    checksums = metadata.get("artifact_checksums")
    if not isinstance(checksums, dict):
        raise TypeError("metadata is missing artifact checksums")
    expected_checksums = {
        "results_csv": _sha256_file(results_csv),
        "summary_json": _sha256_file(summary_json),
        "summary_markdown": _sha256_file(Path(summary_json).with_suffix(".md")),
    }
    if checksums != expected_checksums:
        raise ValueError("artifact checksums do not match generated files")

    summary = json.loads(Path(summary_json).read_text(encoding="utf-8"))
    expected_summary = summarize_cap_expansion_rows(rows, manifest)
    expected_summary["provenance"] = _summary_provenance(metadata)
    if summary != expected_summary:
        raise ValueError("summary does not match results and metadata")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results_csv", type=Path)
    parser.add_argument("metadata_json", type=Path)
    parser.add_argument("summary_json", type=Path)
    parser.add_argument("summary_markdown", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    summarize_cap_expansion(args.results_csv, args.summary_json, args.summary_markdown, args.manifest)
    if args.validate:
        validate_cap_expansion(args.results_csv, args.metadata_json, args.summary_json, args.manifest)


if __name__ == "__main__":
    main()
