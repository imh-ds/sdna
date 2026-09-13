"""Benchmarks for exact and analytic leave-one-out influence."""

from __future__ import annotations

import argparse
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from benchmarks.provenance import write_payload
from sdna.estimation import fit_network
from sdna.influence import analytic_influence, exact_loo_influence


def _validate_dimensions(n: int, p: int, repeats: int = 1) -> None:
    if n < 4:
        raise ValueError("n must be at least 4")
    if p < 2:
        raise ValueError("p must be at least 2")
    if repeats < 1:
        raise ValueError("repeats must be positive")


def _timed(function: Any) -> float:
    start = perf_counter()
    function()
    return perf_counter() - start


def benchmark_row(
    n: int,
    p: int,
    *,
    seed: int = 20260910,
    repeats: int = 1,
) -> dict[str, Any]:
    """Measure exact and analytic influence on one fixed-seed dataset."""
    _validate_dimensions(n, p, repeats)
    rng = np.random.default_rng(seed)
    data = rng.normal(size=(n, p))
    fitted = fit_network(data)
    exact_seconds = sum(
        _timed(lambda: exact_loo_influence(data, fitted)) for _ in range(repeats)
    ) / repeats
    analytic_seconds = sum(
        _timed(lambda: analytic_influence(fitted)) for _ in range(repeats)
    ) / repeats
    slope, mae, maximum = _approximation_metrics_for(data, fitted)
    return {
        "N": n,
        "p": p,
        "seed": seed,
        "repeats": repeats,
        "exact_loo_seconds": exact_seconds,
        "analytic_influence_seconds": analytic_seconds,
        "approximation_slope": slope,
        "approximation_mae": mae,
        "approximation_max_abs_error": maximum,
    }


def run_benchmark_matrix(
    n_values: tuple[int, ...] | list[int] = (50, 75, 100, 150),
    p_values: tuple[int, ...] | list[int] = (5, 10, 15, 20),
    *,
    seed: int = 20260910,
    repeats: int = 1,
) -> list[dict[str, Any]]:
    """Run the influence benchmark over the plan's N-by-p matrix."""
    if not n_values or not p_values:
        raise ValueError("n_values and p_values must not be empty")
    child_seeds = np.random.SeedSequence(seed).spawn(len(n_values) * len(p_values))
    rows: list[dict[str, Any]] = []
    seed_index = 0
    for n in n_values:
        for p in p_values:
            row_seed = int(child_seeds[seed_index].generate_state(1)[0])
            rows.append(benchmark_row(n, p, seed=row_seed, repeats=repeats))
            seed_index += 1
    return rows


def write_results(
    rows: list[dict[str, Any]],
    output: str | Path,
    *,
    settings: dict[str, Any] | None = None,
) -> None:
    """Write benchmark rows and reproducibility provenance as indented JSON."""
    write_payload("influence", rows, output, settings)


def _approximation_metrics_for(
    data: np.ndarray, fitted: Any
) -> tuple[float | None, float | None, float | None]:
    exact = exact_loo_influence(data, fitted).changes
    approx = analytic_influence(fitted).changes
    iu = np.triu_indices(data.shape[1], 1)
    analytic_values = approx[:, iu[0], iu[1]].ravel()
    exact_values = exact[:, iu[0], iu[1]].ravel()
    if not np.isfinite(analytic_values).all() or not np.isfinite(exact_values).all():
        return None, None, None
    mae = float(np.mean(np.abs(analytic_values - exact_values)))
    maximum = float(np.max(np.abs(analytic_values - exact_values)))
    if np.std(analytic_values) == 0.0:
        return None, mae, maximum
    slope = float(np.polyfit(analytic_values, exact_values, 1)[0])
    return slope, mae, maximum


def benchmark(n: int, p: int) -> float:
    """Return the legacy exact-LOO timing helper result."""
    rng = np.random.default_rng(20260910 + n + p)
    data = rng.normal(size=(n, p))
    fitted = fit_network(data)
    start = perf_counter()
    exact_loo_influence(data, fitted)
    return perf_counter() - start


def approximation_metrics(n: int, p: int) -> tuple[float | None, float | None, float | None]:
    rng = np.random.default_rng(20260910 + n + p)
    data = rng.normal(size=(n, p))
    fitted = fit_network(data)
    return _approximation_metrics_for(data, fitted)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seed", type=int, default=20260910)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--n-values", type=int, nargs="+", default=[50, 75, 100, 150])
    parser.add_argument("--p-values", type=int, nargs="+", default=[5, 10, 15, 20])
    args = parser.parse_args()
    rows = run_benchmark_matrix(
        tuple(args.n_values), tuple(args.p_values), seed=args.seed, repeats=args.repeats
    )
    for row in rows:
        slope = "n/a" if row["approximation_slope"] is None else f"{row['approximation_slope']:.4f}"
        mae = "n/a" if row["approximation_mae"] is None else f"{row['approximation_mae']:.6f}"
        maximum = (
            "n/a"
            if row["approximation_max_abs_error"] is None
            else f"{row['approximation_max_abs_error']:.6f}"
        )
        print(
            f"N={row['N']:3d}, p={row['p']:2d}: "
            f"exact_loo={row['exact_loo_seconds']:.6f}s "
            f"analytic={row['analytic_influence_seconds']:.6f}s "
            f"slope={slope} MAE={mae} max|error|={maximum}"
        )
    if args.output is not None:
        write_results(
            rows,
            args.output,
            settings={
                "seed": args.seed,
                "repeats": args.repeats,
                "n_values": args.n_values,
                "p_values": args.p_values,
            },
        )


if __name__ == "__main__":
    main()
