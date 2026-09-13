"""Load and expand the frozen reach-boundary study manifest."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

SCENARIO_NAMES = (
    "clean_planted_edge",
    "single_influential_case",
    "coalition_contamination",
    "mixture_subgroup",
    "heavy_tails",
    "collinearity_stress",
)

_ALL_SCENARIOS = list(SCENARIO_NAMES)
_ARM_NAMES = (
    "baseline_cap2",
    "cap3",
    "cap4",
    "target07_cap2",
    "heavy_df8",
    "collinear_rho90",
    "collinear_rho99",
)
_EXPECTED_ARM_DEFINITIONS = {
    "baseline_cap2": {
        "scenario_scope": _ALL_SCENARIOS,
        "target": 0.5,
        "search_cap": 2,
        "dgp_overrides": {},
    },
    "cap3": {
        "scenario_scope": _ALL_SCENARIOS,
        "target": 0.5,
        "search_cap": 3,
        "dgp_overrides": {},
    },
    "cap4": {
        "scenario_scope": _ALL_SCENARIOS,
        "target": 0.5,
        "search_cap": 4,
        "dgp_overrides": {},
    },
    "target07_cap2": {
        "scenario_scope": _ALL_SCENARIOS,
        "target": 0.7,
        "search_cap": 2,
        "dgp_overrides": {},
    },
    "heavy_df8": {
        "scenario_scope": ["heavy_tails"],
        "target": 0.5,
        "search_cap": 2,
        "dgp_overrides": {"degrees_of_freedom": 8.0},
    },
    "collinear_rho90": {
        "scenario_scope": ["collinearity_stress"],
        "target": 0.5,
        "search_cap": 2,
        "dgp_overrides": {"adjacent_correlation": 0.9},
    },
    "collinear_rho99": {
        "scenario_scope": ["collinearity_stress"],
        "target": 0.5,
        "search_cap": 2,
        "dgp_overrides": {"adjacent_correlation": 0.99},
    },
}


def _require_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _require_int(value: object, label: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def _require_float(value: object, label: str, *, lower: float, upper: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
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


def _scenario_parameter_values(manifest: dict[str, Any], scenario: str) -> list[float | int | None]:
    if scenario == "clean_planted_edge":
        return [float(value) for value in manifest["population_partial_r"]]
    if scenario == "coalition_contamination":
        return [
            int(value)
            for value in manifest["contamination_cases"]
            if int(value) > 0
        ]
    return [None]


def _validate_arm(arm: dict[str, Any], manifest: dict[str, Any]) -> None:
    name = arm.get("name")
    if not isinstance(name, str) or name not in _ARM_NAMES:
        raise ValueError(f"unknown arm name: {name!r}")
    scope = arm.get("scenario_scope")
    if not isinstance(scope, list) or not scope:
        raise ValueError(f"{name} scenario_scope must be a nonempty list")
    if len(set(scope)) != len(scope):
        raise ValueError(f"{name} scenario_scope must not contain duplicates")
    for scenario in scope:
        if scenario not in manifest["scenarios"]:
            raise ValueError(f"{name} has unknown scenario: {scenario}")
    _require_float(arm.get("target"), f"{name} target", lower=0.0, upper=1.0)
    _require_int(arm.get("search_cap"), f"{name} search_cap")
    overrides = arm.get("dgp_overrides")
    if not isinstance(overrides, dict):
        raise ValueError(f"{name} dgp_overrides must be an object")
    allowed = {"degrees_of_freedom", "adjacent_correlation"}
    if not set(overrides).issubset(allowed):
        raise ValueError(f"{name} has an unsupported DGP override")
    if "degrees_of_freedom" in overrides:
        if scope != ["heavy_tails"]:
            raise ValueError(f"{name} degrees_of_freedom requires heavy_tails only")
        value = overrides["degrees_of_freedom"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) <= 2.0:
            raise ValueError(f"{name} degrees_of_freedom must exceed 2")
    if "adjacent_correlation" in overrides:
        if scope != ["collinearity_stress"]:
            raise ValueError(f"{name} adjacent_correlation requires collinearity_stress only")
        _require_float(
            overrides["adjacent_correlation"],
            f"{name} adjacent_correlation",
            lower=0.0,
            upper=1.0,
        )
    expected = _EXPECTED_ARM_DEFINITIONS[name]
    actual_definition = {
        "scenario_scope": scope,
        "target": arm["target"],
        "search_cap": arm["search_cap"],
        "dgp_overrides": overrides,
    }
    if actual_definition != expected:
        raise ValueError(f"{name} does not match its frozen arm definition")


def load_reach_boundary_manifest(path: str | Path) -> dict[str, Any]:
    """Load and validate the immutable reach-boundary arm manifest."""
    manifest = _require_mapping(
        json.loads(Path(path).read_text(encoding="utf-8")),
        "manifest",
    )
    if manifest.get("version") != 1:
        raise ValueError("manifest version must be 1")
    _require_int(manifest.get("seed"), "seed", minimum=0)
    if manifest.get("replications") != 10:
        raise ValueError("replications must be 10")
    n_values = _require_positive_ints(manifest.get("n_values"), "n_values")
    p_values = _require_positive_ints(manifest.get("p_values"), "p_values")
    scenarios = manifest.get("scenarios")
    if scenarios != _ALL_SCENARIOS:
        raise ValueError("scenarios must contain the six frozen scenario names")
    edge = manifest.get("focal_edge")
    if edge != [0, 1]:
        raise ValueError("focal_edge must be [0, 1]")
    population_partial = manifest.get("population_partial_r")
    if not isinstance(population_partial, list) or not population_partial:
        raise ValueError("population_partial_r must be a nonempty list")
    contamination_cases = manifest.get("contamination_cases")
    if not isinstance(contamination_cases, list) or not contamination_cases:
        raise ValueError("contamination_cases must be a nonempty list")

    arms = manifest.get("arms")
    if not isinstance(arms, list) or not arms:
        raise ValueError("arms must be a nonempty list")
    arm_maps = [_require_mapping(arm, "arm") for arm in arms]
    names = [arm.get("name") for arm in arm_maps]
    if len(set(names)) != len(names):
        raise ValueError("duplicate arm name")
    missing_arm_names = set(_ARM_NAMES) - set(names)
    if missing_arm_names:
        missing = ", ".join(sorted(missing_arm_names))
        raise ValueError(f"manifest is missing required arm(s): {missing}")
    if set(names) != set(_ARM_NAMES):
        raise ValueError("manifest must contain exactly the frozen arm names")
    for arm in arm_maps:
        _validate_arm(arm, manifest)

    expected_rows = _require_int(manifest.get("expected_rows"), "expected_rows")
    calculated_rows = sum(
        len(n_values)
        * len(p_values)
        * manifest["replications"]
        * sum(
            len(_scenario_parameter_values(manifest, scenario))
            for scenario in arm["scenario_scope"]
        )
        for arm in arm_maps
    )
    if expected_rows != calculated_rows:
        raise ValueError(
            f"expected_rows={expected_rows} does not match expanded rows={calculated_rows}"
        )
    return manifest


def expand_reach_boundary_jobs(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand a validated manifest into deterministic row specifications."""
    jobs: list[dict[str, Any]] = []
    for arm in manifest["arms"]:
        for n in manifest["n_values"]:
            for p in manifest["p_values"]:
                for scenario in arm["scenario_scope"]:
                    parameters = _scenario_parameter_values(manifest, scenario)
                    for parameter_id, parameter in enumerate(parameters):
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
                                    "dgp_overrides": dict(arm["dgp_overrides"]),
                                }
                            )
    return jobs
