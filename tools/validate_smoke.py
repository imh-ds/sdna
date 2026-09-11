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

EXPECTED_FIELDS = [
    "scenario",
    "replication",
    "seed",
    "N",
    "p",
    "fragility_target",
    "true_rho",
    "observed_rho",
    "lambda",
    "contamination_count",
    "greedy_fragility_50",
    "exact_fragility_50",
    "certified",
    "reached",
    "reference_tail_probability",
    "wald_z",
    "bootstrap_ci_excludes_zero",
    "influence_top_k_recall",
]

FINITE_FIELDS = ("true_rho", "observed_rho", "lambda", "wald_z")


def _checksum(config: dict[str, Any]) -> str:
    encoded = json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _expected_scenario_rows(config: dict[str, Any], replications: int) -> Counter[str]:
    per_scenario = (
        replications
        * len(config["n_values"])
        * len(config["p_values"])
        * len(config["population_partial_r"])
    )
    return Counter(
        "coalition_contamination" if count else "clean_planted_edge"
        for count in config["contamination_cases"]
        for _ in range(per_scenario)
    )


def validate_smoke(
    results_path: str | Path,
    metadata_path: str | Path,
    summary_path: str | Path,
    config_path: str | Path,
) -> None:
    """Raise ``ValueError`` when smoke artifacts violate their stable contract."""
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    replications = min(int(config["replications"]), 10)
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
            value = float(row[field])
            if not math.isfinite(value):
                raise ValueError(f"simulation field {field!r} is not finite")
        int(row["replication"])
        int(row["seed"])
        int(row["N"])
        int(row["p"])
        int(row["contamination_count"])
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

    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    if summary.get("rows") != expected_rows:
        raise ValueError("summary row count does not match results")
    summary_scenarios = summary.get("scenarios")
    if not isinstance(summary_scenarios, dict):
        raise ValueError("summary does not contain a scenarios object")
    if set(summary_scenarios) != set(expected_scenarios):
        raise ValueError("summary scenarios do not match simulation scenarios")
    for scenario, expected_count in expected_scenarios.items():
        values = summary_scenarios[scenario]
        if values.get("rows") != expected_count:
            raise ValueError(f"summary row count is wrong for {scenario!r}")
        if not math.isfinite(float(values["mean_observed_rho"])):
            raise ValueError(f"summary mean observed rho is not finite for {scenario!r}")
        rate = values["clean_false_flag_rate_at_0.05"]
        if rate is not None and not 0.0 <= float(rate) <= 1.0:
            raise ValueError(f"summary false-flag rate is invalid for {scenario!r}")


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
