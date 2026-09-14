"""Load and checksum the certification-usability audit manifest."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

__all__ = [
    "certification_usability_manifest_checksum",
    "load_certification_usability_manifest",
]

_EXPECTED_SOURCE_MANIFEST_CHECKSUM = (
    "415576f1fec5ccd2a47e0ad411d29e4d48c6e8e370609ae495ccc877fe74e974"
)
_EXPECTED_SOURCE_RESULTS_SHA256 = (
    "110d0b4f266b253251ac1a64bb4195b61722008d426b74c75802d3de57b43d87"
)
_EXPECTED_REASON_VALUES = [
    "not_applicable_unreached",
    "not_applicable_prior_error",
    "certified",
    "combination_budget_exhausted",
    "not_certified_other",
    "error",
]
_EXPECTED_FIELDS = {
    "version",
    "study",
    "source_manifest",
    "source_manifest_checksum",
    "source_run_id",
    "source_commit",
    "source_artifact",
    "source_results_sha256",
    "candidate_caps",
    "primary_population",
    "primary_endpoint",
    "instrumented_schema_version",
    "reason_values",
}


def certification_usability_manifest_checksum(manifest: Mapping[str, Any]) -> str:
    """Return a stable SHA-256 checksum for a validated manifest mapping."""
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("certification-usability manifest must be an object")
    return value


def _require_string(manifest: Mapping[str, Any], field: str, expected: str) -> None:
    if manifest.get(field) != expected:
        raise ValueError(f"{field} must be {expected!r}")


def load_certification_usability_manifest(path: str | Path) -> dict[str, Any]:
    """Load and validate the immutable certification-usability manifest."""
    manifest = _require_mapping(json.loads(Path(path).read_text(encoding="utf-8")))
    if set(manifest) != _EXPECTED_FIELDS:
        raise ValueError("manifest fields do not match the certification-usability contract")
    if manifest["version"] != 1:
        raise ValueError("version must be 1")
    _require_string(manifest, "study", "certification_usability_audit")
    _require_string(manifest, "source_manifest", "simulations/configs/cap_expansion_v1.json")
    _require_string(manifest, "source_manifest_checksum", _EXPECTED_SOURCE_MANIFEST_CHECKSUM)
    _require_string(manifest, "source_run_id", "34871220664")
    _require_string(
        manifest,
        "source_commit",
        "338b0d95cdb312b2805affb0de458e06508d80f0",
    )
    _require_string(manifest, "source_artifact", "sdna-cap-expansion-34871220664")
    _require_string(manifest, "source_results_sha256", _EXPECTED_SOURCE_RESULTS_SHA256)
    if manifest["candidate_caps"] != [3, 4]:
        raise ValueError("candidate_caps must be [3, 4]")
    _require_string(
        manifest,
        "primary_population",
        "baseline_unreached_candidate_reached",
    )
    _require_string(manifest, "primary_endpoint", "candidate_certification_yield")
    if manifest["instrumented_schema_version"] != 1:
        raise ValueError("instrumented_schema_version must be 1")
    if manifest["reason_values"] != _EXPECTED_REASON_VALUES:
        raise ValueError("reason_values do not match the certification-usability contract")
    return manifest
