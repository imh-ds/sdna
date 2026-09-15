"""Tests for the deterministic fixed-budget sensitivity arm runner."""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from simulations.full_workflow import dataset_digest, derive_workflow_seeds
from tools import run_certification_budget_sensitivity as runner
from tools.certification_budget_sensitivity_manifest import (
    load_certification_budget_sensitivity_manifest,
)
from tools.prepare_certification_budget_sensitivity import build_selection_manifest
from tools.run_cap_expansion import (
    CAP_EXPANSION_FIELDNAMES,
    CERTIFICATION_DIAGNOSTIC_FIELDNAMES,
)

SOURCE_CONFIG_PATH = Path("simulations/configs/cap_expansion_v1.json")
STUDY_CONFIG_PATH = Path(
    "simulations/configs/certification_budget_sensitivity_v1.json"
)
STUDY_MANIFEST = load_certification_budget_sensitivity_manifest(STUDY_CONFIG_PATH)


def _pair_key(row: dict[str, Any]) -> tuple[str, int, int, int, int]:
    return (
        str(row["scenario"]),
        int(row["N"]),
        int(row["p"]),
        int(row["parameter_id"]),
        int(row["replication"]),
    )


def _dataset(key: tuple[str, int, int, int, int]) -> SimpleNamespace:
    value = float(key[-1] + 1)
    return SimpleNamespace(X=np.array([[value, 0.0], [0.0, value]], dtype=float))


def _workflow_fields(budget: int) -> dict[str, Any]:
    return {
        "true_rho": 0.2,
        "observed_rho": 0.19,
        "lambda": 0.1,
        "contamination_count": 0,
        "contamination_status": 0,
        "greedy_fragility_50": 2,
        "exact_fragility_50": 2,
        "certified": True,
        "reached": True,
        "reference_tail_probability": 0.12,
        "reference_reached_fraction": 0.8,
        "wald_z": 1.25,
        "bootstrap_ci_excludes_zero": False,
        "bootstrap_rejected_resamples": 1,
        "influence_top_k_precision": None,
        "influence_top_k_recall": None,
        "first_planted_reciprocal_rank": None,
        "planted_absolute_influence_share": None,
        "fragility_status": "reached",
        "certification_status": "certified",
        "calibration_status": "right_censored",
        "wald_status": "ok",
        "bootstrap_status": "ok",
        "workflow_status": "ok",
        "error_stage": None,
        "error_type": None,
        "error_message": None,
        "certification_combinations_checked": 7,
        "certification_combination_budget": budget,
        "certification_budget_exhausted": False,
        "certification_failure_reason": "certified",
    }


def _source_row(
    arm: str,
    *,
    scenario: str,
    n: int,
    p: int,
    parameter_id: int,
    replication: int,
    fragility_status: str,
) -> dict[str, Any]:
    key = (scenario, n, p, parameter_id, replication)
    data_seed = 1000 + replication
    child_seeds = derive_workflow_seeds(data_seed)
    row = {
        "arm": arm,
        "scenario": scenario,
        "parameter_id": str(parameter_id),
        "parameter": "0.2",
        "replication": str(replication),
        "N": str(n),
        "p": str(p),
        "data_seed": str(data_seed),
        "calibration_seed": str(child_seeds.calibration),
        "bootstrap_seed": str(child_seeds.bootstrap),
        "dataset_digest": dataset_digest(_dataset(key)),
        "fragility_target": "0.5",
        "search_cap": str({"baseline_cap2": 2, "cap3": 3, "cap4": 4}[arm]),
        "calibration_require_reached": "False",
        **_workflow_fields(1000),
        "elapsed_seconds": "0.25",
    }
    row["fragility_status"] = fragility_status
    row["reached"] = fragility_status == "reached"
    return row


def _selection_rows() -> list[dict[str, Any]]:
    keys = [
        ("clean_planted_edge", 12, 3, 0, 0, True, True),
        ("heavy_tails", 13, 3, 1, 1, True, False),
        ("single_influential_case", 14, 3, 2, 2, False, True),
    ]
    rows: list[dict[str, Any]] = []
    for scenario, n, p, parameter_id, replication, cap3, cap4 in keys:
        common = {
            "scenario": scenario,
            "n": n,
            "p": p,
            "parameter_id": parameter_id,
            "replication": replication,
        }
        rows.append(_source_row("baseline_cap2", fragility_status="unreached", **common))
        rows.append(
            _source_row(
                "cap3",
                fragility_status="reached" if cap3 else "unreached",
                **common,
            )
        )
        rows.append(
            _source_row(
                "cap4",
                fragility_status="reached" if cap4 else "unreached",
                **common,
            )
        )
    return rows


def _write_selection_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, dict[str, Any]]:
    manifest = copy.deepcopy(STUDY_MANIFEST)
    manifest["expected_population_rows"] = {"cap3": 2, "cap4": 2}
    manifest["expected_rows_per_budget"] = 4
    selection = build_selection_manifest(_selection_rows(), manifest)
    path = tmp_path / "selection.json"
    path.write_text(json.dumps(selection), encoding="utf-8")
    monkeypatch.setattr(
        runner,
        "load_certification_budget_sensitivity_manifest",
        lambda _: copy.deepcopy(manifest),
    )
    return path, manifest


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _install_successful_workflow(
    monkeypatch: pytest.MonkeyPatch,
    *,
    calls: list[dict[str, Any]] | None = None,
) -> None:
    def deterministic_dataset(
        job: dict[str, Any], seed: int, manifest: dict[str, Any]
    ) -> SimpleNamespace:
        return _dataset(_pair_key(job))

    def deterministic_workflow(dataset: Any, **kwargs: Any) -> dict[str, Any]:
        if calls is not None:
            calls.append({"dataset": dataset, **kwargs})
        return _workflow_fields(int(kwargs["certification_combination_budget"]))

    monkeypatch.setattr(runner, "generate_cap_expansion_dataset", deterministic_dataset)
    monkeypatch.setattr(runner, "run_full_workflow", deterministic_workflow)


def test_runner_uses_one_dataset_per_pair_and_records_requested_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection_path, _ = _write_selection_fixture(tmp_path, monkeypatch)
    generated: list[tuple[dict[str, Any], int, dict[str, Any]]] = []
    calls: list[dict[str, Any]] = []

    def tracked_dataset(
        job: dict[str, Any], seed: int, manifest: dict[str, Any]
    ) -> SimpleNamespace:
        generated.append((job, seed, manifest))
        return _dataset(_pair_key(job))

    def tracked_workflow(dataset: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append({"dataset": dataset, **kwargs})
        return _workflow_fields(int(kwargs["certification_combination_budget"]))

    monkeypatch.setattr(runner, "generate_cap_expansion_dataset", tracked_dataset)
    monkeypatch.setattr(runner, "run_full_workflow", tracked_workflow)

    status = runner.run_certification_budget_arm(
        selection_path,
        SOURCE_CONFIG_PATH,
        STUDY_CONFIG_PATH,
        5000,
        tmp_path,
    )

    rows = _read_csv(tmp_path / "results.csv")
    with (tmp_path / "results.csv").open(newline="", encoding="utf-8") as handle:
        header = next(csv.reader(handle))
    assert status["arm_status"] == "complete"
    assert len(generated) == 3
    assert len(rows) == 4
    assert header == CAP_EXPANSION_FIELDNAMES + CERTIFICATION_DIAGNOSTIC_FIELDNAMES
    assert {int(row["certification_combination_budget"]) for row in rows} == {5000}
    assert {call["certification_combination_budget"] for call in calls} == {5000}
    assert calls[0]["dataset"] is calls[2]["dataset"]
    for job, _, _ in generated:
        assert all(
            isinstance(job[field], int)
            for field in ("parameter_id", "replication", "N", "p", "search_cap")
        )
        assert isinstance(job["parameter"], float)
        assert isinstance(job["target"], float)
    source_candidates = [
        entry["candidate"]
        for cap in ("cap3", "cap4")
        for entry in json.loads(selection_path.read_text(encoding="utf-8"))[
            "populations"
        ][cap]
    ]
    noncertification_fields = [
        field
        for field in CAP_EXPANSION_FIELDNAMES
        if field != "elapsed_seconds"
    ]
    for source, row in zip(source_candidates, rows, strict=True):
        assert {
            field: "" if source[field] is None else str(source[field])
            for field in noncertification_fields
        } == {field: row[field] for field in noncertification_fields}


def test_runner_checkpoints_complete_status_metadata_and_source_identities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection_path, manifest = _write_selection_fixture(tmp_path, monkeypatch)
    _install_successful_workflow(monkeypatch)
    output_dir = tmp_path / "arm"

    status = runner.run_certification_budget_arm(
        selection_path,
        SOURCE_CONFIG_PATH,
        STUDY_CONFIG_PATH,
        1000,
        output_dir,
    )

    persisted = json.loads((output_dir / "arm_status.json").read_text(encoding="utf-8"))
    metadata = json.loads(
        (output_dir / "results.metadata.json").read_text(encoding="utf-8")
    )
    assert status == persisted
    assert status["expected_rows"] == 4
    assert status["completed_rows"] == 4
    assert status["rows"] == 4
    assert status["observed_cap_rows"] == {"cap3": 2, "cap4": 2}
    assert status["arm_rows"] == {"cap3": 2, "cap4": 2}
    assert status["certification_budget_exhausted_rows"] == 0
    assert len(status["completed_keys"]) == 4
    assert status["last_completed_key"]["arm"] == "cap4"
    assert status["runtime_ceiling_seconds"] == 1800
    assert status["source_checksums"]["source_task25_manifest"] == (
        manifest["source_task25_manifest_checksum"]
    )
    assert status["source_checksums"]["source_task24_manifest"] == (
        manifest["source_task24_manifest_checksum"]
    )
    assert status["source_checksums"]["source_task25_manifest"] != (
        status["source_checksums"]["source_task24_manifest"]
    )
    assert set(status["environment"]) >= {
        "python_version",
        "numpy_version",
        "package_version",
        "platform",
    }
    assert set(status["artifact_checksums"]) == {
        "results.csv",
        "results.metadata.json",
    }
    assert metadata["artifact_checksums"]["results.csv"] == (
        status["artifact_checksums"]["results.csv"]
    )


def test_runner_times_out_between_rows_and_preserves_completed_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection_path, _ = _write_selection_fixture(tmp_path, monkeypatch)
    clock = SimpleNamespace(value=0.0)
    calls: list[dict[str, Any]] = []

    def deterministic_dataset(
        job: dict[str, Any], seed: int, manifest: dict[str, Any]
    ) -> SimpleNamespace:
        return _dataset(_pair_key(job))

    def timed_workflow(dataset: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        clock.value = 1800.0
        return _workflow_fields(int(kwargs["certification_combination_budget"]))

    monkeypatch.setattr(runner, "perf_counter", lambda: clock.value)
    monkeypatch.setattr(runner, "generate_cap_expansion_dataset", deterministic_dataset)
    monkeypatch.setattr(runner, "run_full_workflow", timed_workflow)
    output_dir = tmp_path / "timeout-arm"

    status = runner.run_certification_budget_arm(
        selection_path,
        SOURCE_CONFIG_PATH,
        STUDY_CONFIG_PATH,
        5000,
        output_dir,
    )

    rows = _read_csv(output_dir / "results.csv")
    assert status["arm_status"] == "timeout"
    assert len(rows) == 1
    assert len(calls) == 1
    assert status["completed_rows"] == 1
    assert status["last_completed_key"] == {
        "arm": "cap3",
        "scenario": "clean_planted_edge",
        "N": 12,
        "p": 3,
        "parameter_id": 0,
        "replication": 0,
    }


def test_runner_records_expected_dataset_generation_error_as_a_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection_path, _ = _write_selection_fixture(tmp_path, monkeypatch)

    def failing_dataset(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("synthetic data failure")

    monkeypatch.setattr(runner, "generate_cap_expansion_dataset", failing_dataset)
    output_dir = tmp_path / "data-error-arm"

    status = runner.run_certification_budget_arm(
        selection_path,
        SOURCE_CONFIG_PATH,
        STUDY_CONFIG_PATH,
        10000,
        output_dir,
    )

    rows = _read_csv(output_dir / "results.csv")
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    expected_digests = [
        entry["candidate"]["dataset_digest"]
        for cap in ("cap3", "cap4")
        for entry in selection["populations"][cap]
    ]
    assert status["arm_status"] == "complete"
    assert len(rows) == 4
    assert [row["dataset_digest"] for row in rows] == expected_digests
    assert {row["error_stage"] for row in rows} == {"data"}
    assert {row["workflow_status"] for row in rows} == {"error"}
    assert {row["certification_failure_reason"] for row in rows} == {
        "not_applicable_prior_error"
    }
    assert {row["certification_budget_exhausted"] for row in rows} == {"False"}


@pytest.mark.parametrize("exception_type", [TypeError, ValueError, RuntimeError])
def test_runner_marks_unexpected_exception_failed_without_synthetic_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exception_type: type[Exception],
) -> None:
    selection_path, _ = _write_selection_fixture(tmp_path, monkeypatch)
    _install_successful_workflow(monkeypatch)
    calls = 0

    def unexpected_workflow(dataset: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise exception_type("unexpected runner failure")
        return _workflow_fields(int(kwargs["certification_combination_budget"]))

    monkeypatch.setattr(runner, "run_full_workflow", unexpected_workflow)
    output_dir = tmp_path / "failed-arm"

    status = runner.run_certification_budget_arm(
        selection_path,
        SOURCE_CONFIG_PATH,
        STUDY_CONFIG_PATH,
        20000,
        output_dir,
    )

    rows = _read_csv(output_dir / "results.csv")
    assert status["arm_status"] == "failed"
    assert status["error_type"] == exception_type.__name__
    assert status["error_message"] == "unexpected runner failure"
    assert len(rows) == 1
    assert rows[0]["workflow_status"] == "ok"


@pytest.mark.parametrize("field", ["dataset_digest", "calibration_seed", "bootstrap_seed"])
def test_runner_rejects_source_provenance_mismatch_as_arm_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    selection_path, manifest = _write_selection_fixture(tmp_path, monkeypatch)
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    selection["populations"]["cap3"][0]["candidate"][field] = "0"
    unsigned = {
        key: value for key, value in selection.items() if key != "selection_checksum"
    }
    selection["selection_checksum"] = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    selection_path.write_text(json.dumps(selection), encoding="utf-8")
    monkeypatch.setattr(
        runner,
        "load_certification_budget_sensitivity_manifest",
        lambda _: copy.deepcopy(manifest),
    )
    _install_successful_workflow(monkeypatch)
    output_dir = tmp_path / f"mismatch-{field}"

    status = runner.run_certification_budget_arm(
        selection_path,
        SOURCE_CONFIG_PATH,
        STUDY_CONFIG_PATH,
        1000,
        output_dir,
    )

    assert status["arm_status"] == "failed"
    assert status["completed_rows"] == 0
    assert _read_csv(output_dir / "results.csv") == []


def test_budget_execution_order_does_not_change_noncertification_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection_path, _ = _write_selection_fixture(tmp_path, monkeypatch)
    _install_successful_workflow(monkeypatch)

    outputs: dict[tuple[str, int], list[dict[str, str]]] = {}
    for order_name, budgets in (("forward", (1000, 5000)), ("reverse", (5000, 1000))):
        for budget in budgets:
            output_dir = tmp_path / f"{order_name}-{budget}"
            status = runner.run_certification_budget_arm(
                selection_path,
                SOURCE_CONFIG_PATH,
                STUDY_CONFIG_PATH,
                budget,
                output_dir,
            )
            assert status["arm_status"] == "complete"
            outputs[(order_name, budget)] = _read_csv(output_dir / "results.csv")

    ignored = {*CERTIFICATION_DIAGNOSTIC_FIELDNAMES, "elapsed_seconds"}
    for budget in (1000, 5000):
        forward = outputs[("forward", budget)]
        reverse = outputs[("reverse", budget)]
        assert [
            {field: value for field, value in row.items() if field not in ignored}
            for row in forward
        ] == [
            {field: value for field, value in row.items() if field not in ignored}
            for row in reverse
        ]
        for field in (
            "data_seed",
            "calibration_seed",
            "bootstrap_seed",
            "dataset_digest",
        ):
            assert [row[field] for row in forward] == [row[field] for row in reverse]


@pytest.mark.parametrize(
    ("arm_status", "exit_code"),
    [("complete", 0), ("timeout", 1), ("failed", 1), ("incomplete", 1)],
)
def test_cli_exits_zero_only_for_a_complete_arm(
    monkeypatch: pytest.MonkeyPatch, arm_status: str, exit_code: int
) -> None:
    captured: dict[str, Any] = {}

    def fake_run(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"arm_status": arm_status}

    monkeypatch.setattr(runner, "run_certification_budget_arm", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_certification_budget_sensitivity",
            "selection.json",
            "source.json",
            "study.json",
            "5000",
            "arm-output",
        ],
    )

    with pytest.raises(SystemExit) as raised:
        runner.main()

    assert raised.value.code == exit_code
    assert captured == {
        "selection_manifest_path": Path("selection.json"),
        "source_manifest_path": Path("source.json"),
        "study_manifest_path": Path("study.json"),
        "budget": 5000,
        "output_dir": Path("arm-output"),
    }
