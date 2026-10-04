"""Run the frozen estimator comparison (docs/methodology/estimator_comparison_study_v1.md)."""

from __future__ import annotations

import argparse
import csv
import json
import platform
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from typing import Any

import numpy as np

from sdna.estimation import fit_network
from simulations.composite_dgp_v2 import (
    STRENGTHS,
    edge_threshold,
    generate_composite_dataset,
)
from simulations.composite_dgp_v2 import TRUTH_DRAWS as COMPOSITE_TRUTH_DRAWS
from simulations.ebic_glasso import ebic_glasso
from simulations.edge_recovery import (
    edge_recovery_metrics,
    ordinary_partial_correlation,
    ring_truth,
)

SEED = 20261008
N_VALUES = (30, 50, 100, 150, 200, 300)
REPLICATIONS = 100
METRICS = ("sign_agreement", "rank_correlation", "edge_auc", "top_k_precision", "magnitude_ratio")
PART_A_P = (5, 8, 12)
PART_B_P = (6, 12)
PART_B_CONDITIONS = ("continuous_control", "severe_ceiling")


def _cells() -> list[tuple[str, int, str, str]]:
    cells = [("A", p, s, "gaussian") for p in PART_A_P for s in STRENGTHS]
    cells += [
        ("B", p, s, c) for p in PART_B_P for s in STRENGTHS for c in PART_B_CONDITIONS
    ]
    return cells


def _selection(estimate: Any, truth: Any, threshold: float) -> dict[str, float]:
    upper = np.triu_indices(truth.shape[0], k=1)
    selected = np.abs(estimate[upper]) > 0.0
    is_edge = np.abs(truth[upper]) > threshold
    return {
        "sensitivity": float(selected[is_edge].mean()),
        "specificity": float((~selected[~is_edge]).mean()),
        "empty": float(not selected.any()),
        "selected_edges": float(selected.sum()),
    }


def _run_job(args: tuple[Any, ...]) -> list[dict[str, Any]]:
    (part, p, strength, condition, n, replication), child, truth_draws = args
    seed = int(child.generate_state(1, dtype=np.uint32)[0])
    if part == "A":
        covariance, truth = ring_truth(p, STRENGTHS[strength])
        X = np.random.default_rng(seed).multivariate_normal(np.zeros(p), covariance, size=n)
        threshold = 1e-8
    else:
        dataset = generate_composite_dataset(
            n, p, strength, condition, "none", seed, truth_draws
        )
        X, truth = dataset.X, dataset.partial_correlation
        found = edge_threshold(truth)
        if found is None:
            return []
        threshold = found
    row: dict[str, Any] = {
        "part": part, "p": p, "strength": strength, "condition": condition,
        "N": n, "replication": replication, "seed": seed,
    }
    estimates: dict[str, Any] = {"sdna": fit_network(X).partial_correlation}
    ebic, _ = ebic_glasso(X)
    estimates["ebic"] = ebic
    ordinary = ordinary_partial_correlation(X)
    if ordinary is not None:
        estimates["ordinary"] = ordinary
    for name, estimate in estimates.items():
        metrics = edge_recovery_metrics(estimate, truth, threshold)
        for metric in METRICS:
            row[f"{name}_{metric}"] = metrics[metric]
    row.update({f"ebic_{k}": v for k, v in _selection(ebic, truth, threshold).items()})
    return [row]


def run(
    replications: int = REPLICATIONS,
    *,
    n_values: tuple[int, ...] = N_VALUES,
    truth_draws: int = COMPOSITE_TRUTH_DRAWS,
    workers: int = 1,
) -> list[dict[str, Any]]:
    keys = [
        (*cell, n, rep) for cell in _cells() for n in n_values for rep in range(replications)
    ]
    children = np.random.SeedSequence(SEED).spawn(len(keys))
    jobs = [(key, child, truth_draws) for key, child in zip(keys, children, strict=True)]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_run_job, jobs, chunksize=4))
    else:
        results = [_run_job(job) for job in jobs]
    return [row for chunk in results for row in chunk]


def _mean_se(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    array = np.asarray(values, dtype=float)
    se = float(array.std(ddof=1) / np.sqrt(array.size)) if array.size > 1 else None
    return float(array.mean()), se


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cells: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        cells[(row["part"], row["p"], row["strength"], row["condition"], row["N"])].append(row)
    out: list[dict[str, Any]] = []
    for key, group in sorted(cells.items()):
        part, p, strength, condition, n = key
        entry: dict[str, Any] = {
            "part": part, "p": p, "strength": strength, "condition": condition,
            "N": n, "rows": len(group),
        }
        for estimator in ("sdna", "ebic", "ordinary"):
            for metric in METRICS:
                values = [
                    r[f"{estimator}_{metric}"] for r in group
                    if r.get(f"{estimator}_{metric}") is not None
                ]
                entry[f"{estimator}_{metric}"] = _mean_se(values)[0]
                entry[f"{estimator}_{metric}_n"] = len(values)
        for metric in ("edge_auc", "sign_agreement", "top_k_precision"):
            diffs = [
                r[f"sdna_{metric}"] - r[f"ebic_{metric}"]
                for r in group
                if r.get(f"sdna_{metric}") is not None and r.get(f"ebic_{metric}") is not None
            ]
            mean, se = _mean_se(diffs)
            entry[f"paired_diff_{metric}"] = mean
            entry[f"paired_diff_{metric}_se"] = se
            entry[f"paired_diff_{metric}_n"] = len(diffs)
            entry[f"sdna_higher_{metric}"] = sum(d > 1e-12 for d in diffs)
            entry[f"sdna_lower_{metric}"] = sum(d < -1e-12 for d in diffs)
        for name in ("sensitivity", "specificity", "empty", "selected_edges"):
            entry[f"ebic_{name}"] = _mean_se([r[f"ebic_{name}"] for r in group])[0]
        out.append(entry)
    return out


def main() -> None:
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--replications", type=int, default=REPLICATIONS)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    rows = run(args.replications, workers=args.workers)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "rows.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), restval="")
        writer.writeheader()
        writer.writerows(rows)
    (args.output_dir / "summary.json").write_text(
        json.dumps(summarize(rows), indent=2), encoding="utf-8"
    )
    (args.output_dir / "environment.json").write_text(
        json.dumps(
            {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "platform": platform.platform(),
                "processor": platform.processor(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
