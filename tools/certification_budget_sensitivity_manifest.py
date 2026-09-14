"""Load and checksum the immutable certification-budget sensitivity manifest."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

__all__ = [
    "BUDGET_GRID",
    "certification_budget_sensitivity_manifest_checksum",
    "load_certification_budget_sensitivity_manifest",
]

BUDGET_GRID: tuple[int, int, int, int] = (1000, 5000, 10000, 20000)

_EXPECTED_MANIFEST: dict[str, Any] = {
    "version": 1,
    "study": "certification_budget_sensitivity",
    "output_schema_version": 1,
    "source_task25_run_id": "34895397606",
    "source_task25_commit": "7b22b3fca39888e1a452cb5a7ad8ec244ccd752e",
    "source_task25_artifact": "sdna-certification-usability-34895397606",
    "source_task25_results_sha256": (
        "4ec0068d8fe2b2b62df45fccbbf71f884c50589e319e48c3a2400111ae051918"
    ),
    "source_task25_manifest_checksum": (
        "b47842e33092b9431220204f46c77723f2465f86a1685e1cd1c90e601bedd4ff"
    ),
    "source_task24_run_id": "34871220664",
    "source_task24_commit": "338b0d95cdb312b2805affb0de458e06508d80f0",
    "source_task24_artifact": "sdna-cap-expansion-34871220664",
    "source_task24_results_sha256": (
        "110d0b4f266b253251ac1a64bb4195b61722008d426b74c75802d3de57b43d87"
    ),
    "source_task24_manifest_checksum": (
        "415576f1fec5ccd2a47e0ad411d29e4d48c6e8e370609ae495ccc877fe74e974"
    ),
    "source_manifest": "simulations/configs/cap_expansion_v1.json",
    "task25_manifest": "simulations/configs/certification_usability_v1.json",
    "candidate_caps": [3, 4],
    "expected_population_rows": {"cap3": 44, "cap4": 68},
    "budget_grid": list(BUDGET_GRID),
    "baseline_budget": 1000,
    "runtime_ceiling_seconds": 1800,
    "actions_timeout_minutes": 40,
    "expected_rows_per_budget": 112,
    "seed": 20260910,
    "calibration_simulations": 25,
    "bootstrap_samples": 100,
    "bootstrap_confidence": 0.95,
    "calibration_require_reached": False,
    "primary_target": 0.5,
    "reason_values": [
        "not_applicable_unreached",
        "not_applicable_prior_error",
        "certified",
        "combination_budget_exhausted",
        "not_certified_other",
        "error",
    ],
}


def certification_budget_sensitivity_manifest_checksum(
    manifest: Mapping[str, Any],
) -> str:
    """Return the SHA-256 of a canonical JSON representation."""
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_certification_budget_sensitivity_manifest(path: str | Path) -> dict[str, Any]:
    """Load the Task 26 manifest and reject every protocol mutation."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("certification-budget sensitivity manifest must be an object")
    if set(raw) != set(_EXPECTED_MANIFEST):
        raise ValueError("manifest fields do not match the certification-budget contract")
    for field, expected in _EXPECTED_MANIFEST.items():
        if raw[field] != expected:
            raise ValueError(f"{field} does not match the certification-budget contract")
    return copy.deepcopy(raw)
