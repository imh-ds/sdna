"""Load and expand the frozen paired cap-expansion study manifest."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

CAP_ARM_NAMES = ("baseline_cap2", "cap3", "cap4")
PAIRING_FIELDS = ("scenario", "N", "p", "parameter_id", "replication")
SCENARIO_NAMES = (
    "clean_planted_edge",
    "single_influential_case",
    "coalition_contamination",
    "mixture_subgroup",
    "heavy_tails",
    "collinearity_stress",
)

_EXPECTED_ARM_DEFINITIONS = {
    "baseline_cap2": {
        "scenario_scope": list(SCENARIO_NAMES),
        "target": 0.5,
        "search_cap": 2,
        "dgp_overrides": {},
    },
    "cap3": {
        "scenario_scope": list(SCENARIO_NAMES),
        "target": 0.5,
        "search_cap": 3,
        "dgp_overrides": {},
    },
    "cap4": {
        "scenario_scope": list(SCENARIO_NAMES),
        "target": 0.5,
        "search_cap": 4,
        "dgp_overrides": {},
    },
}


def _require_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    return value


def _require_int(value: object, label: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def _require_float(value: object, label: str, *, lower: float, upper: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be numeric")
    parsed = float(value)
    if not math.isfinite(parsed) or not lower < parsed < upper:
        raise ValueError(f"{label} must be strictly between {lower} and {upper}")
    return parsed


def _require_positive_ints(value: object, label: str) -> list[int]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a nonempty list")
    values = [_require_int(item, f"{label} item") for item in value]
    if len(set(values)) != len(values):
        raise ValueError(f"{label} must not contain duplicates")
    return values


def _scenario_parameter_values(
    manifest: Mapping[str, Any], scenario: str
) -> list[float | int | None]:
    if scenario == "clean_planted_edge":
        return [float(value) for value in manifest["population_partial_r"]]
    if scenario == "coalition_contamination":
        return [
            int(value)
            for value in manifest["contamination_cases"]
            if int(value) > 0
        ]
    return [None]


def _validate_arm(arm: Mapping[str, Any]) -> None:
    name = arm.get("name")
    if name not in CAP_ARM_NAMES:
        raise ValueError(f"unknown arm name: {name!r}")
    expected = _EXPECTED_ARM_DEFINITIONS[name]
    if {
        "name": name,
        "scenario_scope": arm.get("scenario_scope"),
        "target": arm.get("target"),
        "search_cap": arm.get("search_cap"),
        "dgp_overrides": arm.get("dgp_overrides"),
    } != {"name": name, **expected}:
        raise ValueError(f"{name} does not match its frozen arm definition")


def load_cap_expansion_manifest(path: str | Path) -> dict[str, Any]:
    """Load and validate the immutable cap-expansion manifest."""
    manifest = _require_mapping(
        json.loads(Path(path).read_text(encoding="utf-8")),
        "manifest",
    )
    if manifest.get("version") != 1:
        raise ValueError("version must be 1")
    _require_int(manifest.get("seed"), "seed", minimum=0)
    if manifest.get("replications") != 10:
        raise ValueError("replications must be 10")
    if _require_positive_ints(manifest.get("n_values"), "n_values") != [50, 100, 150]:
        raise ValueError("n_values must be [50, 100, 150]")
    if _require_positive_ints(manifest.get("p_values"), "p_values") != [5, 10, 20]:
        raise ValueError("p_values must be [5, 10, 20]")
    if manifest.get("scenarios") != list(SCENARIO_NAMES):
        raise ValueError("scenarios must contain the six frozen scenario names")
    if manifest.get("focal_edge") != [0, 1]:
        raise ValueError("focal_edge must be [0, 1]")
    if manifest.get("population_partial_r") != [0.2]:
        raise ValueError("population_partial_r must be [0.2]")
    if manifest.get("contamination_cases") != [3]:
        raise ValueError("contamination_cases must be [3]")
    if manifest.get("fragility_targets") != [0.9, 0.7, 0.5, 0.3]:
        raise ValueError("fragility_targets do not match the frozen study")
    if manifest.get("primary_target") != 0.5:
        raise ValueError("primary_target must be 0.5")
    if manifest.get("calibration_simulations") != 25:
        raise ValueError("calibration_simulations must be 25")
    if manifest.get("bootstrap_samples") != 100:
        raise ValueError("bootstrap_samples must be 100")
    if manifest.get("bootstrap_confidence") != 0.95:
        raise ValueError("bootstrap_confidence must be 0.95")
    if manifest.get("certification_combination_budget") != 1000:
        raise ValueError("certification_combination_budget must be 1000")
    if manifest.get("calibration_require_reached") is not False:
        raise ValueError("calibration_require_reached must be false")
    if manifest.get("operational_runtime_ceiling_seconds") != 900:
        raise ValueError("operational_runtime_ceiling_seconds must be 900")

    arms = manifest.get("arms")
    if not isinstance(arms, list) or [arm.get("name") for arm in arms if isinstance(arm, dict)] != list(
        CAP_ARM_NAMES
    ):
        raise ValueError("arms must contain exactly the frozen arm names in order")
    for raw_arm in arms:
        _validate_arm(_require_mapping(raw_arm, "arm"))

    expected_rows = _require_int(manifest.get("expected_rows"), "expected_rows")
    calculated_rows = sum(
        len(manifest["n_values"])
        * len(manifest["p_values"])
        * manifest["replications"]
        * sum(
            len(_scenario_parameter_values(manifest, scenario))
            for scenario in arm["scenario_scope"]
        )
        for arm in arms
    )
    if expected_rows != calculated_rows or expected_rows != 1620:
        raise ValueError(
            f"expected_rows={expected_rows} does not match frozen expanded rows=1620"
        )
    return manifest


def expand_cap_expansion_jobs(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Expand a validated manifest into deterministic arm-specific jobs."""
    jobs: list[dict[str, Any]] = []
    for arm in manifest["arms"]:
        for n in manifest["n_values"]:
            for p in manifest["p_values"]:
                for scenario in arm["scenario_scope"]:
                    for parameter_id, parameter in enumerate(
                        _scenario_parameter_values(manifest, scenario)
                    ):
                        for replication in range(manifest["replications"]):
                            jobs.append(
                                {
                                    "arm": arm["name"],
                                    "scenario": scenario,
                                    "parameter_id": parameter_id,
                                    "parameter": parameter,
                                    "replication": replication,
                                    "N": n,
                                    "p": p,
                                    "target": arm["target"],
                                    "search_cap": arm["search_cap"],
                                }
                            )
    return jobs


def cap_expansion_pairing_keys(
    manifest: Mapping[str, Any],
) -> list[tuple[Any, ...]]:
    """Return sorted unique keys shared by all three cap arms."""
    jobs = expand_cap_expansion_jobs(manifest)
    keys = {tuple(job[field] for field in PAIRING_FIELDS) for job in jobs}
    return sorted(keys, key=lambda key: (key[1], key[2], key[0], key[3], key[4]))


def manifest_checksum(manifest: Mapping[str, Any]) -> str:
    """Return the canonical checksum for a validated manifest."""
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
