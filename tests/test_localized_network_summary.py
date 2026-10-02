"""Contract tests for Task 27 localized-network artifact summaries."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from pathlib import Path

import pytest

from simulations.localized_network_dgp import build_localized_population
from simulations.full_workflow import derive_workflow_seeds
from tools import run_localized_network as runner
from tools.run_localized_network import RESULT_FIELDNAMES
from tools.localized_network_manifest import (
    expand_localized_jobs,
    load_localized_manifest,
    localized_manifest_checksum,
)
from tools.summarize_localized_network import FIELDNAMES as SUMMARY_FIELDS
from tools.summarize_localized_network import main as summary_main
from tools.summarize_localized_network import (
    compare_localized_network_rerun,
    summarize_localized_network,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "simulations" / "configs" / "localized_network_v1.json"
FIELDS = (
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


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _refresh_metadata(shard: Path) -> None:
    status_path = shard / "shard_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    with (shard / "results.csv").open(newline="", encoding="utf-8") as handle:
        status["completed_rows"] = sum(1 for _ in csv.DictReader(handle))
    status_path.write_text(json.dumps(status), encoding="utf-8")
    metadata_path = shard / "results.metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["files"] = {
        "results.csv": _sha(shard / "results.csv"),
        "shard_status.json": _sha(shard / "shard_status.json"),
    }
    if (shard / "github-run.txt").is_file():
        metadata["files"]["github-run.txt"] = _sha(shard / "github-run.txt")
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")


def _make_shards(root: Path, *, outcome: str = "clean", run_id: str = "1001") -> list[Path]:
    manifest = load_localized_manifest(CONFIG)
    jobs = expand_localized_jobs(manifest)
    population_by_p = {p: build_localized_population(p) for p in manifest["p_values"]}
    output: list[Path] = []
    for p in manifest["p_values"]:
        shard = root / f"p-{p}"
        shard.mkdir(parents=True)
        rows: list[dict[str, object]] = []
        for job in jobs:
            if job["p"] != p:
                continue
            pop = population_by_p[p]
            focal_i, focal_j = pop.focal_edges[job["focal_context"]]
            contaminated = job["condition"] != "clean"
            stages = {
                "fragility_status": "reached",
                "certification_status": "certified",
                "calibration_status": "finite",
                "wald_status": "ok",
                "bootstrap_status": "ok",
                "workflow_status": "ok",
            }
            generation_failed = (
                outcome == "generation_error"
                and job["N"] == 50 and p == 20
                and job["condition"] == "coalition" and job["replication"] == 0
            )
            if generation_failed:
                stages.update(
                    fragility_status="error",
                    certification_status="error",
                    calibration_status="error",
                    wald_status="error",
                    bootstrap_status="error",
                    workflow_status="error",
                )
            if outcome == "mixed":
                if job["replication"] == 0:
                    stages.update(
                        fragility_status="unreached",
                        certification_status="skipped_unreached",
                        calibration_status="observed_unreached",
                        workflow_status="partial",
                    )
                elif job["replication"] == 1:
                    stages.update(
                        fragility_status="error",
                        certification_status="error",
                        calibration_status="error",
                        workflow_status="error",
                    )
                elif job["replication"] == 2:
                    stages.update(
                        certification_status="not_certified",
                        certification_budget_exhausted="true",
                    )
            seeds = derive_workflow_seeds(job["data_seed"])
            planted = list(range({"clean": 0, "single_case": 1, "coalition": 3}[job["condition"]]))
            row: dict[str, object] = {
                **{field: job[field] for field in (
                    "arm", "N", "p", "focal_context", "condition", "replication", "data_seed"
                )},
                "N": job["N"],
                "data_seed": job["data_seed"],
                "calibration_seed": seeds.calibration,
                "bootstrap_seed": seeds.bootstrap,
                "dataset_digest": hashlib.sha256(
                    (
                        f"{job['N']}:{p}:{job['condition']}:{job['replication']}"
                        + (f":{job['focal_context']}" if contaminated else "")
                    ).encode()
                ).hexdigest(),
                "focal_i": focal_i,
                "focal_j": focal_j,
                "planted_case_indices": json.dumps(planted, separators=(",", ":")),
                "module_count": p // 5,
                "true_rho": float(pop.partial_correlation[focal_i, focal_j]),
                "observed_rho": 0.04,
                "lambda": 0.1,
                "condition_number": 42.0,
                "contamination_count": len(planted),
                "contamination_status": int(contaminated),
                "fragility_target": job["target"],
                "search_cap": job["search_cap"],
                "calibration_require_reached": "false",
                "greedy_fragility_50": 0.1,
                "exact_fragility_50": 0.1,
                "certified": "true",
                "reached": "true",
                "certification_combinations_checked": 10,
                "certification_combination_budget": 1000,
                "certification_budget_exhausted": "false",
                "certification_failure_reason": "",
                "reference_tail_probability": "0.01" if not contaminated else "0.5",
                "reference_reached_fraction": 1.0,
                "wald_z": 1.0,
                "bootstrap_ci_excludes_zero": "false",
                "bootstrap_rejected_resamples": 0,
                "influence_top_k_precision": 1.0 if contaminated else "",
                "influence_top_k_recall": 1.0 if contaminated else "",
                "first_planted_reciprocal_rank": 1.0 if contaminated else "",
                "planted_absolute_influence_share": 0.5 if contaminated else "",
                "error_stage": "",
                "error_type": "",
                "error_message": "",
                "elapsed_seconds": 0.25,
                **stages,
            }
            if outcome == "mixed" and job["replication"] in {0, 1}:
                row.update(
                    reached="false",
                    certified="false",
                    reference_tail_probability="",
                    reference_reached_fraction="",
                    wald_z="",
                    bootstrap_ci_excludes_zero="",
                    bootstrap_rejected_resamples="",
                influence_top_k_precision="",
                influence_top_k_recall="",
                first_planted_reciprocal_rank="",
                planted_absolute_influence_share="",
                )
                if job["replication"] == 1:
                    row.update(
                        reached="",
                        certified="",
                        error_stage="fragility",
                        error_type="RuntimeError",
                        error_message="fixture error",
                    )
            if outcome == "mixed" and job["replication"] == 2:
                row.update(certified="false")
            if generation_failed:
                row.update(
                    dataset_digest="",
                    planted_case_indices="",
                    contamination_count="",
                    contamination_status="",
                    observed_rho="",
                    **{"lambda": ""},
                    condition_number="",
                    certified="",
                    reached="",
                    certification_combinations_checked="",
                    reference_tail_probability="",
                    reference_reached_fraction="",
                    wald_z="",
                    bootstrap_ci_excludes_zero="",
                    bootstrap_rejected_resamples="",
                    influence_top_k_precision="",
                    influence_top_k_recall="",
                    first_planted_reciprocal_rank="",
                    planted_absolute_influence_share="",
                    error_stage="generation",
                    error_type="RuntimeError",
                    error_message="fixture generation error",
                )
            rows.append(row)
        results = shard / "results.csv"
        with results.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        status = {
            "p_shard": p,
            "status": "complete",
            "expected_rows": 540,
            "completed_rows": 540,
            "runtime_ceiling_seconds": manifest["operational_runtime_ceiling_seconds"],
            "runtime_ceiling_exceeded": False,
            "elapsed_seconds": 1.0,
            "started_at_utc": "2026-10-02T00:00:00+00:00",
        }
        (shard / "shard_status.json").write_text(json.dumps(status), encoding="utf-8")
        (shard / "github-run.txt").write_text(
            f"workflow=SDNA localized-network operating-envelope study\n"
            f"run_id={run_id}\np_shard={p}\nref=refs/heads/codex/task-27-localized-envelope\n"
            f"sha={'a' * 40}\n",
            encoding="utf-8",
        )
        metadata = {
            "study": manifest["study"],
            "git_commit": "a" * 40,
            "python_version": "3.11.0",
            "numpy_version": "2.0.0",
            "package_version": "0.1.0",
            "manifest_checksum": localized_manifest_checksum(manifest),
            "p_shard": p,
            "started_at_utc": "2026-10-02T00:00:00+00:00",
            "updated_at_utc": "2026-10-02T00:00:01+00:00",
            "files": {
                "results.csv": _sha(results),
                "shard_status.json": _sha(shard / "shard_status.json"),
                "github-run.txt": _sha(shard / "github-run.txt"),
            },
        }
        (shard / "results.metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        output.append(shard)
    return output


def _copy_shards(shards: list[Path], root: Path) -> list[Path]:
    root.mkdir(parents=True, exist_ok=True)
    copies = [Path(shutil.copytree(shard, root / shard.name)) for shard in shards]
    for shard in copies:
        run_path = shard / "github-run.txt"
        contents = run_path.read_text(encoding="utf-8").replace("run_id=1001", "run_id=1002")
        run_path.write_text(contents, encoding="utf-8")
        _refresh_metadata(shard)
    return copies


def test_summary_csv_schema_matches_the_committed_task3_runner() -> None:
    assert SUMMARY_FIELDS == RESULT_FIELDNAMES


def test_cli_writes_summary_for_runner_shard_arguments(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shards = _make_shards(tmp_path / "shards")
    matched_rerun = _copy_shards(shards, tmp_path / "matched-rerun")
    arguments = ["summarize_localized_network.py", "--config", str(CONFIG), "--output-dir", str(tmp_path / "cli-summary")]
    for shard in shards:
        arguments.extend(("--shard", str(shard)))
    for shard in matched_rerun:
        arguments.extend(("--matched-rerun-shard", str(shard)))
    monkeypatch.setattr("sys.argv", arguments)
    summary_main()
    assert (tmp_path / "cli-summary" / "summary.json").is_file()
    assert (tmp_path / "cli-summary" / "summary.md").is_file()


def test_cli_accepts_complete_baseline_while_marking_rerun_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shards = _make_shards(tmp_path / "shards")
    arguments = [
        "summarize_localized_network.py", "--config", str(CONFIG),
        "--output-dir", str(tmp_path / "cli-summary"),
    ]
    for shard in shards:
        arguments.extend(("--shard", str(shard)))
    monkeypatch.setattr("sys.argv", arguments)

    summary_main()

    report = json.loads((tmp_path / "cli-summary" / "summary.json").read_text(encoding="utf-8"))
    assert report["acceptance_status"] == "awaiting_matched_rerun"


def test_full_shards_report_denominators_wilson_intervals_and_nulls(tmp_path: Path) -> None:
    shards = _make_shards(tmp_path / "shards")
    matched_rerun = _copy_shards(shards, tmp_path / "matched-rerun")
    report = summarize_localized_network(
        shards, CONFIG, tmp_path / "summary", matched_rerun_shard_dirs=matched_rerun
    )
    assert report["acceptance_status"] == "complete"
    assert report["schema_version"] == 2
    assert report["valid_rows"] == 1620
    cell = report["cells"][0]
    assert cell["reached_rate"]["numerator"] == 10
    assert cell["reached_rate"]["denominator"] == 10
    assert cell["reached_rate"]["estimate"] == 1.0
    assert cell["reached_rate"]["wilson_95"][0] == pytest.approx(0.722, abs=0.002)
    assert cell["reached_rate"]["wilson_95"][1] == pytest.approx(1.0)
    assert cell["clean_false_flag_rate"]["denominator"] == 10
    assert cell["shrinkage"] == {
        "mean": 0.1, "minimum": 0.1, "maximum": 0.1,
        "valid_rows": 10, "scheduled_rows": 10,
    }
    assert cell["condition_number"] == {
        "mean": 42.0, "minimum": 42.0, "maximum": 42.0,
        "valid_rows": 10, "scheduled_rows": 10,
    }
    assert "Condition number mean" in (tmp_path / "summary" / "summary.md").read_text(
        encoding="utf-8"
    )
    assert cell["influence_top_k_precision"]["valid_rows"] == 0
    assert cell["influence_top_k_precision"]["scheduled_rows"] == 0
    assert cell["influence_top_k_precision"]["mean"] is None
    assert (tmp_path / "summary" / "summary.json").is_file()
    assert (tmp_path / "summary" / "summary.md").is_file()


def test_complete_matrix_waits_for_matched_rerun_before_acceptance(tmp_path: Path) -> None:
    shards = _make_shards(tmp_path / "shards")
    report = summarize_localized_network(shards, CONFIG, tmp_path / "summary")

    assert report["acceptance_status"] == "awaiting_matched_rerun"
    assert report["matched_rerun"]["status"] == "not_provided"


def test_error_unreached_and_certification_exhaustion_are_separate(tmp_path: Path) -> None:
    shards = _make_shards(tmp_path / "shards", outcome="mixed")
    report = summarize_localized_network(shards, CONFIG, tmp_path / "summary")
    cell = next(c for c in report["cells"] if c["condition"] == "clean" and c["replication_count"] == 10)
    assert cell["scheduled_rows"] == 10
    assert cell["unreached_rows"] == 1
    assert cell["fragility_error_rows"] == 1
    assert cell["certification_budget_exhausted_rows"] == 1


def test_generation_error_rows_remain_valid_scheduled_outcomes(tmp_path: Path) -> None:
    shards = _make_shards(tmp_path / "shards", outcome="generation_error")
    matched_rerun = _copy_shards(shards, tmp_path / "matched-rerun")
    report = summarize_localized_network(
        shards, CONFIG, tmp_path / "summary", matched_rerun_shard_dirs=matched_rerun
    )
    assert report["acceptance_status"] == "complete"
    assert report["valid_rows"] == 1620
    assert report["overall"]["workflow_status_counts"]["error"] == 6


def test_influence_stage_errors_remain_valid_scheduled_outcomes(tmp_path: Path) -> None:
    shards = _make_shards(tmp_path / "shards")
    results_path = shards[0] / "results.csv"
    with results_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if (
            row["N"] == "50"
            and row["p"] == "20"
            and row["focal_context"] == "within_community"
            and row["condition"] == "single_case"
            and row["replication"] == "0"
        ):
            row.update(
                workflow_status="error",
                error_stage="influence",
                error_type="RuntimeError",
                error_message="injected influence failure",
                    influence_top_k_precision="",
                    influence_top_k_recall="",
                    first_planted_reciprocal_rank="",
                    planted_absolute_influence_share="",
            )
    with results_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    _refresh_metadata(shards[0])
    matched_rerun = _copy_shards(shards, tmp_path / "matched-rerun")

    report = summarize_localized_network(
        shards, CONFIG, tmp_path / "summary", matched_rerun_shard_dirs=matched_rerun
    )

    assert report["acceptance_status"] == "complete", report["shard_issues"]
    assert report["valid_rows"] == 1620
    assert report["overall"]["workflow_status_counts"]["error"] == 2
    assert not any(issue["p"] == 20 for issue in report["shard_issues"])


def test_matched_rerun_compares_deterministic_fields_but_ignores_timing(
    tmp_path: Path,
) -> None:
    primary = _make_shards(tmp_path / "primary")
    rerun = _make_shards(tmp_path / "rerun", run_id="1002")
    for shard in rerun:
        results_path = shard / "results.csv"
        with results_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            row["elapsed_seconds"] = "999.0"
        with results_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        _refresh_metadata(shard)

    result = compare_localized_network_rerun(primary, rerun, CONFIG)

    assert result["status"] == "matched"
    assert result["compared_rows"] == 1620
    assert result["mismatches"] == []
    assert result["primary_run_id"] == "1001"
    assert result["rerun_run_id"] == "1002"


def test_matched_rerun_rejects_changed_deterministic_result(tmp_path: Path) -> None:
    primary = _make_shards(tmp_path / "primary")
    rerun = _make_shards(tmp_path / "rerun", run_id="1002")
    results_path = rerun[0] / "results.csv"
    with results_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["observed_rho"] = "0.123"
    with results_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    _refresh_metadata(rerun[0])

    result = compare_localized_network_rerun(primary, rerun, CONFIG)

    assert result["status"] == "mismatch"
    assert result["compared_rows"] == 1620
    assert any(item["field"] == "observed_rho" for item in result["mismatches"])
    report = summarize_localized_network(
        primary, CONFIG, tmp_path / "summary", matched_rerun_shard_dirs=rerun
    )
    assert report["acceptance_status"] == "incomplete"
    assert report["matched_rerun"]["status"] == "mismatch"


def test_matched_rerun_requires_distinct_github_run_ids(tmp_path: Path) -> None:
    primary = _make_shards(tmp_path / "primary", run_id="1001")
    copied_artifacts = _make_shards(tmp_path / "copied", run_id="1001")

    result = compare_localized_network_rerun(primary, copied_artifacts, CONFIG)

    assert result["status"] == "invalid"
    assert "distinct GitHub Actions run IDs" in result["issues"][0]


def test_summarizer_accepts_actual_runner_generation_error_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_generation(*args: object, **kwargs: object) -> object:
        raise RuntimeError("injected generation failure")

    monkeypatch.setattr(runner, "generate_localized_dataset", fail_generation)
    output = tmp_path / "runner-p20"
    status = runner.run_localized_network(CONFIG, output, 20)
    report = summarize_localized_network([output], CONFIG, tmp_path / "summary")

    assert status["status"] == "complete"
    assert report["acceptance_status"] == "incomplete"  # p=40 and p=60 are absent
    assert report["valid_rows"] == 540
    assert report["overall"]["workflow_status_counts"] == {"error": 540}
    assert not any(issue["p"] == 20 for issue in report["shard_issues"])


@pytest.mark.parametrize("mutation", [
    "missing_shard", "duplicate", "missing_arm", "seed", "digest", "truth",
    "case_json", "checksum", "commit_format", "commit_mismatch", "condition_number",
    "influence_error_metrics", "missing_condition_number", "shrinkage_range",
    "generation_error_digest",
])
def test_invalid_or_missing_artifacts_cannot_be_accepted_complete(tmp_path: Path, mutation: str) -> None:
    shards = _make_shards(
        tmp_path / "shards",
        outcome="clean",
    )
    if mutation == "missing_shard":
        shards = shards[:2]
    elif mutation in {"commit_format", "commit_mismatch"}:
        changed_shards = shards if mutation == "commit_format" else shards[:1]
        for shard in changed_shards:
            metadata_path = shard / "results.metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["git_commit"] = (
                "placeholder" if mutation == "commit_format" else "b" * 40
            )
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    elif mutation == "generation_error_digest":
        target = shards[0] / "results.csv"
        with target.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        for generation_row in rows:
            if not (
                generation_row["N"] == "50"
                and generation_row["condition"] == "clean"
                and generation_row["replication"] == "0"
            ):
                continue
            generation_row.update(
                dataset_digest="f" * 64,
                planted_case_indices="",
                contamination_count="",
                contamination_status="",
                observed_rho="",
                **{"lambda": ""},
                condition_number="",
                greedy_fragility_50="",
                exact_fragility_50="",
                certified="",
                reached="",
                certification_combinations_checked="",
                certification_budget_exhausted="",
                certification_failure_reason="",
                reference_tail_probability="",
                reference_reached_fraction="",
                wald_z="",
                bootstrap_ci_excludes_zero="",
                bootstrap_rejected_resamples="",
                influence_top_k_precision="",
                influence_top_k_recall="",
                first_planted_reciprocal_rank="",
                planted_absolute_influence_share="",
                fragility_status="error",
                certification_status="error",
                calibration_status="error",
                wald_status="error",
                bootstrap_status="error",
                workflow_status="error",
                error_stage="generation",
                error_type="RuntimeError",
                error_message="fixture generation error",
            )
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        _refresh_metadata(shards[0])
    else:
        target = shards[0] / "results.csv"
        with target.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if mutation == "duplicate":
            rows.append(dict(rows[0]))
        elif mutation == "missing_arm":
            rows = [r for r in rows if r["arm"] != "diagnostic_cap4" or r["replication"] != "0"]
        elif mutation in {"seed", "digest", "truth", "case_json"}:
            rows[0][{"seed": "calibration_seed", "digest": "dataset_digest", "truth": "true_rho", "case_json": "planted_case_indices"}[mutation]] = {
                "seed": "7", "digest": "f" * 64, "truth": "0.2", "case_json": "not-json"
            }[mutation]
        elif mutation == "condition_number":
            rows[0]["condition_number"] = "0"
        elif mutation == "missing_condition_number":
            rows[0]["condition_number"] = ""
        elif mutation == "shrinkage_range":
            rows[0]["lambda"] = "1.5"
        elif mutation == "influence_error_metrics":
            for row in rows:
                if (
                    row["N"] == "50"
                    and row["condition"] == "single_case"
                    and row["focal_context"] == "within_community"
                    and row["replication"] == "0"
                ):
                    row.update(
                        workflow_status="error",
                        error_stage="influence",
                        error_type="RuntimeError",
                        error_message="injected influence failure",
                    )
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        if mutation in {"duplicate", "missing_arm"}:
            status_path = shards[0] / "shard_status.json"
            status = json.loads(status_path.read_text(encoding="utf-8"))
            status["status"] = "incomplete"
            status_path.write_text(json.dumps(status), encoding="utf-8")
        if mutation == "checksum":
            with target.open("a", encoding="utf-8") as handle:
                handle.write("\n")
        if mutation != "checksum":
            _refresh_metadata(shards[0])
    report = summarize_localized_network(shards, CONFIG, tmp_path / "summary")
    assert report["acceptance_status"] == "incomplete"
    if mutation == "commit_format":
        assert any("git_commit" in item["reason"] for item in report["shard_issues"])
    elif mutation == "commit_mismatch":
        assert report["valid_rows"] == 1620
        assert any("provenance differs" in item["reason"] for item in report["shard_issues"])
    elif mutation == "generation_error_digest":
        assert any("generation errors must not claim a dataset digest" in item["reason"] for item in report["shard_issues"])
    elif mutation == "condition_number":
        assert any("condition_number must be positive" in item["reason"] for item in report["shard_issues"])
    elif mutation == "missing_condition_number":
        assert any("successful fits require numerical diagnostics" in item["reason"] for item in report["shard_issues"])
    elif mutation == "shrinkage_range":
        assert any("lambda must be within [0, 1]" in item["reason"] for item in report["shard_issues"])
    elif mutation == "influence_error_metrics":
        assert any("influence errors must not contain influence metrics" in item["reason"] for item in report["shard_issues"])
    elif mutation == "duplicate":
        assert report["valid_rows"] == 1620
        assert report["duplicate_arm_pairing_rows"] == 1
    else:
        assert report["valid_rows"] < 1620
    assert (tmp_path / "summary" / "summary.json").is_file()
    if mutation == "missing_shard":
        empty_cell = next(
            cell for cell in report["cells"]
            if cell["N"] == 50 and cell["p"] == 60
            and cell["focal_context"] == "within_community"
            and cell["condition"] == "clean" and cell["arm"] == "baseline_cap2"
        )
        assert empty_cell["scheduled_rows"] == 10
        assert empty_cell["available_rows"] == 0
        assert empty_cell["reached_rate"]["estimate"] is None
        assert empty_cell["reached_rate"]["wilson_95"] is None


def test_clean_false_flags_exclude_invalid_reference_probabilities(tmp_path: Path) -> None:
    shards = _make_shards(tmp_path / "shards")
    matched_rerun = _copy_shards(shards, tmp_path / "matched-rerun")
    target = shards[0] / "results.csv"
    with target.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    clean = next(
        row for row in rows
        if row["N"] == "50" and row["p"] == "20"
        and row["focal_context"] == "within_community"
        and row["condition"] == "clean" and row["arm"] == "baseline_cap2"
    )
    clean["reference_tail_probability"] = "nan"
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    _refresh_metadata(shards[0])
    report = summarize_localized_network(
        shards, CONFIG, tmp_path / "summary", matched_rerun_shard_dirs=matched_rerun
    )
    cell = next(
        c for c in report["cells"]
        if c["condition"] == "clean" and c["N"] == 50 and c["p"] == 20
        and c["focal_context"] == "within_community" and c["arm"] == "baseline_cap2"
    )
    assert cell["clean_false_flag_rate"]["denominator"] == 9
    assert cell["clean_invalid_reference_rows"] == 1


def test_partial_timeout_shard_writes_summary_for_available_valid_rows(tmp_path: Path) -> None:
    shards = _make_shards(tmp_path / "shards")
    results_path = shards[2] / "results.csv"
    with results_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows = rows[:500]
    with results_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    status_path = shards[2] / "shard_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status.update(status="incomplete", completed_rows=500)
    status_path.write_text(json.dumps(status), encoding="utf-8")
    _refresh_metadata(shards[2])
    report = summarize_localized_network(shards, CONFIG, tmp_path / "summary")
    assert report["acceptance_status"] == "incomplete"
    assert report["valid_rows"] == 1580
    assert report["available_rows"] == 1580
    assert report["incomplete_shards"] == [60]
    assert math.isfinite(report["overall"]["elapsed_seconds"]["mean"])
    incomplete_cell = next(
        cell for cell in report["cells"]
        if cell["N"] == 150 and cell["p"] == 60
        and cell["focal_context"] == "bridge"
        and cell["condition"] == "coalition" and cell["arm"] == "diagnostic_cap4"
    )
    assert incomplete_cell["scheduled_rows"] == 10
    assert incomplete_cell["available_rows"] < 10
    assert (tmp_path / "summary" / "summary.json").is_file()


def test_unavailable_clean_rows_are_not_counted_as_invalid_references(tmp_path: Path) -> None:
    shards = _make_shards(tmp_path / "shards")
    results_path = shards[0] / "results.csv"
    with results_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    removed = 0
    retained: list[dict[str, str]] = []
    for row in rows:
        selected = (
            row["N"] == "50"
            and row["focal_context"] == "within_community"
            and row["condition"] == "clean"
            and row["arm"] == "baseline_cap2"
            and row["replication"] in {"5", "6", "7", "8", "9"}
        )
        if selected:
            removed += 1
        else:
            retained.append(row)
    assert removed == 5
    with results_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(retained)
    status_path = shards[0] / "shard_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status.update(status="incomplete", completed_rows=len(retained))
    status_path.write_text(json.dumps(status), encoding="utf-8")
    _refresh_metadata(shards[0])

    report = summarize_localized_network(shards, CONFIG, tmp_path / "summary")
    cell = next(
        cell for cell in report["cells"]
        if cell["N"] == 50 and cell["p"] == 20
        and cell["focal_context"] == "within_community"
        and cell["condition"] == "clean" and cell["arm"] == "baseline_cap2"
    )
    assert report["acceptance_status"] == "incomplete"
    assert cell["scheduled_rows"] == 10
    assert cell["available_rows"] == 5
    assert cell["clean_invalid_reference_rows"] == 0
