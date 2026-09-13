"""Tests for the pre-specified reach-boundary manifest."""

from __future__ import annotations

import copy
import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

import tools.run_reach_boundary as reach_boundary
from tools.reach_boundary_manifest import (
    expand_reach_boundary_jobs,
    load_reach_boundary_manifest,
)
from tools.summarize_reach_boundary import summarize_rows

MANIFEST_PATH = Path("simulations/configs/reach_boundary_v1.json")


def _manifest_data() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _write_manifest(tmp_path: Path, data: dict[str, object]) -> Path:
    path = tmp_path / "reach-boundary.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_reach_boundary_manifest_expands_to_declared_paired_grid() -> None:
    manifest = load_reach_boundary_manifest(MANIFEST_PATH)

    jobs = expand_reach_boundary_jobs(manifest)

    assert len(jobs) == 2_430
    assert Counter(job["arm"] for job in jobs) == Counter(
        {
            "baseline_cap2": 540,
            "cap3": 540,
            "cap4": 540,
            "target07_cap2": 540,
            "heavy_df8": 90,
            "collinear_rho90": 90,
            "collinear_rho99": 90,
        }
    )

    pairing_fields = ("scenario", "N", "p", "parameter_id", "replication")
    paired_keys = {
        arm: {
            tuple(job[field] for field in pairing_fields)
            for job in jobs
            if job["arm"] == arm
        }
        for arm in ("baseline_cap2", "cap3", "cap4", "target07_cap2")
    }
    assert len({frozenset(keys) for keys in paired_keys.values()}) == 1


def test_reach_boundary_manifest_rejects_duplicate_arm_names(tmp_path: Path) -> None:
    data = _manifest_data()
    data["arms"] = [*data["arms"], copy.deepcopy(data["arms"][0])]  # type: ignore[index]

    with pytest.raises(ValueError, match="duplicate arm name"):
        load_reach_boundary_manifest(_write_manifest(tmp_path, data))


def test_reach_boundary_manifest_rejects_unknown_scenario(tmp_path: Path) -> None:
    data = _manifest_data()
    data["arms"][0]["scenario_scope"] = ["unknown_scenario"]  # type: ignore[index]

    with pytest.raises(ValueError, match="unknown scenario"):
        load_reach_boundary_manifest(_write_manifest(tmp_path, data))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("search_cap", 0, "search_cap"),
        ("target", 1.0, "target"),
    ],
)
def test_reach_boundary_manifest_rejects_invalid_arm_limits(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    data = _manifest_data()
    data["arms"][0][field] = value  # type: ignore[index]

    with pytest.raises(ValueError, match=message):
        load_reach_boundary_manifest(_write_manifest(tmp_path, data))


def test_reach_boundary_manifest_requires_baseline_arm(tmp_path: Path) -> None:
    data = _manifest_data()
    data["arms"] = [
        arm for arm in data["arms"] if arm["name"] != "baseline_cap2"  # type: ignore[index]
    ]

    with pytest.raises(ValueError, match="baseline_cap2"):
        load_reach_boundary_manifest(_write_manifest(tmp_path, data))


def test_reach_boundary_manifest_rejects_wrong_declared_row_count(tmp_path: Path) -> None:
    data = _manifest_data()
    data["expected_rows"] = 2_429

    with pytest.raises(ValueError, match="expected_rows"):
        load_reach_boundary_manifest(_write_manifest(tmp_path, data))


def test_reach_boundary_manifest_rejects_changed_frozen_arm_definition(
    tmp_path: Path,
) -> None:
    data = _manifest_data()
    cap3 = next(arm for arm in data["arms"] if arm["name"] == "cap3")  # type: ignore[index]
    cap3["search_cap"] = 2

    with pytest.raises(ValueError, match="cap3"):
        load_reach_boundary_manifest(_write_manifest(tmp_path, data))


def test_runner_preserves_pairing_and_records_row_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest = load_reach_boundary_manifest(MANIFEST_PATH)
    all_jobs = expand_reach_boundary_jobs(manifest)
    baseline_job = next(job for job in all_jobs if job["arm"] == "baseline_cap2")
    pairing_key = tuple(
        baseline_job[field]
        for field in ("scenario", "N", "p", "parameter_id", "replication")
    )
    jobs = [
        job
        for job in all_jobs
        if tuple(
            job[field]
            for field in ("scenario", "N", "p", "parameter_id", "replication")
        )
        == pairing_key
        and job["arm"] in {"baseline_cap2", "cap3"}
    ]
    monkeypatch.setattr(reach_boundary, "expand_reach_boundary_jobs", lambda _: jobs)

    generated: list[tuple[str, np.ndarray]] = []
    original_generate = reach_boundary.generate_reach_boundary_dataset

    def tracked_generate(job: dict[str, object], rng: np.random.Generator, manifest: dict[str, object]):
        dataset = original_generate(job, rng, manifest)
        generated.append((str(job["arm"]), dataset.X.copy()))
        return dataset

    monkeypatch.setattr(reach_boundary, "generate_reach_boundary_dataset", tracked_generate)
    original_greedy = reach_boundary.greedy_fragility

    def fail_cap3(*args: object, **kwargs: object):
        if kwargs.get("search_cap") == 3:
            raise np.linalg.LinAlgError("forced row failure")
        return original_greedy(*args, **kwargs)

    monkeypatch.setattr(reach_boundary, "greedy_fragility", fail_cap3)

    output_path = tmp_path / "reach-boundary.csv"
    reach_boundary.run_reach_boundary(MANIFEST_PATH, output_path)

    with output_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["arm"] for row in rows] == ["baseline_cap2", "cap3"]
    assert rows[0]["seed"] == rows[1]["seed"]
    assert len(generated) == 1
    assert rows[0]["status"] == "ok"
    assert rows[1]["status"] == "error"
    assert rows[1]["error_type"] == "LinAlgError"
    assert rows[1]["reached"] == ""


def _summary_row(
    arm: str,
    replication: int,
    *,
    reached: bool | None,
    greedy_count: int | None,
    status: str = "ok",
) -> dict[str, object]:
    return {
        "arm": arm,
        "scenario": "heavy_tails",
        "parameter_id": 0,
        "parameter": None,
        "replication": replication,
        "seed": replication + 100,
        "N": 50,
        "p": 5,
        "fragility_target": 0.5,
        "search_cap": 2 if arm == "baseline_cap2" else 3,
        "reached": reached,
        "greedy_count": greedy_count,
        "cap_exhausted": reached is False,
        "full_value": 0.2 if status == "ok" else None,
        "final_value": 0.1 if status == "ok" else None,
        "trajectory": "[0.2, 0.1]" if status == "ok" else None,
        "shrinkage": 0.1 if status == "ok" else None,
        "rank": 5 if status == "ok" else None,
        "min_eigenvalue_correlation": 0.1 if status == "ok" else None,
        "min_eigenvalue_shrunk_correlation": 0.2 if status == "ok" else None,
        "condition_number": 10.0 if status == "ok" else None,
        "elapsed_seconds": 0.1,
        "status": status,
        "error_type": "LinAlgError" if status == "error" else None,
        "error_message": "forced failure" if status == "error" else None,
    }


def test_summary_reports_paired_transitions_and_separates_errors_from_censoring() -> None:
    rows = [
        _summary_row("baseline_cap2", 0, reached=False, greedy_count=None),
        _summary_row("cap3", 0, reached=True, greedy_count=3),
        _summary_row("baseline_cap2", 1, reached=False, greedy_count=None),
        _summary_row("cap3", 1, reached=True, greedy_count=3),
        _summary_row("baseline_cap2", 2, reached=True, greedy_count=2),
        _summary_row("cap3", 2, reached=True, greedy_count=3),
        _summary_row("baseline_cap2", 3, reached=False, greedy_count=None),
        _summary_row("cap3", 3, reached=None, greedy_count=None, status="error"),
    ]

    comparison = summarize_rows(rows)["comparisons"]["cap3"]

    assert comparison["matched_pairs"] == 4
    assert comparison["transition_counts"] == {
        "0_to_0": 0,
        "0_to_1": 2,
        "1_to_0": 0,
        "1_to_1": 1,
    }
    assert comparison["baseline_error_rows"] == 0
    assert comparison["candidate_error_rows"] == 1
    assert comparison["baseline_censored_rows"] == 3
    assert comparison["candidate_censored_rows"] == 0
    assert comparison["newly_reached_rows"] == 2
    assert comparison["median_greedy_count_newly_reached"] == 3.0
    assert comparison["median_extra_deletions_both_reached"] == 1.0
