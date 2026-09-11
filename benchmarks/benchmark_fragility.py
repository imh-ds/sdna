"""Benchmarks for greedy fragility search and reference calibration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from sdna.calibration import calibrate_fragility
from sdna.estimation import fit_network
from sdna.fragility import FragilityTarget, greedy_fragility


def _validate_dimensions(n: int, p: int, calibration_simulations: int) -> None:
    if n < 4:
        raise ValueError("n must be at least 4")
    if p < 2:
        raise ValueError("p must be at least 2")
    if calibration_simulations < 1:
        raise ValueError("calibration_simulations must be positive")


def benchmark_row(
    n: int,
    p: int,
    *,
    seed: int = 20260910,
    calibration_simulations: int = 500,
    search_cap: int | None = None,
) -> dict[str, Any]:
    """Measure one greedy search and one fixed-seed calibration run."""
    _validate_dimensions(n, p, calibration_simulations)
    rng = np.random.default_rng(seed)
    data = rng.normal(size=(n, p))
    fitted = fit_network(data)
    target = FragilityTarget("relative", 0.5)

    start = perf_counter()
    greedy = greedy_fragility(
        data,
        edge=(0, 1),
        target=target,
        shrinkage=fitted.shrinkage,
        search_cap=search_cap,
    )
    greedy_seconds = perf_counter() - start

    calibration_seed = np.random.SeedSequence(seed).spawn(1)[0]
    start = perf_counter()
    calibration = calibrate_fragility(
        data,
        edge=(0, 1),
        target=target,
        n_sim=calibration_simulations,
        rng=np.random.default_rng(calibration_seed),
        shrinkage=fitted.shrinkage,
        search_cap=search_cap,
        require_reached=False,
    )
    calibration_seconds = perf_counter() - start
    reached_fraction = sum(calibration.reference_reached) / len(calibration.reference_reached)
    return {
        "N": n,
        "p": p,
        "seed": seed,
        "search_cap": search_cap,
        "calibration_simulations": calibration_simulations,
        "greedy_fragility_seconds": greedy_seconds,
        "calibration_seconds": calibration_seconds,
        "greedy_count": greedy.greedy_count,
        "greedy_reached": greedy.reached,
        "calibration_observed_reached": calibration.observed_reached,
        "calibration_reference_reached_fraction": reached_fraction,
    }


def run_benchmark_matrix(
    n_values: tuple[int, ...] | list[int] = (50, 75, 100, 150),
    p_values: tuple[int, ...] | list[int] = (5, 10, 15, 20),
    *,
    seed: int = 20260910,
    calibration_simulations: int = 500,
    search_cap: int | None = None,
) -> list[dict[str, Any]]:
    """Run fragility and calibration benchmarks over the plan's N-by-p matrix."""
    if not n_values or not p_values:
        raise ValueError("n_values and p_values must not be empty")
    child_seeds = np.random.SeedSequence(seed).spawn(len(n_values) * len(p_values))
    rows: list[dict[str, Any]] = []
    seed_index = 0
    for n in n_values:
        for p in p_values:
            row_seed = int(child_seeds[seed_index].generate_state(1)[0])
            rows.append(
                benchmark_row(
                    n,
                    p,
                    seed=row_seed,
                    calibration_simulations=calibration_simulations,
                    search_cap=search_cap,
                )
            )
            seed_index += 1
    return rows


def write_results(rows: list[dict[str, Any]], output: str | Path) -> None:
    """Write benchmark rows as indented JSON."""
    Path(output).write_text(json.dumps({"rows": rows}, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seed", type=int, default=20260910)
    parser.add_argument("--calibration-simulations", type=int, default=500)
    parser.add_argument("--search-cap", type=int)
    parser.add_argument("--n-values", type=int, nargs="+", default=[50, 75, 100, 150])
    parser.add_argument("--p-values", type=int, nargs="+", default=[5, 10, 15, 20])
    args = parser.parse_args()
    rows = run_benchmark_matrix(
        tuple(args.n_values),
        tuple(args.p_values),
        seed=args.seed,
        calibration_simulations=args.calibration_simulations,
        search_cap=args.search_cap,
    )
    for row in rows:
        print(
            f"N={row['N']:3d}, p={row['p']:2d}: "
            f"greedy={row['greedy_fragility_seconds']:.6f}s "
            f"calibration={row['calibration_seconds']:.6f}s "
            f"reference_reached={row['calibration_reference_reached_fraction']:.3f}"
        )
    if args.output is not None:
        write_results(rows, args.output)


if __name__ == "__main__":
    main()
