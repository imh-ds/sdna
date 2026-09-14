"""Tests for the frozen paired cap-expansion manifest."""

import json
from collections import Counter
from pathlib import Path

import pytest

from tools.cap_expansion_manifest import (
    CAP_ARM_NAMES,
    cap_expansion_pairing_keys,
    expand_cap_expansion_jobs,
    load_cap_expansion_manifest,
)


MANIFEST_PATH = Path("simulations/configs/cap_expansion_v1.json")


def _write_manifest(tmp_path: Path, manifest: dict[str, object]) -> Path:
    path = tmp_path / "cap-expansion.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_cap_expansion_manifest_has_three_balanced_arms() -> None:
    manifest = load_cap_expansion_manifest(MANIFEST_PATH)
    jobs = expand_cap_expansion_jobs(manifest)

    assert len(jobs) == 1620
    assert Counter(job["arm"] for job in jobs) == {
        "baseline_cap2": 540,
        "cap3": 540,
        "cap4": 540,
    }
    assert tuple(sorted(CAP_ARM_NAMES)) == ("baseline_cap2", "cap3", "cap4")
    assert {job["search_cap"] for job in jobs} == {2, 3, 4}
    assert len(cap_expansion_pairing_keys(manifest)) == 540


def test_cap_expansion_manifest_pairs_each_key_across_all_arms() -> None:
    manifest = load_cap_expansion_manifest(MANIFEST_PATH)
    jobs = expand_cap_expansion_jobs(manifest)
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for job in jobs:
        key = tuple(job[field] for field in ("scenario", "N", "p", "parameter_id", "replication"))
        grouped.setdefault(key, []).append(job)

    assert len(grouped) == 540
    assert all({job["arm"] for job in rows} == set(CAP_ARM_NAMES) for rows in grouped.values())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("expected_rows", 1619, "expected_rows"),
        ("version", 2, "version"),
        ("seed", 20260911, "seed"),
    ],
)
def test_manifest_rejects_changed_frozen_values(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest[field] = value

    with pytest.raises((TypeError, ValueError), match=message):
        load_cap_expansion_manifest(_write_manifest(tmp_path, manifest))


def test_manifest_rejects_changed_arm_definition(tmp_path: Path) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["arms"][1]["search_cap"] = 5

    with pytest.raises(ValueError, match="cap3"):
        load_cap_expansion_manifest(_write_manifest(tmp_path, manifest))


def test_manifest_rejects_extra_arm(tmp_path: Path) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["arms"].append(
        {
            "name": "cap5",
            "scenario_scope": manifest["scenarios"],
            "target": 0.5,
            "search_cap": 5,
            "dgp_overrides": {},
        }
    )

    with pytest.raises(ValueError, match="exactly"):
        load_cap_expansion_manifest(_write_manifest(tmp_path, manifest))
