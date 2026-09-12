"""Validate the structural contract of a fixed-seed simulation smoke run."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from simulations.run_simulation import FIELDNAMES as EXPECTED_FIELDS

FINITE_FIELDS = ("true_rho", "observed_rho", "lambda", "wald_z", "elapsed_seconds")


def _checksum(config: dict[str, Any]) -> str:
    encoded = json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _expected_scenario_rows(config: dict[str, Any], replications: int) -> Counter[str]:
    base = replications * len(config["n_values"]) * len(config["p_values"])
    configured_scenarios = config.get("scenarios")
    if configured_scenarios is None:
        per_parameter = base * len(config["population_partial_r"])
        expected: Counter[str] = Counter()
        coalition_rows = per_parameter * sum(
            int(count) > 0 for count in config["contamination_cases"]
        )
        clean_rows = per_parameter * sum(
            int(count) == 0 for count in config["contamination_cases"]
        )
        if coalition_rows:
            expected["coalition_contamination"] = coalition_rows
        if clean_rows:
            expected["clean_planted_edge"] = clean_rows
        return expected

    expected: Counter[str] = Counter()
    for scenario in configured_scenarios:
        if scenario == "clean_planted_edge":
            multiplier = len(config["population_partial_r"])
        elif scenario == "coalition_contamination":
            multiplier = sum(int(count) > 0 for count in config["contamination_cases"])
        else:
            multiplier = 1
        expected[scenario] += base * multiplier
    return expected


def _optional_float(raw: str) -> float | None:
    if raw.strip().lower() in {"", "none"}:
        return None
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError("simulation field must be finite")
    return value


def _required_float(row: dict[str, str], field: str) -> float:
    value = _optional_float(row[field])
    if value is None:
        raise ValueError(f"simulation field {field!r} must be finite")
    return value


def _optional_int(row: dict[str, str], field: str) -> int | None:
    raw = row[field].strip()
    if raw.lower() in {"", "none"}:
        return None
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"simulation field {field!r} must be an integer or blank") from error
    if value < 0:
        raise ValueError(f"simulation field {field!r} must be nonnegative")
    return value


def _required_bool(row: dict[str, str], field: str) -> bool:
    normalized = row[field].strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise ValueError(f"simulation field {field!r} must be Boolean")


def _check_rate(value: float | None, field: str) -> None:
    if value is not None and not 0.0 <= value <= 1.0:
        raise ValueError(f"simulation field {field!r} must be between 0 and 1")


def validate_smoke(
    results_path: str | Path,
    metadata_path: str | Path,
    summary_path: str | Path,
    config_path: str | Path,
) -> None:
    """Raise ``ValueError`` when smoke artifacts violate their stable contract."""
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    replications = min(int(config["replications"]), 5)
    expected_scenarios = _expected_scenario_rows(config, replications)
    expected_rows = sum(expected_scenarios.values())

    with Path(results_path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXPECTED_FIELDS:
            raise ValueError(
                f"unexpected simulation schema: {reader.fieldnames!r}; "
                f"expected {EXPECTED_FIELDS!r}"
            )
        rows = list(reader)
    if len(rows) != expected_rows:
        raise ValueError(f"expected {expected_rows} simulation rows, found {len(rows)}")

    observed_scenarios: Counter[str] = Counter()
    for row in rows:
        scenario = row["scenario"]
        observed_scenarios[scenario] += 1
        if scenario not in expected_scenarios:
            raise ValueError(f"unexpected simulation scenario: {scenario!r}")
        for field in FINITE_FIELDS:
            value = _required_float(row, field)
            if field == "elapsed_seconds" and value < 0.0:
                raise ValueError("simulation field 'elapsed_seconds' must be nonnegative")
        target = _required_float(row, "fragility_target")
        if not 0.0 < target < 1.0:
            raise ValueError("simulation field 'fragility_target' must be between 0 and 1")
        for field in ("true_rho", "observed_rho"):
            if not -1.0 <= _required_float(row, field) <= 1.0:
                raise ValueError(f"simulation field {field!r} must be between -1 and 1")
        if _required_float(row, "lambda") <= 0.0:
            raise ValueError("simulation field 'lambda' must be positive")
        int(row["replication"])
        int(row["seed"])
        if int(row["N"]) < 4 or int(row["p"]) < 2:
            raise ValueError("simulation dimensions are below the minimum supported size")
        contamination_count = int(row["contamination_count"])
        if contamination_count < 0:
            raise ValueError("contamination_count must be nonnegative")
        contamination_status = int(row["contamination_status"])
        if contamination_status not in {0, 1}:
            raise ValueError("contamination_status must be 0 or 1")
        if contamination_status != int(contamination_count > 0):
            raise ValueError("contamination_status does not match contamination_count")
        _optional_int(row, "greedy_fragility_50")
        _optional_int(row, "exact_fragility_50")
        _required_bool(row, "certified")
        _required_bool(row, "reached")
        reference_tail = _optional_float(row["reference_tail_probability"])
        _check_rate(reference_tail, "reference_tail_probability")
        reference_reach = _required_float(row, "reference_reached_fraction")
        _check_rate(reference_reach, "reference_reached_fraction")
        _required_bool(row, "bootstrap_ci_excludes_zero")
        rejected = int(row["bootstrap_rejected_resamples"])
        if rejected < 0:
            raise ValueError("bootstrap_rejected_resamples must be nonnegative")
        influence_fields = (
            "influence_top_k_precision",
            "influence_top_k_recall",
            "first_planted_reciprocal_rank",
            "planted_absolute_influence_share",
        )
        for field in influence_fields:
            influence_value = _optional_float(row[field])
            _check_rate(influence_value, field)
            if contamination_status == 0 and influence_value is not None:
                raise ValueError(f"{field} must be blank without planted cases")
    if observed_scenarios != expected_scenarios:
        raise ValueError(
            f"unexpected scenario counts: {observed_scenarios!r}; "
            f"expected {expected_scenarios!r}"
        )

    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    if metadata.get("smoke") is not True:
        raise ValueError("simulation metadata does not identify a smoke run")
    if metadata.get("rows") != expected_rows:
        raise ValueError("simulation metadata row count does not match results")
    if metadata.get("config_checksum") != _checksum(config):
        raise ValueError("simulation metadata config checksum does not match config")
    timing = metadata.get("timing")
    if not isinstance(timing, dict):
        raise TypeError("simulation metadata does not contain a timing object")
    elapsed_seconds = timing.get("elapsed_seconds")
    if elapsed_seconds is None or not math.isfinite(float(elapsed_seconds)):
        raise ValueError("simulation metadata elapsed time is not finite")
    if float(elapsed_seconds) < 0.0:
        raise ValueError("simulation metadata elapsed time is negative")
    scenario_elapsed = timing.get("scenario_elapsed_seconds")
    scenario_rows = timing.get("scenario_rows")
    if not isinstance(scenario_elapsed, dict) or not isinstance(scenario_rows, dict):
        raise TypeError("simulation metadata timing detail is invalid")
    if set(scenario_elapsed) != set(expected_scenarios) or set(scenario_rows) != set(
        expected_scenarios
    ):
        raise ValueError("simulation metadata timing scenarios do not match results")
    scenario_elapsed_total = 0.0
    for scenario, expected_count in expected_scenarios.items():
        elapsed = float(scenario_elapsed[scenario])
        if not math.isfinite(elapsed) or elapsed < 0.0:
            raise ValueError(f"simulation metadata elapsed time is invalid for {scenario!r}")
        if int(scenario_rows[scenario]) != expected_count:
            raise ValueError(f"simulation metadata timing row count is wrong for {scenario!r}")
        scenario_elapsed_total += elapsed
    if float(elapsed_seconds) + 1e-9 < scenario_elapsed_total:
        raise ValueError("simulation metadata total elapsed time is below scenario total")

    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    if summary.get("rows") != expected_rows:
        raise ValueError("summary row count does not match results")
    summary_scenarios = summary.get("scenarios")
    if not isinstance(summary_scenarios, dict):
        raise TypeError("summary does not contain a scenarios object")
    if set(summary_scenarios) != set(expected_scenarios):
        raise ValueError("summary scenarios do not match simulation scenarios")
    summary_falsification = summary.get("falsification")
    if not isinstance(summary_falsification, dict):
        raise TypeError("summary does not contain a falsification object")
    if set(summary_falsification) != set(expected_scenarios):
        raise ValueError("summary falsification scenarios do not match simulation scenarios")
    for scenario, expected_count in expected_scenarios.items():
        values = summary_scenarios[scenario]
        if values.get("rows") != expected_count:
            raise ValueError(f"summary row count is wrong for {scenario!r}")
        if not math.isfinite(float(values["mean_observed_rho"])):
            raise ValueError(f"summary mean observed rho is not finite for {scenario!r}")
        rate = values["clean_false_flag_rate_at_0.05"]
        if rate is not None and not 0.0 <= float(rate) <= 1.0:
            raise ValueError(f"summary false-flag rate is invalid for {scenario!r}")
        falsification = summary_falsification[scenario]
        if not isinstance(falsification, dict):
            raise TypeError(f"summary falsification entry is invalid for {scenario!r}")
        for field in (
            "certification_rate",
            "fragility_reach_rate",
            "reference_reach_rate",
            "mean_influence_top_k_precision",
            "mean_influence_top_k_recall",
            "mean_first_planted_reciprocal_rank",
            "mean_planted_absolute_influence_share",
        ):
            value = falsification.get(field)
            if value is not None and not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"summary falsification rate is invalid for {scenario!r}: {field}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("summary", type=Path)
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    validate_smoke(args.results, args.metadata, args.summary, args.config)
    print(f"Smoke validation passed for {args.results}")


if __name__ == "__main__":
    main()
