"""Summarize and validate reach-boundary diagnostic artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from statistics import median
from typing import Any

from tools.reach_boundary_manifest import (
    expand_reach_boundary_jobs,
    load_reach_boundary_manifest,
)
from tools.run_reach_boundary import FIELDNAMES

BASELINE_ARM = "baseline_cap2"
_DIAGNOSTIC_FIELDS = (
    "full_value",
    "final_value",
    "shrinkage",
    "rank",
    "min_eigenvalue_correlation",
    "min_eigenvalue_shrunk_correlation",
    "condition_number",
)


def _optional_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1"}:
            return True
        if normalized in {"false", "0"}:
            return False
    return None


def _optional_float(value: object) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _required_int(row: dict[str, Any], field: str) -> int:
    value = _optional_float(row.get(field))
    if value is None or not value.is_integer():
        raise ValueError(f"row field {field} must be an integer")
    return int(value)


def _pairing_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["scenario"]),
        _required_int(row, "N"),
        _required_int(row, "p"),
        _required_int(row, "parameter_id"),
        _required_int(row, "replication"),
    )


def _full_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (str(row["arm"]), *_pairing_key(row))


def _status(row: dict[str, Any]) -> str:
    status = str(row.get("status", ""))
    if status not in {"ok", "error"}:
        raise ValueError(f"row has invalid status: {status!r}")
    return status


def _median_field(rows: Iterable[dict[str, Any]], field: str) -> float | None:
    values = [value for row in rows if (value := _optional_float(row.get(field))) is not None]
    return float(median(values)) if values else None


def _cell_summary(arm: str, key: tuple[Any, ...], rows: list[dict[str, Any]]) -> dict[str, Any]:
    scenario, n, p, parameter_id = key
    statuses = Counter(_status(row) for row in rows)
    reached = sum(_optional_bool(row.get("reached")) is True for row in rows)
    censored = sum(
        _status(row) == "ok" and _optional_bool(row.get("reached")) is False for row in rows
    )
    errors = statuses.get("error", 0)
    total = len(rows)
    return {
        "arm": arm,
        "scenario": scenario,
        "N": n,
        "p": p,
        "parameter_id": parameter_id,
        "rows": total,
        "successful_rows": statuses.get("ok", 0),
        "reached_rows": reached,
        "censored_rows": censored,
        "error_rows": errors,
        "reach_rate": reached / total if total else None,
        "censor_rate": censored / total if total else None,
        "error_rate": errors / total if total else None,
        "median_condition_number": _median_field(rows, "condition_number"),
        "median_min_eigenvalue_shrunk_correlation": _median_field(
            rows, "min_eigenvalue_shrunk_correlation"
        ),
        "median_elapsed_seconds": _median_field(rows, "elapsed_seconds"),
        "total_elapsed_seconds": sum(
            value for row in rows if (value := _optional_float(row.get("elapsed_seconds"))) is not None
        ),
    }


def _group_cells(rows: list[dict[str, Any]]) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[_pairing_key(row)[:4]].append(row)
    return groups


def _group_pairs(rows: list[dict[str, Any]]) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[_pairing_key(row)].append(row)
    return groups


def _group_by_arm(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row["arm"])].append(row)
    return groups


def _row_state(row: dict[str, Any]) -> bool | None:
    if _status(row) == "error":
        return None
    reached = _optional_bool(row.get("reached"))
    if reached is None:
        raise ValueError("successful row must have a Boolean reached field")
    return reached


def _transition_summary(
    baseline_rows: dict[tuple[Any, ...], list[dict[str, Any]]],
    candidate_rows: dict[tuple[Any, ...], list[dict[str, Any]]],
) -> dict[str, Any]:
    common_keys = set(baseline_rows) & set(candidate_rows)
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    duplicate_keys = 0
    for key in sorted(common_keys):
        if len(baseline_rows[key]) != 1 or len(candidate_rows[key]) != 1:
            duplicate_keys += 1
            continue
        pairs.append((baseline_rows[key][0], candidate_rows[key][0]))

    transitions = {"0_to_0": 0, "0_to_1": 0, "1_to_0": 0, "1_to_1": 0}
    baseline_errors = candidate_errors = 0
    baseline_censored = candidate_censored = 0
    newly_reached_counts: list[float] = []
    extra_deletions: list[float] = []
    for baseline, candidate in pairs:
        baseline_state = _row_state(baseline)
        candidate_state = _row_state(candidate)
        baseline_errors += baseline_state is None
        candidate_errors += candidate_state is None
        baseline_censored += baseline_state is False
        candidate_censored += candidate_state is False
        if baseline_state is None or candidate_state is None:
            continue
        transition = f"{int(baseline_state)}_to_{int(candidate_state)}"
        transitions[transition] += 1
        baseline_count = _optional_float(baseline.get("greedy_count"))
        candidate_count = _optional_float(candidate.get("greedy_count"))
        if not baseline_state and candidate_state and candidate_count is not None:
            newly_reached_counts.append(candidate_count)
        if baseline_state and candidate_state and baseline_count is not None and candidate_count is not None:
            extra_deletions.append(candidate_count - baseline_count)

    matched_pairs = len(pairs)
    baseline_reached = transitions["1_to_0"] + transitions["1_to_1"]
    candidate_reached = transitions["0_to_1"] + transitions["1_to_1"]
    return {
        "matched_pairs": matched_pairs,
        "unmatched_baseline_rows": sum(
            len(rows) for key, rows in baseline_rows.items() if key not in common_keys
        ),
        "unmatched_candidate_rows": sum(
            len(rows) for key, rows in candidate_rows.items() if key not in common_keys
        ),
        "duplicate_keys": duplicate_keys,
        "transition_counts": transitions,
        "baseline_error_rows": baseline_errors,
        "candidate_error_rows": candidate_errors,
        "baseline_censored_rows": baseline_censored,
        "candidate_censored_rows": candidate_censored,
        "baseline_reach_rate": baseline_reached / matched_pairs if matched_pairs else None,
        "candidate_reach_rate": candidate_reached / matched_pairs if matched_pairs else None,
        "reach_difference": (
            (candidate_reached - baseline_reached) / matched_pairs if matched_pairs else None
        ),
        "newly_reached_rows": transitions["0_to_1"],
        "median_greedy_count_newly_reached": (
            float(median(newly_reached_counts)) if newly_reached_counts else None
        ),
        "median_extra_deletions_both_reached": (
            float(median(extra_deletions)) if extra_deletions else None
        ),
    }


def _comparison_summary(
    baseline_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    baseline_groups = _group_pairs(baseline_rows)
    candidate_groups = _group_pairs(candidate_rows)
    aggregate = _transition_summary(
        {key: rows for key, rows in baseline_groups.items()},
        {key: rows for key, rows in candidate_groups.items()},
    )
    cells: list[dict[str, Any]] = []
    baseline_cells = _group_cells(baseline_rows)
    candidate_cells = _group_cells(candidate_rows)
    for cell_key in sorted(candidate_cells):
        cell = _transition_summary(
            _group_pairs(baseline_cells.get(cell_key, [])),
            _group_pairs(candidate_cells.get(cell_key, [])),
        )
        scenario, n, p, parameter_id = cell_key
        cells.append(
            {
                "scenario": scenario,
                "N": n,
                "p": p,
                "parameter_id": parameter_id,
                **cell,
            }
        )
    return {**aggregate, "cell_summaries": cells}


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize arm reach, diagnostics, and paired transitions."""
    arm_groups = _group_by_arm(rows)
    arm_summaries: dict[str, Any] = {}
    cell_summaries: list[dict[str, Any]] = []
    for arm, arm_rows in sorted(arm_groups.items()):
        cells = _group_cells(arm_rows)
        summaries = [
            _cell_summary(arm, key, cell_rows)
            for key, cell_rows in sorted(cells.items())
        ]
        cell_summaries.extend(summaries)
        arm_summaries[arm] = {
            **_cell_summary(arm, ("all", 0, 0, 0), arm_rows),
            "cell_count": len(summaries),
        }
        arm_summaries[arm].pop("scenario", None)
        arm_summaries[arm].pop("N", None)
        arm_summaries[arm].pop("p", None)
        arm_summaries[arm].pop("parameter_id", None)

    baseline_rows = arm_groups.get(BASELINE_ARM, [])
    comparisons = {
        arm: _comparison_summary(baseline_rows, candidate_rows)
        for arm, candidate_rows in sorted(arm_groups.items())
        if arm != BASELINE_ARM
    }
    return {
        "rows": len(rows),
        "arms": arm_summaries,
        "cell_summaries": cell_summaries,
        "comparisons": comparisons,
    }


def _format(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Reach-Boundary Summary",
        "",
        "## Arm summaries",
        "",
        "| Arm | Rows | Successful | Reached | Censored | Errors | Reach rate | Error rate | Median condition | Runtime (s) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm, values in summary["arms"].items():
        lines.append(
            f"| {arm} | {values['rows']} | {values['successful_rows']} | "
            f"{values['reached_rows']} | {values['censored_rows']} | {values['error_rows']} | "
            f"{_format(values['reach_rate'])} | {_format(values['error_rate'])} | "
            f"{_format(values['median_condition_number'])} | "
            f"{_format(values['total_elapsed_seconds'])} |"
        )
    lines.extend(
        [
            "",
            "## Paired transitions against `baseline_cap2`",
            "",
            "| Candidate | Matched | 0->0 | 0->1 | 1->0 | 1->1 | Baseline errors | Candidate errors | Reach difference | Median new count | Median extra deletions |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for arm, values in summary["comparisons"].items():
        transitions = values["transition_counts"]
        lines.append(
            f"| {arm} | {values['matched_pairs']} | {transitions['0_to_0']} | "
            f"{transitions['0_to_1']} | {transitions['1_to_0']} | {transitions['1_to_1']} | "
            f"{values['baseline_error_rows']} | {values['candidate_error_rows']} | "
            f"{_format(values['reach_difference'])} | "
            f"{_format(values['median_greedy_count_newly_reached'])} | "
            f"{_format(values['median_extra_deletions_both_reached'])} |"
        )
    lines.extend(
        [
            "",
            "## Arm/scenario/cell diagnostics",
            "",
            "The JSON summary retains the complete machine-readable record.",
            "",
            "| Arm | Scenario | N | p | Rows | Reached | Censored | Errors | Reach rate | Median condition | Runtime (s) |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for values in summary["cell_summaries"]:
        lines.append(
            f"| {values['arm']} | {values['scenario']} | {values['N']} | {values['p']} | "
            f"{values['rows']} | {values['reached_rows']} | {values['censored_rows']} | "
            f"{values['error_rows']} | {_format(values['reach_rate'])} | "
            f"{_format(values['median_condition_number'])} | "
            f"{_format(values['total_elapsed_seconds'])} |"
        )
    return "\n".join(lines) + "\n"


def summarize_reach_boundary(
    input_csv: str | Path, json_output: str | Path, markdown_output: str | Path
) -> None:
    """Read reach-boundary rows and write JSON plus Markdown summaries."""
    with Path(input_csv).open(newline="", encoding="utf-8") as handle:
        summary = summarize_rows(list(csv.DictReader(handle)))
    Path(json_output).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    Path(markdown_output).write_text(_markdown(summary), encoding="utf-8")


def _manifest_checksum(manifest: dict[str, Any]) -> str:
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_finite(row: dict[str, Any], field: str) -> float:
    value = _optional_float(row.get(field))
    if value is None:
        raise ValueError(f"successful row has missing or nonfinite {field}")
    return value


def _validate_row(row: dict[str, Any]) -> None:
    status = _status(row)
    elapsed = _require_finite(row, "elapsed_seconds")
    if elapsed < 0.0:
        raise ValueError("elapsed_seconds must be nonnegative")
    if status == "error":
        if not row.get("error_type") or not row.get("error_message"):
            raise ValueError("error row must include error_type and error_message")
        if any(row.get(field) not in {None, ""} for field in _DIAGNOSTIC_FIELDS):
            raise ValueError("error row must not contain successful diagnostics")
        if row.get("reached") not in {None, ""}:
            raise ValueError("error row must not have a reach status")
        return

    reached = _optional_bool(row.get("reached"))
    cap_exhausted = _optional_bool(row.get("cap_exhausted"))
    if reached is None or cap_exhausted is None:
        raise ValueError("successful row must have Boolean reached and cap_exhausted fields")
    target = _require_finite(row, "fragility_target")
    if not 0.0 < target < 1.0:
        raise ValueError("fragility_target must be between 0 and 1")
    cap = _required_int(row, "search_cap")
    if cap < 1:
        raise ValueError("search_cap must be positive")
    full_value = _require_finite(row, "full_value")
    final_value = _require_finite(row, "final_value")
    if not -1.0 <= full_value <= 1.0 or not -1.0 <= final_value <= 1.0:
        raise ValueError("partial-correlation values must be between -1 and 1")
    shrinkage = _require_finite(row, "shrinkage")
    if not 0.0 <= shrinkage <= 1.0:
        raise ValueError("shrinkage must be between 0 and 1")
    if _required_int(row, "rank") < 1:
        raise ValueError("rank must be positive")
    if _require_finite(row, "condition_number") < 1.0:
        raise ValueError("condition_number must be at least 1")
    for field in ("min_eigenvalue_correlation", "min_eigenvalue_shrunk_correlation"):
        _require_finite(row, field)
    trajectory = json.loads(str(row.get("trajectory", "")))
    if not isinstance(trajectory, list) or not trajectory:
        raise ValueError("trajectory must be a nonempty JSON list")
    if any(not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in trajectory):
        raise ValueError("trajectory values must be finite")
    if not math.isclose(float(trajectory[0]), full_value, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("trajectory does not start at full_value")
    if not math.isclose(float(trajectory[-1]), final_value, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("trajectory does not end at final_value")
    count = _optional_float(row.get("greedy_count"))
    if reached:
        if count is None or not count.is_integer() or not 0 <= count <= cap:
            raise ValueError("reached row has invalid greedy_count")
    elif count is not None:
        raise ValueError("unreached row must not have greedy_count")


def _read_results(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != FIELDNAMES:
            raise ValueError("results CSV fields do not match the reach-boundary schema")
        return list(reader)


def validate_reach_boundary(
    results_csv: str | Path,
    metadata_json: str | Path,
    summary_json: str | Path,
    manifest_path: str | Path,
) -> None:
    """Validate a reach-boundary artifact against its frozen manifest."""
    manifest = load_reach_boundary_manifest(manifest_path)
    rows = _read_results(results_csv)
    expected_jobs = expand_reach_boundary_jobs(manifest)
    expected_keys = {
        (job["arm"], *_pairing_key(job))
        for job in expected_jobs
    }
    if len(rows) != manifest["expected_rows"]:
        raise ValueError(
            f"results contain {len(rows)} rows, expected {manifest['expected_rows']}"
        )
    actual_keys = [_full_key(row) for row in rows]
    if len(set(actual_keys)) != len(actual_keys):
        raise ValueError("results contain duplicate arm/pairing keys")
    if set(actual_keys) != expected_keys:
        raise ValueError("results arm/pairing keys do not match the frozen manifest")
    for row in rows:
        _validate_row(row)

    expected_arm_rows = Counter(job["arm"] for job in expected_jobs)
    actual_arm_rows = Counter(str(row["arm"]) for row in rows)
    if actual_arm_rows != expected_arm_rows:
        raise ValueError("results arm counts do not match the frozen manifest")
    actual_status_counts = Counter(_status(row) for row in rows)

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
    if metadata["manifest_checksum"] != _manifest_checksum(manifest):
        raise ValueError("manifest checksum does not match metadata")
    if metadata["rows"] != len(rows):
        raise ValueError("metadata row count does not match results")
    if Counter(metadata["arm_rows"]) != expected_arm_rows:
        raise ValueError("metadata arm counts do not match results")
    if Counter(metadata["status_counts"]) != actual_status_counts:
        raise ValueError("metadata status counts do not match results")
    elapsed = _optional_float(metadata.get("timing", {}).get("elapsed_seconds"))
    if elapsed is None or elapsed < 0.0:
        raise ValueError("metadata timing is invalid")

    summary = json.loads(Path(summary_json).read_text(encoding="utf-8"))
    if summary.get("rows") != len(rows):
        raise ValueError("summary row count does not match results")
    if set(summary.get("arms", {})) != set(expected_arm_rows):
        raise ValueError("summary arms do not match results")
    if set(summary.get("comparisons", {})) != set(expected_arm_rows) - {BASELINE_ARM}:
        raise ValueError("summary comparisons do not match candidate arms")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("results_csv", type=Path)
    parser.add_argument("metadata_json", type=Path)
    parser.add_argument("summary_json", type=Path)
    parser.add_argument("summary_markdown", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    summarize_reach_boundary(args.results_csv, args.summary_json, args.summary_markdown)
    if args.validate:
        validate_reach_boundary(
            args.results_csv,
            args.metadata_json,
            args.summary_json,
            args.manifest,
        )


if __name__ == "__main__":
    main()
