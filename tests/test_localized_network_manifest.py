"""Contract tests for the frozen Task 27 localized-network manifest."""

from __future__ import annotations

import copy
import json
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from tools.localized_network_manifest import (
    DATA_SEED_FIELDS,
    LOCALIZED_PAIRING_FIELDS,
    expand_localized_jobs,
    load_localized_manifest,
    localized_data_seed,
    localized_data_seed_key,
    localized_manifest_checksum,
    localized_pairing_keys,
)

CONFIG_PATH = (
    Path(__file__).parents[1]
    / "simulations"
    / "configs"
    / "localized_network_v1.json"
)


def test_frozen_manifest_values_and_expansion_counts() -> None:
    manifest = load_localized_manifest(CONFIG_PATH)

    assert manifest["version"] == 1
    assert manifest["study"] == "localized_network_operating_envelope"
    assert manifest["seed"] == 20261002
    assert manifest["n_values"] == [50, 100, 150]
    assert manifest["p_values"] == [20, 40, 60]
    assert manifest["modules"]["nodes_per_module"] == 5
    assert manifest["modules"]["within_module_edges"] == [
        "ring",
        "hub_to_all_other_nodes",
    ]
    assert manifest["modules"]["between_module_edges"] == [
        "last_node_to_next_module_hub"
    ]
    assert manifest["population"] == {
        "precision_diagonal": 1.0,
        "edge_precision": -0.05,
        "focal_partial_correlation": 0.05,
    }
    assert manifest["focal_contexts"] == [
        "within_community",
        "hub_adjacent",
        "bridge",
    ]
    assert manifest["conditions"] == ["clean", "single_case", "coalition"]
    assert manifest["condition_settings"] == {
        "clean": {"planted_case_count": 0, "shift": 0.0},
        "single_case": {"planted_case_count": 1, "shift": 4.0},
        "coalition": {"planted_case_count": 3, "shift": 4.0},
    }
    assert manifest["replications"] == 10
    assert manifest["arms"] == [
        {"name": "baseline_cap2", "target": 0.5, "search_cap": 2, "role": "primary"},
        {
            "name": "diagnostic_cap4",
            "target": 0.5,
            "search_cap": 4,
            "role": "diagnostic",
        },
    ]
    assert manifest["certification_combination_budget"] == 1000
    assert manifest["calibration_simulations"] == 25
    assert manifest["calibration_require_reached"] is False
    assert manifest["reference_tail_treatment"] == "right_censored"
    assert manifest["bootstrap_draws"] == 100
    assert manifest["bootstrap_confidence"] == 0.95
    assert manifest["expected_pairing_keys"] == 810
    assert manifest["expected_rows"] == 1620
    assert manifest["expected_pairing_keys_per_p"] == 270
    assert manifest["expected_rows_per_p"] == 540
    assert "dataset_digest" not in manifest

    jobs = expand_localized_jobs(manifest)
    keys = localized_pairing_keys(manifest)
    assert len(jobs) == 1620
    assert jobs == expand_localized_jobs(manifest)
    assert len(keys) == 810
    assert Counter(job["arm"] for job in jobs) == {
        "baseline_cap2": 810,
        "diagnostic_cap4": 810,
    }


def test_pairing_key_and_data_seed_key_are_explicit_contracts() -> None:
    manifest = load_localized_manifest(CONFIG_PATH)
    jobs = expand_localized_jobs(manifest)
    paired: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)

    assert LOCALIZED_PAIRING_FIELDS == (
        "N",
        "p",
        "focal_context",
        "condition",
        "replication",
    )
    assert DATA_SEED_FIELDS == ("N", "p", "condition", "replication")
    for job in jobs:
        paired[tuple(job[field] for field in LOCALIZED_PAIRING_FIELDS)].append(job)
        assert localized_data_seed_key(job) == tuple(
            job[field] for field in ("N", "p", "condition", "replication")
        )
        assert len(localized_data_seed_key(job)) == 4

    assert len(paired) == 810
    for rows in paired.values():
        assert {row["arm"] for row in rows} == {"baseline_cap2", "diagnostic_cap4"}
        assert len(rows) == 2
        assert rows[0]["search_cap"] != rows[1]["search_cap"]
        assert rows[0]["target"] == rows[1]["target"] == 0.5
        assert localized_data_seed_key(rows[0]) == localized_data_seed_key(rows[1])

    by_seed_key: dict[tuple[int, int, str, int], list[dict[str, object]]] = defaultdict(list)
    for job in jobs:
        seed_key = localized_data_seed_key(job)
        by_seed_key[seed_key].append(job)
        assert job["data_seed"] == localized_data_seed(manifest["seed"], seed_key)
        assert "dataset_digest" not in job

    assert len(by_seed_key) == 270
    for rows in by_seed_key.values():
        assert len(rows) == 6  # three focal contexts paired across two arms
        assert len({row["focal_context"] for row in rows}) == 3
        assert {row["arm"] for row in rows} == {"baseline_cap2", "diagnostic_cap4"}
        assert len({row["data_seed"] for row in rows}) == 1


@pytest.mark.parametrize("p", [20, 40, 60])
def test_p_shard_contains_only_its_frozen_rows_and_pairing_keys(p: int) -> None:
    manifest = load_localized_manifest(CONFIG_PATH)

    jobs = expand_localized_jobs(manifest, p_shard=p)
    keys = localized_pairing_keys(manifest, p_shard=p)

    assert len(jobs) == 540
    assert len(keys) == 270
    assert {job["p"] for job in jobs} == {p}
    assert {key[1] for key in keys} == {p}


def test_manifest_checksum_is_canonical() -> None:
    manifest = load_localized_manifest(CONFIG_PATH)
    reordered = dict(reversed(list(manifest.items())))

    assert localized_manifest_checksum(manifest) == localized_manifest_checksum(reordered)
    assert len(localized_manifest_checksum(manifest)) == 64


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("arms",), []),
        (("n_values",), [50, 100]),
        (("p_values",), [20, 40, 80]),
        (("replications",), 9),
        (("modules", "nodes_per_module"), 6),
        (("population", "focal_partial_correlation"), 0.1),
        (("focal_contexts",), ["within_community", "hub_adjacent", "other"]),
        (("conditions",), ["clean", "single_case", "other"]),
        (("condition_settings", "coalition", "shift"), 3.0),
        (("reference_tail_treatment",), "uncensored"),
        (("expected_pairing_keys",), 809),
        (("expected_rows",), 1618),
        (("expected_pairing_keys_per_p",), 269),
        (("expected_rows_per_p",), 539),
    ],
)
def test_loader_rejects_changes_to_frozen_contract(
    tmp_path: Path, path: tuple[str, ...], value: object
) -> None:
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(raw)
    parent = changed
    for field in path[:-1]:
        parent = parent[field]
    parent[path[-1]] = value
    candidate = tmp_path / "manifest.json"
    candidate.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises((TypeError, ValueError)):
        load_localized_manifest(candidate)


def test_loader_rejects_each_mutated_arm_setting(tmp_path: Path) -> None:
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    for field, value in (("search_cap", 3), ("target", 0.7), ("role", "primary")):
        changed = copy.deepcopy(raw)
        changed["arms"][1][field] = value
        candidate = tmp_path / f"{field}.json"
        candidate.write_text(json.dumps(changed), encoding="utf-8")
        with pytest.raises(ValueError):
            load_localized_manifest(candidate)


def test_data_seed_key_excludes_arm_and_focal_context() -> None:
    first = {
        "N": 50,
        "p": 20,
        "focal_context": "within_community",
        "condition": "single_case",
        "replication": 3,
        "arm": "baseline_cap2",
    }
    second = {
        **first,
        "focal_context": "bridge",
        "arm": "diagnostic_cap4",
    }

    assert localized_data_seed_key(first) == (50, 20, "single_case", 3)
    assert localized_data_seed_key(second) == localized_data_seed_key(first)


def test_data_seed_depends_only_on_root_seed_and_data_seed_key() -> None:
    key = (50, 20, "single_case", 3)

    seed = localized_data_seed(20261002, key)
    assert seed == localized_data_seed(20261002, key)
    assert seed != localized_data_seed(20261003, key)
    assert seed != localized_data_seed(20261002, (100, 20, "single_case", 3))
    assert seed != localized_data_seed(20261002, (50, 40, "single_case", 3))
    assert seed != localized_data_seed(20261002, (50, 20, "clean", 3))
    assert seed != localized_data_seed(20261002, (50, 20, "single_case", 4))
