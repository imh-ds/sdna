"""Tests for the certification-usability audit manifest."""

import copy
import json
from pathlib import Path

import pytest

from tools.certification_usability_manifest import (
    certification_usability_manifest_checksum,
    load_certification_usability_manifest,
)

MANIFEST_PATH = Path("simulations/configs/certification_usability_v1.json")


def test_certification_usability_manifest_pins_task24_source() -> None:
    manifest = load_certification_usability_manifest(MANIFEST_PATH)

    assert manifest["source_run_id"] == "34871220664"
    assert manifest["source_commit"] == "338b0d95cdb312b2805affb0de458e06508d80f0"
    assert manifest["source_artifact"] == "sdna-cap-expansion-34871220664"
    assert manifest["source_manifest_checksum"] == (
        "415576f1fec5ccd2a47e0ad411d29e4d48c6e8e370609ae495ccc877fe74e974"
    )
    assert manifest["source_results_sha256"] == (
        "110d0b4f266b253251ac1a64bb4195b61722008d426b74c75802d3de57b43d87"
    )
    assert manifest["candidate_caps"] == [3, 4]
    assert manifest["primary_population"] == "baseline_unreached_candidate_reached"
    assert manifest["primary_endpoint"] == "candidate_certification_yield"
    assert manifest["instrumented_schema_version"] == 1
    assert manifest["reason_values"] == [
        "not_applicable_unreached",
        "not_applicable_prior_error",
        "certified",
        "combination_budget_exhausted",
        "not_certified_other",
        "error",
    ]


def test_certification_usability_manifest_checksum_is_canonical() -> None:
    manifest = load_certification_usability_manifest(MANIFEST_PATH)
    reordered = json.loads(json.dumps(manifest, sort_keys=True))

    assert certification_usability_manifest_checksum(manifest) == (
        certification_usability_manifest_checksum(reordered)
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_run_id", "99999999999"),
        ("source_commit", "0" * 40),
        ("candidate_caps", [2, 3]),
        ("reason_values", ["unexpected"]),
    ],
)
def test_certification_usability_manifest_rejects_mutated_contract(
    tmp_path: Path, field: str, value: object
) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(manifest)
    mutated[field] = value
    path = tmp_path / "mutated.json"
    path.write_text(json.dumps(mutated), encoding="utf-8")

    with pytest.raises(ValueError):
        load_certification_usability_manifest(path)
