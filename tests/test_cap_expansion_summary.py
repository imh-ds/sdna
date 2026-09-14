"""Tests for cap-expansion summaries and artifact validation."""

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from simulations.full_workflow import derive_workflow_seeds
from simulations.run_simulation import replication_seeds
from tools.cap_expansion_manifest import (
    PAIRING_FIELDS,
    cap_expansion_pairing_keys,
    expand_cap_expansion_jobs,
    load_cap_expansion_manifest,
    manifest_checksum,
)
from tools.run_cap_expansion import CAP_EXPANSION_FIELDNAMES
from tools.summarize_cap_expansion import (
    summarize_cap_expansion,
    summarize_cap_expansion_rows,
    validate_cap_expansion,
)

MANIFEST_PATH = Path("simulations/configs/cap_expansion_v1.json")


def cap_row(
    arm: str,
    replication: int,
    *,
    reached: bool | None,
    status: str = "ok",
    digest: str = "a" * 64,
    observed_rho: float = 0.2,
    exact_fragility: float | None = 2.0,
) -> dict[str, object]:
    cap = {"baseline_cap2": 2, "cap3": 3, "cap4": 4}[arm]
    is_error = status == "error"
    fragility_status = "error" if is_error else ("reached" if reached else "unreached")
    return {
        "arm": arm,
        "scenario": "coalition_contamination",
        "parameter_id": 0,
        "parameter": 3,
        "replication": replication,
        "N": 50,
        "p": 5,
        "data_seed": 11,
        "calibration_seed": 12,
        "bootstrap_seed": 13,
        "dataset_digest": digest,
        "fragility_target": 0.5,
        "search_cap": cap,
        "calibration_require_reached": False,
        "true_rho": 0.0,
        "observed_rho": observed_rho,
        "lambda": 0.1,
        "contamination_count": 3,
        "contamination_status": 1,
        "greedy_fragility_50": exact_fragility if reached else None,
        "exact_fragility_50": exact_fragility if reached else None,
        "certified": bool(reached) if not is_error else None,
        "reached": reached,
        "reference_tail_probability": 0.01 if reached else None,
        "reference_reached_fraction": 1.0 if reached else 0.0,
        "wald_z": 1.0,
        "bootstrap_ci_excludes_zero": False,
        "bootstrap_rejected_resamples": 0,
        "influence_top_k_precision": 0.5,
        "influence_top_k_recall": 0.5,
        "first_planted_reciprocal_rank": 1.0,
        "planted_absolute_influence_share": 0.4,
        "fragility_status": fragility_status,
        "certification_status": "certified" if reached else "skipped_unreached",
        "calibration_status": "finite" if reached else "observed_unreached",
        "wald_status": "error" if is_error else "ok",
        "bootstrap_status": "error" if is_error else "ok",
        "workflow_status": "error" if is_error else ("ok" if reached else "partial"),
        "error_stage": "bootstrap" if is_error else None,
        "error_type": "RuntimeError" if is_error else None,
        "error_message": "synthetic failure" if is_error else None,
        "elapsed_seconds": 0.1,
    }


def hand_computable_cap_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for replication in range(3):
        rows.append(
            cap_row(
                "baseline_cap2",
                replication,
                reached=replication != 0,
            )
        )
        rows.append(
            cap_row(
                "cap3",
                replication,
                reached=True if replication < 2 else None,
                status="error" if replication == 2 else "ok",
            )
        )
        rows.append(cap_row("cap4", replication, reached=True))
    return rows


def test_cap_summary_reports_transitions_and_joint_denominators() -> None:
    manifest = load_cap_expansion_manifest(MANIFEST_PATH)
    summary = summarize_cap_expansion_rows(hand_computable_cap_rows(), manifest)

    comparison = summary["comparisons"]["cap3"]
    assert comparison["transition_counts"]["unreached_to_reached"] == 1
    assert comparison["candidate_error_rows"] == 1
    assert comparison["jointly_valid_pair_count"] == 1
    assert comparison["pooled_metrics"] != comparison["jointly_valid_pair_metrics"]


def _write_valid_artifact_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    manifest = load_cap_expansion_manifest(MANIFEST_PATH)
    jobs = expand_cap_expansion_jobs(manifest)
    pair_keys = cap_expansion_pairing_keys(manifest)
    data_seeds = dict(
        zip(
            pair_keys,
            replication_seeds(int(manifest["seed"]), len(pair_keys)),
            strict=True,
        )
    )
    rows: list[dict[str, object]] = []
    for job in jobs:
        row = cap_row(str(job["arm"]), int(job["replication"]), reached=True)
        key = tuple(job[field] for field in PAIRING_FIELDS)
        data_seed = data_seeds[key]
        child_seeds = derive_workflow_seeds(data_seed)
        row.update(
            {
                "scenario": job["scenario"],
                "parameter_id": job["parameter_id"],
                "parameter": job["parameter"],
                "N": job["N"],
                "p": job["p"],
                "search_cap": job["search_cap"],
                "data_seed": data_seed,
                "calibration_seed": child_seeds.calibration,
                "bootstrap_seed": child_seeds.bootstrap,
            }
        )
        rows.append(row)

    results = tmp_path / "results.csv"
    with results.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CAP_EXPANSION_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    metadata = tmp_path / "results.metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "git_commit": "fixture",
                "python_version": "fixture",
                "numpy_version": "fixture",
                "package_version": "fixture",
                "manifest_checksum": manifest_checksum(manifest),
                "rows": 1620,
                "arm_rows": {"baseline_cap2": 540, "cap3": 540, "cap4": 540},
                "status_counts": {
                    field: dict(Counter(str(row[field]) for row in rows))
                    for field in (
                        "fragility_status",
                        "certification_status",
                        "calibration_status",
                        "wald_status",
                        "bootstrap_status",
                        "workflow_status",
                    )
                },
                "timing": {
                    "elapsed_seconds": 1.0,
                    "arm_elapsed_seconds": {
                        "baseline_cap2": 0.3,
                        "cap3": 0.3,
                        "cap4": 0.3,
                    },
                    "runtime_ceiling_seconds": 900,
                    "budget_exceeded": False,
                },
            }
        ),
        encoding="utf-8",
    )
    summary = tmp_path / "summary.json"
    summarize_cap_expansion(results, summary, tmp_path / "summary.md", MANIFEST_PATH)
    return results, metadata, summary, MANIFEST_PATH


def _rewrite_results(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CAP_EXPANSION_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def test_cap_validator_rejects_mismatched_pair_digest(tmp_path: Path) -> None:
    results, metadata, summary, manifest = _write_valid_artifact_fixture(tmp_path)
    with results.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows[1]["dataset_digest"] = "tampered"
    with results.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CAP_EXPANSION_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(ValueError, match="dataset_digest"):
        validate_cap_expansion(results, metadata, summary, manifest)


def test_cap_validator_accepts_valid_fixture(tmp_path: Path) -> None:
    results, metadata, summary, manifest = _write_valid_artifact_fixture(tmp_path)

    validate_cap_expansion(results, metadata, summary, manifest)


def test_cap_summary_distinguishes_unreached_and_right_censored_rows() -> None:
    manifest = load_cap_expansion_manifest(MANIFEST_PATH)
    summary = summarize_cap_expansion_rows(hand_computable_cap_rows(), manifest)

    comparison = summary["comparisons"]["cap3"]
    assert comparison["baseline_unreached_rows"] == 1
    assert comparison["candidate_unreached_rows"] == 0
    assert comparison["baseline_right_censored_rows"] == 0
    assert comparison["candidate_right_censored_rows"] == 0


@pytest.mark.parametrize("mutation", ["workflow", "calibration", "wald"])
def test_cap_validator_rejects_semantically_inconsistent_status(
    tmp_path: Path, mutation: str
) -> None:
    results, metadata, summary, manifest = _write_valid_artifact_fixture(tmp_path)
    with results.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if mutation == "workflow":
        rows[0].update(
            {
                "fragility_status": "unreached",
                "reached": "False",
                "greedy_fragility_50": "",
                "exact_fragility_50": "",
                "certified": "",
                "certification_status": "skipped_unreached",
                "calibration_status": "observed_unreached",
                "reference_tail_probability": "",
                "workflow_status": "ok",
            }
        )
    elif mutation == "calibration":
        rows[0].update(
            {"calibration_status": "finite", "reference_tail_probability": ""}
        )
    else:
        rows[0].update({"wald_status": "ok", "wald_z": ""})
    _rewrite_results(results, rows)

    with pytest.raises(ValueError, match="status|finite|wald|workflow"):
        validate_cap_expansion(results, metadata, summary, manifest)


def test_cap_validator_rejects_tampered_summary(tmp_path: Path) -> None:
    results, metadata, summary, manifest = _write_valid_artifact_fixture(tmp_path)
    summary_data = json.loads(summary.read_text(encoding="utf-8"))
    summary_data["comparisons"]["cap3"]["matched_pairs"] = 0
    summary.write_text(json.dumps(summary_data), encoding="utf-8")
    metadata_data = json.loads(metadata.read_text(encoding="utf-8"))
    metadata_data["artifact_checksums"]["summary_json"] = hashlib.sha256(
        summary.read_bytes()
    ).hexdigest()
    metadata.write_text(json.dumps(metadata_data), encoding="utf-8")

    with pytest.raises(ValueError, match="summary"):
        validate_cap_expansion(results, metadata, summary, manifest)


def test_cap_validator_rejects_non_deterministic_pair_seed(tmp_path: Path) -> None:
    results, metadata, summary, manifest = _write_valid_artifact_fixture(tmp_path)
    with results.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for index in (0, 540, 1080):
        rows[index]["data_seed"] = "999"
    _rewrite_results(results, rows)

    with pytest.raises(ValueError, match="data_seed"):
        validate_cap_expansion(results, metadata, summary, manifest)


def test_cap_validator_rejects_malformed_dataset_digest(tmp_path: Path) -> None:
    results, metadata, summary, manifest = _write_valid_artifact_fixture(tmp_path)
    with results.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for index in (0, 540, 1080):
        rows[index]["dataset_digest"] = "tampered"
    _rewrite_results(results, rows)

    with pytest.raises(ValueError, match="dataset_digest"):
        validate_cap_expansion(results, metadata, summary, manifest)


def test_cap_validator_rejects_parameter_value_mismatch(tmp_path: Path) -> None:
    results, metadata, summary, manifest = _write_valid_artifact_fixture(tmp_path)
    with results.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["parameter"] = "999"
    with results.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CAP_EXPANSION_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(ValueError, match="parameter"):
        validate_cap_expansion(results, metadata, summary, manifest)


def test_methodology_page_points_to_frozen_implementation_contract() -> None:
    text = Path("docs/methodology/cap_expansion_study_v1.md").read_text(encoding="utf-8")

    for required in (
        "bb7a851",
        "1,620",
        "right-censored",
        "jointly-valid",
        "cap-expansion.yml",
    ):
        assert required in text


def test_cap_expansion_workflow_is_manual_only() -> None:
    text = Path(".github/workflows/cap-expansion.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "pull_request:" not in text
    assert "tools.run_cap_expansion" in text
    assert "--validate" in text
    assert "actions/upload-artifact" in text
    assert "metadata['timing']['budget_exceeded']" in text
    assert "grep -q 'budget_exceeded=true'" not in text
    assert text.count("$CAP_EXPANSION_DIR/results.metadata.json") >= 2
