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
