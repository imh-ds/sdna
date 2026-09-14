"""Summarize and validate the Task 25 certification-usability artifact."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.audit_certification_usability import identify_newly_reached_pairs
from tools.cap_expansion_manifest import (
    CAP_ARM_NAMES,
    load_cap_expansion_manifest,
    manifest_checksum,
)
from tools.certification_usability_manifest import load_certification_usability_manifest
from tools.run_cap_expansion import (
    CAP_EXPANSION_FIELDNAMES,
    CERTIFICATION_DIAGNOSTIC_FIELDNAMES,
)
from tools.summarize_cap_expansion import _summaries_match, validate_cap_expansion

REFERENCE_FIELDS = tuple(field for field in CAP_EXPANSION_FIELDNAMES if field != "elapsed_seconds")
_NUMERIC_FIELDS = {
    "parameter_id",
    "parameter",
    "replication",
    "N",
    "p",
    "data_seed",
    "calibration_seed",
    "bootstrap_seed",
    "fragility_target",
    "search_cap",
    "true_rho",
    "observed_rho",
    "lambda",
    "contamination_count",
    "contamination_status",
    "greedy_fragility_50",
    "exact_fragility_50",
    "reference_tail_probability",
    "reference_reached_fraction",
    "wald_z",
    "bootstrap_rejected_resamples",
    "influence_top_k_precision",
    "influence_top_k_recall",
    "first_planted_reciprocal_rank",
    "planted_absolute_influence_share",
}
_BOOLEAN_FIELDS = {
    "calibration_require_reached",
    "certified",
    "reached",
    "bootstrap_ci_excludes_zero",
}

__all__ = [
    "compare_instrumented_rows_to_reference",
    "summarize_certification_usability",
    "validate_certification_usability",
]


def _pair_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (str(row["arm"]), *(_pairing_key(row)))


def _pairing_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    try:
        return (
            str(row["scenario"]),
            int(row["N"]),
            int(row["p"]),
            int(row["parameter_id"]),
            int(row["replication"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("row has invalid pairing fields") from error


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"value is not numeric: {value!r}") from error
    if not math.isfinite(parsed):
        raise ValueError(f"value is not finite: {value!r}")
    return parsed


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


def _values_match(field: str, left: object, right: object) -> bool:
    left_empty = left is None or left == ""
    right_empty = right is None or right == ""
    if left_empty or right_empty:
        return left_empty and right_empty
    if field in _NUMERIC_FIELDS:
        left_number = _optional_float(left)
        right_number = _optional_float(right)
        return (
            left_number is not None
            and right_number is not None
            and math.isclose(left_number, right_number, rel_tol=1e-12, abs_tol=1e-12)
        )
    if field in _BOOLEAN_FIELDS:
        return _optional_bool(left) == _optional_bool(right)
    return str(left) == str(right)


def compare_instrumented_rows_to_reference(
    instrumented_rows: Sequence[Mapping[str, Any]],
    reference_rows: Sequence[Mapping[str, Any]],
) -> None:
    """Require instrumented rows to reproduce the original Task 24 fields."""
    if len(instrumented_rows) != len(reference_rows):
        raise ValueError("instrumented and reference row counts differ")

    reference_by_key: dict[tuple[Any, ...], Mapping[str, Any]] = {}
    for row in reference_rows:
        key = _pair_key(row)
        if key in reference_by_key:
            raise ValueError(f"duplicate reference row for {key}")
        reference_by_key[key] = row

    seen: set[tuple[Any, ...]] = set()
    for row in instrumented_rows:
        key = _pair_key(row)
        if key in seen:
            raise ValueError(f"duplicate instrumented row for {key}")
        seen.add(key)
        reference = reference_by_key.get(key)
        if reference is None:
            raise ValueError(f"instrumented row has no reference row for {key}")
        for field in REFERENCE_FIELDS:
            try:
                matches = _values_match(field, row.get(field), reference.get(field))
            except ValueError as error:
                raise ValueError(f"{field} differs for {key}") from error
            if not matches:
                raise ValueError(f"{field} differs for {key}")


def _counter(values: Sequence[object]) -> dict[str, int]:
    return dict(Counter(str(value) for value in values))


def _stratum_key(row: Mapping[str, Any]) -> str:
    return f"{row['scenario']}|{int(row['N'])}|{int(row['p'])}"


def _combination_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = [
        int(value)
        for row in rows
        if (value := _optional_float(row.get("certification_combinations_checked"))) is not None
    ]
    return {
        "rows": len(values),
        "total": sum(values),
        "minimum": min(values) if values else None,
        "maximum": max(values) if values else None,
    }


def _summarize_population(
    candidate_pairs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    candidate_rows = [pair["candidate"] for pair in candidate_pairs]
    denominator = len(candidate_rows)
    certified_rows = sum(
        row.get("certification_status") == "certified" for row in candidate_rows
    )
    strata: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in candidate_rows:
        strata[_stratum_key(row)].append(row)
    return {
        "rows": denominator,
        "certified_rows": certified_rows,
        "certification_yield": certified_rows / denominator if denominator else None,
        "certification_status_counts": _counter(
            [row.get("certification_status", "") for row in candidate_rows]
        ),
        "reason_counts": _counter(
            [row.get("certification_failure_reason", "") for row in candidate_rows]
        ),
        "budget_exhausted_rows": sum(
            _optional_bool(row.get("certification_budget_exhausted")) is True
            for row in candidate_rows
        ),
        "combination_counts": _combination_summary(candidate_rows),
        "downstream_status_counts": {
            field: _counter([row.get(field, "") for row in candidate_rows])
            for field in (
                "calibration_status",
                "wald_status",
                "bootstrap_status",
                "workflow_status",
            )
        },
        "error_stage_counts": _counter(
            [row.get("error_stage", "") or "none" for row in candidate_rows]
        ),
        "strata": {
            key: {
                "rows": len(stratum_rows),
                "certified_rows": sum(
                    row.get("certification_status") == "certified"
                    for row in stratum_rows
                ),
                "certification_yield": (
                    sum(row.get("certification_status") == "certified" for row in stratum_rows)
                    / len(stratum_rows)
                ),
            }
            for key, stratum_rows in sorted(strata.items())
        },
        "pair_keys": [
            {
                field: value
                for field, value in zip(
                    ("scenario", "N", "p", "parameter_id", "replication"),
                    pair["pair_key"],
                    strict=True,
                )
            }
            for pair in candidate_pairs
        ],
    }


def summarize_certification_usability(
    rows: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    audit_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Summarize certification yield among newly reached paired rows."""
    pairs = identify_newly_reached_pairs(rows)
    return {
        "study": audit_manifest["study"],
        "phase": "B",
        "rows": len(rows),
        "manifest_checksum": manifest_checksum(manifest),
        "candidate_caps": list(audit_manifest["candidate_caps"]),
        "primary_population": audit_manifest["primary_population"],
        "primary_endpoint": audit_manifest["primary_endpoint"],
        "source": {
            "run_id": audit_manifest["source_run_id"],
            "commit": audit_manifest["source_commit"],
            "artifact": audit_manifest["source_artifact"],
            "results_sha256": audit_manifest["source_results_sha256"],
        },
        "populations": {
            candidate_arm: _summarize_population(candidate_pairs)
            for candidate_arm, candidate_pairs in pairs.items()
        },
    }


def _render_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Certification usability Phase B summary",
        "",
        "This instrumented rerun reproduces the Task 24 paired workflow while",
        "recording certification diagnostics. It is not independent evidence",
        "and does not promote a search cap.",
        "",
        "## Certification yield among newly reached rows",
        "",
        "| Candidate cap | U→R rows | Certified rows | Certification yield | Budget-exhausted rows |",
        "| ---: | ---: | ---: | ---: | ---: |",
    ]
    for cap in summary["candidate_caps"]:
        population = summary["populations"][f"cap{cap}"]
        lines.append(
            f"| {cap} | {population['rows']} | {population['certified_rows']} | "
            f"{population['certification_yield']} | {population['budget_exhausted_rows']} |"
        )
    lines.extend(
        [
            "",
            "The denominator is the complete matched population that was",
            "unreached at cap 2 and reached at the candidate cap. Downstream",
            "failures remain in that denominator.",
            "",
            "Cap 2 remains the v0.1 production baseline. Any cap change requires",
            "a separate decision record and validation study.",
            "",
        ]
    )
    return "\n".join(lines)


def _read_rows(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV is missing a header")
        return list(reader.fieldnames), list(reader)


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metadata_provenance(metadata: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "git_commit": metadata["git_commit"],
        "python_version": metadata["python_version"],
        "numpy_version": metadata["numpy_version"],
        "package_version": metadata["package_version"],
        "timing": metadata["timing"],
    }


def _required_int(value: object, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be an integer") from error
    if isinstance(value, bool) or parsed < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return parsed


def _required_bool(value: object, field: str) -> bool:
    parsed = _optional_bool(value)
    if parsed is None:
        raise ValueError(f"{field} must be a boolean")
    return parsed


def _validate_diagnostic_row(row: Mapping[str, Any], allowed_reasons: set[str], budget: int) -> None:
    reason = str(row.get("certification_failure_reason", ""))
    if reason not in allowed_reasons:
        raise ValueError(f"invalid certification_failure_reason: {reason!r}")
    if _required_int(row.get("certification_combination_budget"), "certification budget") != budget:
        raise ValueError("certification combination budget does not match manifest")
    exhausted = _required_bool(
        row.get("certification_budget_exhausted"), "certification_budget_exhausted"
    )
    certification_status = str(row.get("certification_status", ""))
    fragility_status = str(row.get("fragility_status", ""))
    error_stage = str(row.get("error_stage", "") or "")
    if error_stage in {"data", "fit", "fragility"} or fragility_status == "error":
        if reason != "not_applicable_prior_error":
            raise ValueError("prior workflow error requires prior-error certification reason")
        if exhausted:
            raise ValueError("prior workflow error cannot exhaust certification budget")
        return
    if fragility_status == "unreached":
        if reason != "not_applicable_unreached" or exhausted:
            raise ValueError("unreached row has invalid certification diagnostic")
        if _required_int(row.get("certification_combinations_checked"), "combinations checked") != 0:
            raise ValueError("unreached row must have zero certification combinations checked")
        return
    if fragility_status != "reached":
        raise ValueError("row has invalid fragility status for certification diagnostics")
    if certification_status == "certified":
        if reason != "certified" or exhausted:
            raise ValueError("certified row has invalid certification diagnostic")
    elif certification_status == "not_certified":
        if reason == "combination_budget_exhausted" and not exhausted:
            raise ValueError("budget-exhausted reason requires true exhaustion flag")
        if reason == "not_certified_other" and exhausted:
            raise ValueError("other non-certification cannot set exhaustion flag")
        if reason not in {"combination_budget_exhausted", "not_certified_other"}:
            raise ValueError("not-certified row has invalid certification reason")
    elif certification_status == "error":
        if reason != "error" or exhausted:
            raise ValueError("certification error has invalid diagnostic")
    else:
        raise ValueError("reached row has invalid certification status")
    combinations = _required_int(
        row.get("certification_combinations_checked"), "certification combinations checked"
    )
    if combinations < 0:
        raise ValueError("certification combinations checked must be nonnegative")


def _validate_instrumented_rows(
    rows: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    audit_manifest: Mapping[str, Any],
) -> None:
    if len(rows) != manifest["expected_rows"]:
        raise ValueError("instrumented row count does not match manifest")
    arm_counts = Counter(str(row.get("arm", "")) for row in rows)
    if arm_counts != Counter({arm: 540 for arm in CAP_ARM_NAMES}):
        raise ValueError("instrumented arm counts are not balanced")
    seen: set[tuple[Any, ...]] = set()
    allowed_reasons = set(audit_manifest["reason_values"])
    budget = int(manifest["certification_combination_budget"])
    for row in rows:
        key = _pair_key(row)
        if key in seen:
            raise ValueError(f"duplicate instrumented row for {key}")
        seen.add(key)
        _validate_diagnostic_row(row, allowed_reasons, budget)
    identify_newly_reached_pairs(rows)


def _validate_metadata(
    metadata: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    results_csv: str | Path,
    summary_json: str | Path,
) -> None:
    required = {
        "git_commit",
        "python_version",
        "numpy_version",
        "package_version",
        "manifest_checksum",
        "rows",
        "arm_rows",
        "status_counts",
        "timing",
        "artifact_checksums",
    }
    if not required.issubset(metadata):
        raise ValueError("instrumented metadata is missing required fields")
    if metadata["manifest_checksum"] != manifest_checksum(manifest):
        raise ValueError("instrumented manifest checksum does not match manifest")
    if metadata["rows"] != len(rows):
        raise ValueError("instrumented metadata row count does not match results")
    if Counter(metadata["arm_rows"]) != Counter(str(row["arm"]) for row in rows):
        raise ValueError("instrumented metadata arm counts do not match results")
    elapsed = _optional_float(metadata.get("timing", {}).get("elapsed_seconds"))
    if elapsed is None or elapsed < 0.0:
        raise ValueError("instrumented timing is invalid")
    timing = metadata["timing"]
    if timing.get("runtime_ceiling_seconds") != manifest["operational_runtime_ceiling_seconds"]:
        raise ValueError("instrumented runtime ceiling does not match manifest")
    if timing.get("budget_exceeded") != (
        elapsed > manifest["operational_runtime_ceiling_seconds"]
    ):
        raise ValueError("instrumented budget status does not match timing")
    expected_checksums = {
        "results_csv": _sha256_file(results_csv),
        "summary_json": _sha256_file(summary_json),
        "summary_markdown": _sha256_file(Path(summary_json).with_suffix(".md")),
    }
    if metadata["artifact_checksums"] != expected_checksums:
        raise ValueError("instrumented artifact checksums do not match files")


def _write_summary_artifact(
    instrumented_results_csv: str | Path,
    instrumented_metadata_json: str | Path,
    summary_json: str | Path,
    source_manifest: str | Path,
    audit_manifest: str | Path,
) -> None:
    _, rows = _read_rows(instrumented_results_csv)
    manifest = load_cap_expansion_manifest(source_manifest)
    audit_config = load_certification_usability_manifest(audit_manifest)
    metadata = json.loads(Path(instrumented_metadata_json).read_text(encoding="utf-8"))
    summary = summarize_certification_usability(rows, manifest, audit_config)
    summary["provenance"] = _metadata_provenance(metadata)
    summary_file = Path(summary_json)
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    summary_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    markdown_file = summary_file.with_suffix(".md")
    markdown_file.write_text(_render_markdown(summary), encoding="utf-8")
    metadata["artifact_checksums"] = {
        "results_csv": _sha256_file(instrumented_results_csv),
        "summary_json": _sha256_file(summary_file),
        "summary_markdown": _sha256_file(markdown_file),
    }
    Path(instrumented_metadata_json).write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


def validate_certification_usability(
    instrumented_results_csv: str | Path,
    instrumented_metadata_json: str | Path,
    summary_json: str | Path,
    source_results_csv: str | Path,
    source_metadata_json: str | Path,
    source_summary_json: str | Path,
    source_manifest: str | Path,
    audit_manifest: str | Path,
) -> None:
    """Validate instrumented rows and reproduction against the Task 24 artifact."""
    manifest = load_cap_expansion_manifest(source_manifest)
    audit_config = load_certification_usability_manifest(audit_manifest)
    validate_cap_expansion(
        source_results_csv,
        source_metadata_json,
        source_summary_json,
        source_manifest,
    )
    if _sha256_file(source_results_csv) != audit_config["source_results_sha256"]:
        raise ValueError("source results checksum does not match audit manifest")
    instrumented_fields, instrumented_rows = _read_rows(instrumented_results_csv)
    expected_fields = CAP_EXPANSION_FIELDNAMES + CERTIFICATION_DIAGNOSTIC_FIELDNAMES
    if instrumented_fields != expected_fields:
        raise ValueError("instrumented CSV schema does not match the declared contract")
    _, source_rows = _read_rows(source_results_csv)
    _validate_instrumented_rows(instrumented_rows, manifest, audit_config)
    compare_instrumented_rows_to_reference(instrumented_rows, source_rows)
    metadata = json.loads(Path(instrumented_metadata_json).read_text(encoding="utf-8"))
    _validate_metadata(
        metadata,
        instrumented_rows,
        manifest,
        instrumented_results_csv,
        summary_json,
    )
    summary = json.loads(Path(summary_json).read_text(encoding="utf-8"))
    expected_summary = summarize_certification_usability(
        instrumented_rows,
        manifest,
        audit_config,
    )
    expected_summary["provenance"] = _metadata_provenance(metadata)
    if not _summaries_match(expected_summary, summary):
        raise ValueError("certification-usability summary does not match results")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instrumented_results_csv", type=Path)
    parser.add_argument("instrumented_metadata_json", type=Path)
    parser.add_argument("summary_json", type=Path)
    parser.add_argument("source_results_csv", type=Path)
    parser.add_argument("source_metadata_json", type=Path)
    parser.add_argument("source_summary_json", type=Path)
    parser.add_argument("source_manifest", type=Path)
    parser.add_argument("audit_manifest", type=Path)
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    _write_summary_artifact(
        args.instrumented_results_csv,
        args.instrumented_metadata_json,
        args.summary_json,
        args.source_manifest,
        args.audit_manifest,
    )
    if args.validate:
        validate_certification_usability(
            args.instrumented_results_csv,
            args.instrumented_metadata_json,
            args.summary_json,
            args.source_results_csv,
            args.source_metadata_json,
            args.source_summary_json,
            args.source_manifest,
            args.audit_manifest,
        )


if __name__ == "__main__":
    main()
