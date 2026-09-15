"""Tests for the immutable certification-budget sensitivity manifest."""

import copy
import json
from pathlib import Path

import pytest

from tools.certification_budget_sensitivity_manifest import (
    BUDGET_GRID,
    certification_budget_sensitivity_manifest_checksum,
    load_certification_budget_sensitivity_manifest,
)

MANIFEST_PATH = Path("simulations/configs/certification_budget_sensitivity_v1.json")


def _write_json(tmp_path: Path, name: str, value: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_budget_manifest_declares_the_fixed_contract() -> None:
    manifest = load_certification_budget_sensitivity_manifest(MANIFEST_PATH)

    assert BUDGET_GRID == (1000, 5000, 10000, 20000)
    assert manifest["version"] == 1
    assert manifest["study"] == "certification_budget_sensitivity"
    assert manifest["output_schema_version"] == 1
    assert manifest["budget_grid"] == [1000, 5000, 10000, 20000]
    assert manifest["candidate_caps"] == [3, 4]
    assert manifest["expected_population_rows"] == {"cap3": 44, "cap4": 68}
    assert manifest["baseline_budget"] == 1000
    assert manifest["runtime_ceiling_seconds"] == 1800
    assert manifest["actions_timeout_minutes"] == 40
    assert manifest["expected_rows_per_budget"] == 112
    assert manifest["seed"] == 20260910
    assert manifest["calibration_simulations"] == 25
    assert manifest["bootstrap_samples"] == 100
    assert manifest["bootstrap_confidence"] == 0.95
    assert manifest["calibration_require_reached"] is False
    assert manifest["primary_target"] == 0.5
    assert manifest["source_manifest"] == "simulations/configs/cap_expansion_v1.json"
    assert manifest["task25_manifest"] == ("simulations/configs/certification_usability_v1.json")
    assert manifest["reason_values"] == [
        "not_applicable_unreached",
        "not_applicable_prior_error",
        "certified",
        "combination_budget_exhausted",
        "not_certified_other",
        "error",
    ]


def test_budget_manifest_pins_task25_and_nested_task24_identities() -> None:
    manifest = load_certification_budget_sensitivity_manifest(MANIFEST_PATH)

    assert manifest["source_task25_run_id"] == "34895397606"
    assert manifest["source_task25_commit"] == ("7b22b3fca39888e1a452cb5a7ad8ec244ccd752e")
    assert manifest["source_task25_artifact"] == ("sdna-certification-usability-34895397606")
    assert manifest["source_task25_results_sha256"] == (
        "4ec0068d8fe2b2b62df45fccbbf71f884c50589e319e48c3a2400111ae051918"
    )
    assert manifest["source_task25_manifest_checksum"] == (
        "b47842e33092b9431220204f46c77723f2465f86a1685e1cd1c90e601bedd4ff"
    )
    assert manifest["source_task24_run_id"] == "34871220664"
    assert manifest["source_task24_commit"] == ("338b0d95cdb312b2805affb0de458e06508d80f0")
    assert manifest["source_task24_artifact"] == "sdna-cap-expansion-34871220664"
    assert manifest["source_task24_results_sha256"] == (
        "110d0b4f266b253251ac1a64bb4195b61722008d426b74c75802d3de57b43d87"
    )
    assert manifest["source_task24_manifest_checksum"] == (
        "415576f1fec5ccd2a47e0ad411d29e4d48c6e8e370609ae495ccc877fe74e974"
    )


def test_budget_manifest_checksum_is_canonical_and_loader_returns_fresh_data() -> None:
    first = load_certification_budget_sensitivity_manifest(MANIFEST_PATH)
    reordered = json.loads(json.dumps(first, sort_keys=True))
    first["budget_grid"].append(99999)

    second = load_certification_budget_sensitivity_manifest(MANIFEST_PATH)
    assert second["budget_grid"] == [1000, 5000, 10000, 20000]
    assert certification_budget_sensitivity_manifest_checksum(second) == (
        certification_budget_sensitivity_manifest_checksum(reordered)
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("budget_grid", [1000, 5000, 10000]),
        ("budget_grid", [1000, 5000, 5000, 20000]),
        ("source_task25_run_id", "other"),
        ("source_task25_commit", "0" * 40),
        ("source_task25_artifact", "other"),
        ("source_task25_results_sha256", "0" * 64),
        ("source_task25_manifest_checksum", "0" * 64),
        ("source_task24_run_id", "other"),
        ("source_task24_commit", "0" * 40),
        ("source_task24_artifact", "other"),
        ("source_task24_results_sha256", "0" * 64),
        ("source_task24_manifest_checksum", "0" * 64),
        ("expected_population_rows", {"cap3": 43, "cap4": 68}),
        ("runtime_ceiling_seconds", 1),
        ("actions_timeout_minutes", 1),
        ("reason_values", ["unexpected"]),
        ("seed", 1),
        ("calibration_simulations", 1),
        ("bootstrap_samples", 1),
        ("bootstrap_confidence", 0.9),
        ("calibration_require_reached", True),
        ("primary_target", 0.3),
    ],
)
def test_budget_manifest_rejects_protocol_mutation(
    tmp_path: Path, field: str, value: object
) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(manifest)
    mutated[field] = value

    with pytest.raises(ValueError):
        load_certification_budget_sensitivity_manifest(
            _write_json(tmp_path, "mutated.json", mutated)
        )


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_budget_manifest_rejects_field_set_mutation(tmp_path: Path, mutation: str) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if mutation == "missing":
        del manifest["baseline_budget"]
    else:
        manifest["unexpected"] = True

    with pytest.raises(ValueError, match="fields"):
        load_certification_budget_sensitivity_manifest(
            _write_json(tmp_path, "mutated.json", manifest)
        )
