"""Tests for Task 26 arm validation, summaries, and aggregation."""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from tools.certification_budget_sensitivity_manifest import (
    certification_budget_sensitivity_manifest_checksum,
    load_certification_budget_sensitivity_manifest,
)
from tools.prepare_certification_budget_sensitivity import build_selection_manifest
from tools.run_certification_budget_sensitivity import SENSITIVITY_FIELDNAMES
from tools.summarize_certification_budget_sensitivity import (
    _required_exact_nonnegative_int,
    _required_finite_float,
    _required_nonnegative_int,
    aggregate_certification_budget_arms,
    main,
    summarize_certification_budget_arm,
    validate_certification_budget_arm,
)

STUDY_MANIFEST_PATH = Path("simulations/configs/certification_budget_sensitivity_v1.json")
STUDY_MANIFEST = load_certification_budget_sensitivity_manifest(STUDY_MANIFEST_PATH)


@pytest.mark.parametrize(
    ("validator", "value"),
    [
        (_required_nonnegative_int, object()),
        (_required_exact_nonnegative_int, True),
        (_required_finite_float, object()),
    ],
)
def test_numeric_field_validators_raise_type_error_for_wrong_python_types(
    validator: Any, value: object
) -> None:
    with pytest.raises(TypeError, match="field"):
        validator(value, "field")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_row(arm: str, index: int) -> dict[str, Any]:
    cap = {"baseline_cap2": 2, "cap3": 3, "cap4": 4}[arm]
    row = {field: None for field in SENSITIVITY_FIELDNAMES}
    row.update(
        {
            "arm": arm,
            "scenario": "clean_planted_edge" if index % 2 == 0 else "heavy_tails",
            "parameter_id": index % 3,
            "parameter": 0.2,
            "replication": index,
            "N": 100 + index,
            "p": 5,
            "data_seed": 10000 + index,
            "calibration_seed": 20000 + index,
            "bootstrap_seed": 30000 + index,
            "dataset_digest": f"{index + 1:064x}",
            "fragility_target": 0.5,
            "search_cap": cap,
            "calibration_require_reached": False,
            "true_rho": 0.2,
            "observed_rho": 0.19,
            "lambda": 0.1,
            "contamination_count": 0,
            "contamination_status": 0,
            "greedy_fragility_50": cap,
            "exact_fragility_50": None,
            "certified": False,
            "reached": arm != "baseline_cap2",
            "reference_tail_probability": 0.12,
            "reference_reached_fraction": 0.8,
            "wald_z": 1.25,
            "bootstrap_ci_excludes_zero": False,
            "bootstrap_rejected_resamples": 1,
            "influence_top_k_precision": None,
            "influence_top_k_recall": None,
            "first_planted_reciprocal_rank": None,
            "planted_absolute_influence_share": None,
            "fragility_status": "unreached" if arm == "baseline_cap2" else "reached",
            "certification_status": (
                "skipped_unreached" if arm == "baseline_cap2" else "not_certified"
            ),
            "calibration_status": "right_censored",
            "wald_status": "ok",
            "bootstrap_status": "ok",
            "workflow_status": "ok",
            "error_stage": None,
            "error_type": None,
            "error_message": None,
            "elapsed_seconds": 0.25,
            "certification_combinations_checked": 1000,
            "certification_combination_budget": 1000,
            "certification_budget_exhausted": arm != "baseline_cap2",
            "certification_failure_reason": (
                "not_applicable_unreached"
                if arm == "baseline_cap2"
                else "combination_budget_exhausted"
            ),
        }
    )
    return row


@pytest.fixture(scope="module")
def selection() -> dict[str, Any]:
    task25_rows: list[dict[str, Any]] = []
    for index in range(68):
        task25_rows.append(_source_row("baseline_cap2", index))
        task25_rows.append(_source_row("cap3", index))
        task25_rows.append(_source_row("cap4", index))
    # Only the first 44 keys transition at cap 3; all 68 transition at cap 4.
    for index in range(44, 68):
        cap3 = task25_rows[index * 3 + 1]
        cap3["fragility_status"] = "unreached"
        cap3["reached"] = False
        cap3["certification_status"] = "skipped_unreached"
    return build_selection_manifest(task25_rows, STUDY_MANIFEST)


def _arm_rows(selection: dict[str, Any], budget: int) -> list[dict[str, Any]]:
    rows = [
        copy.deepcopy(entry["candidate"])
        for cap in ("cap3", "cap4")
        for entry in selection["populations"][cap]
    ]
    for index, row in enumerate(rows):
        outcome = index % 4
        row["certification_combination_budget"] = budget
        row["elapsed_seconds"] = 0.5 + index / 1000
        if outcome == 0:
            row.update(
                certification_status="certified",
                certified=True,
                exact_fragility_50=int(row["search_cap"]),
                certification_combinations_checked=7,
                certification_budget_exhausted=False,
                certification_failure_reason="certified",
            )
        elif outcome == 1:
            row.update(
                certification_status="not_certified",
                certified=False,
                exact_fragility_50=None,
                certification_combinations_checked=budget,
                certification_budget_exhausted=True,
                certification_failure_reason="combination_budget_exhausted",
            )
        elif outcome == 2:
            row.update(
                certification_status="not_certified",
                certified=False,
                exact_fragility_50=None,
                certification_combinations_checked=3,
                certification_budget_exhausted=False,
                certification_failure_reason="not_certified_other",
            )
        else:
            row.update(
                certification_status="error",
                certified=None,
                exact_fragility_50=None,
                certification_combinations_checked=2,
                certification_budget_exhausted=False,
                certification_failure_reason="error",
            )
    return rows


def _pair_key(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "scenario": row["scenario"],
        "N": int(row["N"]),
        "p": int(row["p"]),
        "parameter_id": int(row["parameter_id"]),
        "replication": int(row["replication"]),
    }


def _completed_key(row: dict[str, Any]) -> dict[str, Any]:
    return {"arm": row["arm"], **_pair_key(row)}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SENSITIVITY_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _write_selection(tmp_path: Path, selection: dict[str, Any]) -> Path:
    path = tmp_path / "selection.json"
    path.write_text(json.dumps(selection), encoding="utf-8")
    return path


def _write_arm(
    root: Path,
    selection: dict[str, Any],
    budget: int,
    *,
    arm_status: str = "complete",
    row_limit: int | None = None,
) -> Path:
    arm_dir = root / str(budget)
    arm_dir.mkdir(parents=True, exist_ok=True)
    rows = _arm_rows(selection, budget)
    if row_limit is not None:
        rows = rows[:row_limit]
    results = arm_dir / "results.csv"
    _write_csv(results, rows)
    cap_counts = Counter(str(row["arm"]) for row in rows)
    core: dict[str, Any] = {
        "schema_version": 1,
        "study": "certification_budget_sensitivity",
        "arm_status": arm_status,
        "budget": budget,
        "expected_rows": 112,
        "rows": len(rows),
        "completed_rows": len(rows),
        "arm_rows": {"cap3": cap_counts["cap3"], "cap4": cap_counts["cap4"]},
        "observed_cap_rows": {
            "cap3": cap_counts["cap3"],
            "cap4": cap_counts["cap4"],
        },
        "certification_budget_exhausted_rows": sum(
            bool(row["certification_budget_exhausted"]) for row in rows
        ),
        "completed_keys": [_completed_key(row) for row in rows],
        "last_completed_key": _completed_key(rows[-1]) if rows else None,
        "elapsed_seconds": 12.5,
        "runtime_ceiling_seconds": 1800,
        "started_at": "2026-09-14T20:00:00+00:00",
        "finished_at": "2026-09-14T20:00:12.500000+00:00",
        "source_checksums": {
            "study_manifest": certification_budget_sensitivity_manifest_checksum(STUDY_MANIFEST),
            "selection_manifest": selection["selection_checksum"],
            "source_manifest": STUDY_MANIFEST["source_task24_manifest_checksum"],
            "source_task25_results": STUDY_MANIFEST["source_task25_results_sha256"],
            "source_task25_manifest": STUDY_MANIFEST["source_task25_manifest_checksum"],
            "source_task24_results": STUDY_MANIFEST["source_task24_results_sha256"],
            "source_task24_manifest": STUDY_MANIFEST["source_task24_manifest_checksum"],
        },
        "environment": {
            "git_commit": "7e011d2",
            "python_version": "3.11",
            "numpy_version": "2.0",
            "package_version": "0.1.0",
            "platform": "test",
        },
        "error_type": None,
        "error_message": None,
    }
    metadata = {**core, "artifact_checksums": {"results.csv": _sha256(results)}}
    metadata_path = arm_dir / "results.metadata.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    status = {
        **core,
        "artifact_checksums": {
            "results.csv": _sha256(results),
            "results.metadata.json": _sha256(metadata_path),
        },
    }
    (arm_dir / "arm_status.json").write_text(json.dumps(status), encoding="utf-8")
    return arm_dir


def _resign_arm(arm_dir: Path, rows: list[dict[str, Any]]) -> None:
    results = arm_dir / "results.csv"
    _write_csv(results, rows)
    _resign_arm_artifacts(arm_dir)


def _resign_arm_artifacts(arm_dir: Path) -> None:
    results = arm_dir / "results.csv"
    metadata_path = arm_dir / "results.metadata.json"
    status_path = arm_dir / "arm_status.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    status = json.loads(status_path.read_text(encoding="utf-8"))
    metadata["artifact_checksums"] = {"results.csv": _sha256(results)}
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    status["artifact_checksums"] = {
        "results.csv": _sha256(results),
        "results.metadata.json": _sha256(metadata_path),
    }
    status_path.write_text(json.dumps(status), encoding="utf-8")


def test_complete_arm_summary_uses_fixed_per_cap_denominators(
    selection: dict[str, Any],
) -> None:
    rows = _arm_rows(selection, 5000)
    status = {"arm_status": "complete", "expected_rows": 112, "rows": 112}

    summary = summarize_certification_budget_arm(rows, selection, STUDY_MANIFEST, status)

    cap3 = summary["populations"]["cap3"]
    cap4 = summary["populations"]["cap4"]
    assert (cap3["rows"], cap4["rows"]) == (44, 68)
    assert (cap3["certified_rows"], cap4["certified_rows"]) == (11, 17)
    assert cap3["certification_yield"] == 11 / 44
    assert cap4["certification_yield"] == 17 / 68
    assert cap3["yield_status"] == cap4["yield_status"] == "available"
    assert cap3["reason_counts"] == {
        "certified": 11,
        "combination_budget_exhausted": 11,
        "not_certified_other": 11,
        "error": 11,
    }
    assert cap3["budget_exhausted_rows"] == 11
    assert cap3["combination_counts"] == {
        "rows": 44,
        "total": 11 * (7 + 5000 + 3 + 2),
        "minimum": 2,
        "maximum": 5000,
    }
    assert cap3["downstream_status_counts"]["workflow_status"] == {"ok": 44}
    assert cap3["error_stage_counts"] == {"none": 44}
    assert cap3["pair_keys"] == [entry["pair_key"] for entry in selection["populations"]["cap3"]]
    assert cap4["pair_keys"] == [entry["pair_key"] for entry in selection["populations"]["cap4"]]


def test_incomplete_arm_has_no_certification_yield(
    selection: dict[str, Any],
) -> None:
    rows = _arm_rows(selection, 1000)[:7]
    status = {"arm_status": "timeout", "expected_rows": 112, "rows": 7}

    summary = summarize_certification_budget_arm(rows, selection, STUDY_MANIFEST, status)

    assert summary["arm_status"] == "timeout"
    assert summary["populations"]["cap3"]["rows"] == 7
    assert summary["populations"]["cap3"]["certification_yield"] is None
    assert summary["populations"]["cap3"]["yield_status"] == "unavailable_incomplete_arm"
    assert summary["populations"]["cap4"]["rows"] == 0
    assert summary["populations"]["cap4"]["certification_yield"] is None


def test_validator_accepts_complete_arm_and_writes_report(
    tmp_path: Path, selection: dict[str, Any]
) -> None:
    selection_path = _write_selection(tmp_path, selection)
    arm_dir = _write_arm(tmp_path / "arms", selection, 1000)

    report = validate_certification_budget_arm(arm_dir, selection_path, STUDY_MANIFEST_PATH)

    assert report["valid"] is True
    assert report["complete"] is True
    assert report["budget"] == 1000
    assert report["rows"] == 112
    assert report["summary"]["populations"]["cap3"]["rows"] == 44
    assert json.loads((arm_dir / "arm_validation.json").read_text()) == report


def test_validator_accepts_structurally_valid_timeout_without_yield(
    tmp_path: Path, selection: dict[str, Any]
) -> None:
    selection_path = _write_selection(tmp_path, selection)
    arm_dir = _write_arm(tmp_path / "arms", selection, 5000, arm_status="timeout", row_limit=7)

    report = validate_certification_budget_arm(arm_dir, selection_path, STUDY_MANIFEST_PATH)

    assert report["valid"] is True
    assert report["complete"] is False
    assert report["arm_status"] == "timeout"
    assert report["summary"]["populations"]["cap3"]["certification_yield"] is None


def test_validator_accepts_full_row_incomplete_checkpoint_without_yield(
    tmp_path: Path, selection: dict[str, Any]
) -> None:
    selection_path = _write_selection(tmp_path, selection)
    arm_dir = _write_arm(tmp_path / "arms", selection, 5000, arm_status="incomplete")

    report = validate_certification_budget_arm(arm_dir, selection_path, STUDY_MANIFEST_PATH)

    assert report["valid"] is True
    assert report["complete"] is False
    assert report["arm_status"] == "incomplete"
    assert report["rows"] == 112
    assert report["observed_cap_rows"] == {"cap3": 44, "cap4": 68}
    assert report["summary"]["populations"]["cap3"]["rows"] == 44
    assert report["summary"]["populations"]["cap4"]["rows"] == 68
    assert report["summary"]["populations"]["cap3"]["certification_yield"] is None
    assert report["summary"]["populations"]["cap4"]["certification_yield"] is None


@pytest.mark.parametrize(
    "updates",
    [
        {
            "certification_status": "certified",
            "certified": False,
            "exact_fragility_50": "garbage",
        },
        {
            "certification_status": "certified",
            "certified": True,
            "exact_fragility_50": "3.0",
        },
        {
            "certification_status": "not_certified",
            "certified": True,
            "exact_fragility_50": None,
            "certification_failure_reason": "not_certified_other",
        },
        {
            "certification_status": "not_certified",
            "certified": False,
            "exact_fragility_50": 3,
            "certification_failure_reason": "not_certified_other",
        },
        {
            "certification_status": "error",
            "certified": False,
            "exact_fragility_50": None,
            "certification_failure_reason": "error",
        },
        {
            "certification_status": "error",
            "certified": None,
            "exact_fragility_50": 3,
            "certification_failure_reason": "error",
        },
    ],
)
def test_validator_rejects_inconsistent_certification_outcomes(
    tmp_path: Path,
    selection: dict[str, Any],
    updates: dict[str, Any],
) -> None:
    selection_path = _write_selection(tmp_path, selection)
    arm_dir = _write_arm(tmp_path / "arms", selection, 10000)
    rows = _arm_rows(selection, 10000)
    rows[0].update(updates)
    _resign_arm(arm_dir, rows)

    report = validate_certification_budget_arm(arm_dir, selection_path, STUDY_MANIFEST_PATH)

    assert report["valid"] is False
    assert "certification outcome" in report["error_message"]


@pytest.mark.parametrize("exact_minimum", [0, 4])
def test_validator_rejects_certified_exact_minimum_outside_greedy_bound(
    tmp_path: Path,
    selection: dict[str, Any],
    exact_minimum: int,
) -> None:
    selection_path = _write_selection(tmp_path, selection)
    arm_dir = _write_arm(tmp_path / "arms", selection, 10000)
    rows = _arm_rows(selection, 10000)
    rows[0]["exact_fragility_50"] = exact_minimum
    _resign_arm(arm_dir, rows)

    report = validate_certification_budget_arm(arm_dir, selection_path, STUDY_MANIFEST_PATH)

    assert report["valid"] is False
    assert "certification outcome" in report["error_message"]


@pytest.mark.parametrize(
    "field",
    ["data_seed", "calibration_seed", "bootstrap_seed"],
)
def test_validator_requires_exact_integer_seed_equality(
    tmp_path: Path,
    selection: dict[str, Any],
    field: str,
) -> None:
    selection_path = _write_selection(tmp_path, selection)
    arm_dir = _write_arm(tmp_path / "arms", selection, 10000)
    rows = _arm_rows(selection, 10000)
    rows[0][field] = f"{rows[0][field]}.000000001"
    _resign_arm(arm_dir, rows)

    report = validate_certification_budget_arm(arm_dir, selection_path, STUDY_MANIFEST_PATH)

    assert report["valid"] is False
    assert field in report["error_message"]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("dataset_digest", "0" * 64, "dataset_digest"),
        ("data_seed", 999, "data_seed"),
        ("workflow_status", "error", "workflow_status"),
        ("observed_rho", None, "observed_rho"),
        ("scenario", "tampered", "pairing keys"),
        ("certification_combination_budget", 1000, "budget"),
        ("certification_failure_reason", "unexpected", "reason"),
    ],
)
def test_validator_rejects_resigned_row_tampering(
    tmp_path: Path,
    selection: dict[str, Any],
    field: str,
    value: object,
    message: str,
) -> None:
    selection_path = _write_selection(tmp_path, selection)
    arm_dir = _write_arm(tmp_path / "arms", selection, 5000)
    rows = _arm_rows(selection, 5000)
    rows[0][field] = value
    _resign_arm(arm_dir, rows)

    report = validate_certification_budget_arm(arm_dir, selection_path, STUDY_MANIFEST_PATH)

    assert report["valid"] is False
    assert message in report["error_message"]
    assert report["observed_cap_rows"] == {"cap3": 44, "cap4": 68}
    assert report["source_checksums"]["source_task25_manifest"] == (
        "b47842e33092b9431220204f46c77723f2465f86a1685e1cd1c90e601bedd4ff"
    )
    assert report["source_checksums"]["source_task24_manifest"] == (
        "415576f1fec5ccd2a47e0ad411d29e4d48c6e8e370609ae495ccc877fe74e974"
    )
    assert json.loads((arm_dir / "arm_validation.json").read_text()) == report


def test_validator_rejects_complete_arm_row_count_even_when_resigned(
    tmp_path: Path, selection: dict[str, Any]
) -> None:
    selection_path = _write_selection(tmp_path, selection)
    arm_dir = _write_arm(tmp_path / "arms", selection, 10000)
    rows = _arm_rows(selection, 10000)[:-1]
    _resign_arm(arm_dir, rows)

    report = validate_certification_budget_arm(arm_dir, selection_path, STUDY_MANIFEST_PATH)

    assert report["valid"] is False
    assert "row count" in report["error_message"]


def test_validator_rejects_artifact_checksum_tampering(
    tmp_path: Path, selection: dict[str, Any]
) -> None:
    selection_path = _write_selection(tmp_path, selection)
    arm_dir = _write_arm(tmp_path / "arms", selection, 20000)
    with (arm_dir / "results.csv").open("a", encoding="utf-8") as handle:
        handle.write("\n")

    report = validate_certification_budget_arm(arm_dir, selection_path, STUDY_MANIFEST_PATH)

    assert report["valid"] is False
    assert "checksum" in report["error_message"]


def test_aggregate_writes_deterministic_complete_bundle(
    tmp_path: Path, selection: dict[str, Any]
) -> None:
    selection_path = _write_selection(tmp_path, selection)
    arms_root = tmp_path / "arms"
    arm_dirs = {
        budget: _write_arm(arms_root, selection, budget)
        for budget in reversed(STUDY_MANIFEST["budget_grid"])
    }
    output = tmp_path / "aggregate"

    summary = aggregate_certification_budget_arms(
        arm_dirs, selection_path, STUDY_MANIFEST_PATH, output
    )

    assert summary["complete_sensitivity_result"] is True
    assert summary["observed_rows"] == 448
    assert summary["overlap_rows"] == 44
    assert summary["source_task25"]["manifest_checksum"] == (
        "b47842e33092b9431220204f46c77723f2465f86a1685e1cd1c90e601bedd4ff"
    )
    assert summary["source_task24"]["manifest_checksum"] == (
        "415576f1fec5ccd2a47e0ad411d29e4d48c6e8e370609ae495ccc877fe74e974"
    )
    assert set(summary["per_cap_per_budget"]) == {"cap3", "cap4"}
    assert summary["reason_counts"]["certified"] == 112
    with (output / "results.csv").open(newline="", encoding="utf-8") as handle:
        combined = list(csv.DictReader(handle))
    order = [
        (
            int(row["certification_combination_budget"]),
            int(row["search_cap"]),
            int(row["N"]),
            int(row["p"]),
            row["scenario"],
            int(row["parameter_id"]),
            int(row["replication"]),
        )
        for row in combined
    ]
    assert order == sorted(order)
    assert json.loads((output / "summary.json").read_text()) == summary
    assert json.loads((output / "selection_manifest.json").read_text()) == selection
    assert all((output / f"arm_status_{budget}.json").is_file() for budget in arm_dirs)
    assert summary["artifact_checksums"] == {
        "results.csv": _sha256(output / "results.csv"),
        "selection_manifest.json": _sha256(output / "selection_manifest.json"),
        "summary.md": _sha256(output / "summary.md"),
        "arm_status": {
            str(budget): _sha256(output / f"arm_status_{budget}.json")
            for budget in STUDY_MANIFEST["budget_grid"]
        },
    }
    markdown = (output / "summary.md").read_text(encoding="utf-8")
    for required in (
        "cap-3 and cap-4 denominators are separate and may overlap",
        "incomplete arms are not zero-yield evidence",
        "row-level budget exhaustion differs from arm timeout",
        "cap 2 remains the production baseline",
        "specified selected population and budget",
        "not a cap-promotion or production-budget decision",
    ):
        assert required in markdown


def test_aggregate_rejects_extra_csv_cell_and_writes_diagnostics(
    tmp_path: Path, selection: dict[str, Any]
) -> None:
    selection_path = _write_selection(tmp_path, selection)
    arms_root = tmp_path / "arms"
    arm_dirs = {
        budget: _write_arm(arms_root, selection, budget) for budget in STUDY_MANIFEST["budget_grid"]
    }
    malformed_arm = arm_dirs[10000]
    results_path = malformed_arm / "results.csv"
    with results_path.open(newline="", encoding="utf-8") as handle:
        csv_rows = list(csv.reader(handle))
    csv_rows[1].append("surplus")
    with results_path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(csv_rows)
    _resign_arm_artifacts(malformed_arm)
    output = tmp_path / "aggregate"

    summary = aggregate_certification_budget_arms(
        arm_dirs, selection_path, STUDY_MANIFEST_PATH, output
    )

    assert summary["complete_sensitivity_result"] is False
    assert summary["arm_statuses"]["10000"]["valid"] is False
    assert "extra cells" in summary["arm_statuses"]["10000"]["error_message"]
    assert (output / "summary.json").is_file()
    assert (output / "summary.md").is_file()


def test_aggregate_retains_diagnostics_for_missing_and_incomplete_arms(
    tmp_path: Path, selection: dict[str, Any]
) -> None:
    selection_path = _write_selection(tmp_path, selection)
    arms_root = tmp_path / "arms"
    arm_dirs = {
        1000: _write_arm(arms_root, selection, 1000),
        5000: _write_arm(arms_root, selection, 5000, arm_status="timeout", row_limit=7),
    }
    output = tmp_path / "aggregate"

    summary = aggregate_certification_budget_arms(
        arm_dirs, selection_path, STUDY_MANIFEST_PATH, output
    )

    assert summary["complete_sensitivity_result"] is False
    assert summary["observed_rows"] == 119
    assert summary["arm_statuses"]["5000"]["arm_status"] == "timeout"
    assert summary["arm_statuses"]["10000"]["arm_status"] == "missing"
    assert summary["per_cap_per_budget"]["cap3"]["5000"]["certification_yield"] is None
    assert (output / "summary.json").is_file()
    assert (output / "summary.md").is_file()
    for budget in STUDY_MANIFEST["budget_grid"]:
        status = json.loads((output / f"arm_status_{budget}.json").read_text())
        assert status["arm_status"] == summary["arm_statuses"][str(budget)]["arm_status"]


def test_aggregate_rejects_arm_mapped_to_the_wrong_budget_slot(
    tmp_path: Path, selection: dict[str, Any]
) -> None:
    selection_path = _write_selection(tmp_path, selection)
    arms_root = tmp_path / "arms"
    arm_dirs = {
        budget: _write_arm(arms_root, selection, budget) for budget in STUDY_MANIFEST["budget_grid"]
    }
    arm_dirs[1000] = arm_dirs[5000]
    output = tmp_path / "aggregate"

    summary = aggregate_certification_budget_arms(
        arm_dirs, selection_path, STUDY_MANIFEST_PATH, output
    )

    assert summary["complete_sensitivity_result"] is False
    assert summary["observed_rows"] == 336
    assert summary["arm_statuses"]["1000"]["valid"] is False
    assert (
        "does not match requested budget 1000" in summary["arm_statuses"]["1000"]["error_message"]
    )
    assert summary["per_cap_per_budget"]["cap3"]["1000"] is None


def test_cli_validation_and_aggregation_exit_nonzero_but_write_reports(
    tmp_path: Path,
    selection: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selection_path = _write_selection(tmp_path, selection)
    arms_root = tmp_path / "arms"
    arm_dir = _write_arm(arms_root, selection, 1000, arm_status="timeout", row_limit=7)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "summarize_certification_budget_sensitivity",
            "validate",
            str(arm_dir),
            str(selection_path),
            str(STUDY_MANIFEST_PATH),
        ],
    )
    with pytest.raises(SystemExit, match="1"):
        main()
    assert (arm_dir / "arm_validation.json").is_file()

    output = tmp_path / "aggregate"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "summarize_certification_budget_sensitivity",
            "aggregate",
            str(selection_path),
            str(arms_root),
            str(STUDY_MANIFEST_PATH),
            str(output),
        ],
    )
    with pytest.raises(SystemExit, match="1"):
        main()
    assert (output / "summary.json").is_file()
