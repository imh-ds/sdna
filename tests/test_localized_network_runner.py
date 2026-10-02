"""Contract tests for the paired Task 27 runner."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pytest

from simulations.full_workflow import derive_workflow_seeds
from tools import run_localized_network as runner


CONFIG_PATH = Path(__file__).parents[1] / "simulations/configs/localized_network_v1.json"
CSV_FIELDS = [
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


def _workflow_result(dataset: Any) -> dict[str, Any]:
    return {
        "true_rho": float(dataset.partial_correlation[dataset.focal_edge]),
        "observed_rho": 0.1,
        "lambda": 0.0,
        "contamination_count": len(dataset.contaminated_cases),
        "contamination_status": int(bool(dataset.contaminated_cases)),
        "greedy_fragility_50": 1,
        "exact_fragility_50": 1,
        "certified": True,
        "reached": True,
        "certification_combinations_checked": 1,
        "certification_combination_budget": 1000,
        "certification_budget_exhausted": False,
        "certification_failure_reason": "certified",
        "reference_tail_probability": 0.5,
        "reference_reached_fraction": 1.0,
        "wald_z": 0.2,
        "bootstrap_ci_excludes_zero": False,
        "bootstrap_rejected_resamples": 0,
        "influence_top_k_precision": None,
        "influence_top_k_recall": None,
        "first_planted_reciprocal_rank": None,
        "planted_absolute_influence_share": None,
        "fragility_status": "reached",
        "certification_status": "certified",
        "calibration_status": "finite",
        "wald_status": "ok",
        "bootstrap_status": "ok",
        "workflow_status": "ok",
        "error_stage": None,
        "error_type": None,
        "error_message": None,
    }


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def test_runner_writes_exact_schema_and_paired_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[Any, dict[str, Any]]] = []

    def fake_workflow(dataset: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append((dataset, kwargs))
        return _workflow_result(dataset)

    monkeypatch.setattr(runner, "run_full_workflow", fake_workflow)
    output = tmp_path / "p20"
    status = runner.run_localized_network(CONFIG_PATH, output, 20)

    rows = _read_rows(output / "results.csv")
    assert list(rows[0]) == CSV_FIELDS
    assert len(rows) == 540
    assert {int(row["p"]) for row in rows} == {20}
    assert status["status"] == "complete"
    assert status["expected_rows"] == status["completed_rows"] == 540

    by_key: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = tuple(row[field] for field in ("N", "p", "focal_context", "condition", "replication"))
        by_key[key].append(row)
        assert row["calibration_require_reached"] == "false"
        assert json.loads(row["planted_case_indices"]) == sorted(
            json.loads(row["planted_case_indices"])
        )
        assert float(row["true_rho"]) == pytest.approx(0.05)
        assert int(row["contamination_count"]) == len(json.loads(row["planted_case_indices"]))
        assert int(row["contamination_status"]) == int(int(row["contamination_count"]) > 0)

    assert len(by_key) == 270
    for pair in by_key.values():
        assert len(pair) == 2
        assert {row["arm"] for row in pair} == {"baseline_cap2", "diagnostic_cap4"}
        assert len({row["dataset_digest"] for row in pair}) == 1
        assert len({row["data_seed"] for row in pair}) == 1
        assert len({row["calibration_seed"] for row in pair}) == 1
        assert len({row["bootstrap_seed"] for row in pair}) == 1

    by_data_key: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_data_key[(row["N"], row["p"], row["condition"], row["replication"])].append(row)
    for contexts in by_data_key.values():
        assert len(contexts) == 6
        assert len({row["data_seed"] for row in contexts}) == 1
        assert len({row["calibration_seed"] for row in contexts}) == 1
        assert len({row["bootstrap_seed"] for row in contexts}) == 1
        assert len({row["planted_case_indices"] for row in contexts}) == 1
        if contexts[0]["condition"] == "clean":
            assert len({row["dataset_digest"] for row in contexts}) == 1

    seeds_by_data_seed: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in rows:
        seeds_by_data_seed[row["data_seed"]].add((row["calibration_seed"], row["bootstrap_seed"]))
    assert all(len(seed_pairs) == 1 for seed_pairs in seeds_by_data_seed.values())
    for data_seed, seed_pairs in seeds_by_data_seed.items():
        seeds = derive_workflow_seeds(int(data_seed))
        assert seed_pairs == {(str(seeds.calibration), str(seeds.bootstrap))}
    assert len(calls) == 540  # one workflow per arm; datasets are generated once per context pair
    expected_seed_pairs = {
        derive_workflow_seeds(int(row["data_seed"])) for row in rows
    }
    assert {kwargs["seeds"] for _dataset, kwargs in calls} <= expected_seed_pairs
    assert len({kwargs["seeds"] for _dataset, kwargs in calls}) == 90
    for _dataset, kwargs in calls:
        assert kwargs["calibration_require_reached"] is False
        assert kwargs["calibration_simulations"] == 25
        assert kwargs["bootstrap_samples"] == 100
        assert kwargs["certification_combination_budget"] == 1000

    metadata = json.loads((output / "results.metadata.json").read_text(encoding="utf-8"))
    assert metadata["manifest_checksum"]
    assert metadata["git_commit"]
    assert metadata["p_shard"] == 20
    assert set(metadata["files"]) >= {"results.csv", "shard_status.json"}
    for filename, expected_digest in metadata["files"].items():
        assert hashlib.sha256((output / filename).read_bytes()).hexdigest() == expected_digest


def test_interruption_keeps_completed_rows_and_incomplete_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def interrupted_workflow(dataset: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise KeyboardInterrupt("injected interruption")
        return _workflow_result(dataset)

    monkeypatch.setattr(runner, "run_full_workflow", interrupted_workflow)
    output = tmp_path / "interrupted"

    with pytest.raises(KeyboardInterrupt, match="injected interruption"):
        runner.run_localized_network(CONFIG_PATH, output, 20)

    rows = _read_rows(output / "results.csv")
    status = json.loads((output / "shard_status.json").read_text(encoding="utf-8"))
    assert len(rows) == 2
    assert {row["workflow_status"] for row in rows} == {"ok"}
    assert status["status"] == "incomplete"
    assert status["completed_rows"] == 2
    assert status["expected_rows"] == 540


@pytest.mark.parametrize("tamper", ["commit", "results_checksum"])
def test_resume_rejects_incompatible_checkpoint_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tamper: str
) -> None:
    calls = 0

    def interrupted_workflow(dataset: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt("injected interruption")
        return _workflow_result(dataset)

    monkeypatch.setattr(runner, "_git_commit", lambda: "commit-a")
    monkeypatch.setattr(runner, "run_full_workflow", interrupted_workflow)
    output = tmp_path / f"provenance-{tamper}"
    with pytest.raises(KeyboardInterrupt, match="injected interruption"):
        runner.run_localized_network(CONFIG_PATH, output, 20)

    if tamper == "commit":
        monkeypatch.setattr(runner, "_git_commit", lambda: "commit-b")
    else:
        rows = _read_rows(output / "results.csv")
        rows[0]["true_rho"] = "0.06"
        with (output / "results.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    monkeypatch.setattr(
        runner,
        "run_full_workflow",
        lambda dataset, **kwargs: _workflow_result(dataset),
    )
    with pytest.raises(ValueError, match="provenance|checksum"):
        runner.run_localized_network(CONFIG_PATH, output, 20)


def test_generation_and_workflow_errors_are_rows_and_shard_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_generate = runner.generate_localized_dataset
    generation_failed = False

    def sometimes_generate(n: int, p: int, context: str, condition: str, seed: int) -> Any:
        nonlocal generation_failed
        if not generation_failed:
            generation_failed = True
            raise RuntimeError("injected generation error")
        return original_generate(n, p, context, condition, seed)

    workflow_calls = 0

    def sometimes_workflow(dataset: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal workflow_calls
        workflow_calls += 1
        if workflow_calls == 1:
            raise ValueError("injected workflow error")
        return _workflow_result(dataset)

    monkeypatch.setattr(runner, "generate_localized_dataset", sometimes_generate)
    monkeypatch.setattr(runner, "run_full_workflow", sometimes_workflow)
    output = tmp_path / "errors"
    status = runner.run_localized_network(CONFIG_PATH, output, 20)
    rows = _read_rows(output / "results.csv")

    errors = [row for row in rows if row["workflow_status"] == "error"]
    assert len(rows) == 540
    assert len(errors) == 3  # two paired generation errors and one workflow error
    assert Counter(row["error_stage"] for row in errors) == {"generation": 2, "workflow": 1}
    generation_errors = [row for row in errors if row["error_stage"] == "generation"]
    assert all(row["planted_case_indices"] == "" for row in generation_errors)
    assert all(row["contamination_count"] == "" for row in generation_errors)
    assert status["status"] == "complete"
    assert status["completed_rows"] == 540
    assert any(row["workflow_status"] == "ok" for row in rows)


def test_runtime_ceiling_is_reported_without_dropping_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "run_full_workflow", lambda dataset, **kwargs: _workflow_result(dataset))
    ticks = iter([0.0, 0.0, 0.0, 0.0, 0.0, 3601.0])
    monkeypatch.setattr(runner.time, "monotonic", lambda: next(ticks, 3601.0))

    status = runner.run_localized_network(CONFIG_PATH, tmp_path / "timed", 20)

    assert status["status"] == "runtime_ceiling_exceeded"
    assert status["runtime_ceiling_exceeded"] is True
    assert len(_read_rows(tmp_path / "timed/results.csv")) == 2


def test_cli_accepts_config_output_and_p_shard(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[tuple[str, str, int | None]] = []

    def fake_run(config: str, output: str, p_shard: int | None) -> dict[str, Any]:
        calls.append((config, output, p_shard))
        return {"status": "complete", "completed_rows": 540}

    monkeypatch.setattr(runner, "run_localized_network", fake_run)

    result = runner.main(["--config", "manifest.json", "--output-dir", "shard-40", "--p-shard", "40"])

    assert result == 0
    assert calls == [("manifest.json", "shard-40", 40)]
    assert json.loads(capsys.readouterr().out) == {"status": "complete", "completed_rows": 540}
