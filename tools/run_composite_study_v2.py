"""Run the frozen composite-score study v2 (docs/methodology/composite_score_study_v2.md)."""

from __future__ import annotations

import argparse
import csv
import json
import platform
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from sdna.fragility import FragilityTarget
from simulations.composite_dgp_v2 import (
    CONDITIONS,
    CONTAMINATED_COUNT,
    CONTAMINATIONS,
    P_VALUES,
    STRENGTHS,
    TRUTH_DRAWS,
    edge_threshold,
    generate_composite_dataset,
)
from simulations.edge_recovery import recovery_row
from simulations.full_workflow import derive_workflow_seeds, run_full_workflow

SEED = 20261006
N_VALUES = (50, 100, 150)
REPLICATIONS = 30
TAIL_FLAG = 0.05
RECOVERY_METRICS = (
    "sign_agreement", "rank_correlation", "edge_auc", "top_k_precision", "magnitude_ratio",
)


def _job_keys(replications: int, n_values: tuple[int, ...]) -> list[tuple[int, str, int, int]]:
    return [
        (p, strength, n, rep)
        for p in P_VALUES
        for strength in STRENGTHS
        for n in n_values
        for rep in range(replications)
    ]


def _run_job(args: tuple[Any, ...]) -> list[dict[str, Any]]:
    (p, strength, n, replication), child, settings = args
    seed = int(child.generate_state(1, dtype=np.uint32)[0])
    rows: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        for contamination in CONTAMINATIONS:
            dataset = generate_composite_dataset(
                n, p, strength, condition, contamination, seed, settings["truth_draws"]
            )
            threshold = edge_threshold(dataset.partial_correlation)
            recovery = (
                recovery_row(dataset.X, dataset.partial_correlation, threshold)
                if threshold is not None
                else {}
            )
            workflow = run_full_workflow(
                dataset,
                target=FragilityTarget("relative", 0.5),
                search_cap=2,
                calibration_simulations=settings["calibration_simulations"],
                bootstrap_samples=settings["bootstrap_samples"],
                bootstrap_confidence=0.95,
                certification_combination_budget=1000,
                seeds=derive_workflow_seeds(seed),
                calibration_require_reached=False,
            )
            rows.append({
                "p": p, "strength": strength, "N": n, "replication": replication,
                "condition": condition, "contamination": contamination, "seed": seed,
                "edge_rule_classifiable": threshold is not None,
                **recovery,
                **{f"wf_{k}": v for k, v in workflow.items()},
            })
    return rows


def run(
    replications: int = REPLICATIONS,
    *,
    n_values: tuple[int, ...] = N_VALUES,
    calibration_simulations: int = 25,
    bootstrap_samples: int = 100,
    truth_draws: int = TRUTH_DRAWS,
    workers: int = 1,
) -> list[dict[str, Any]]:
    keys = _job_keys(replications, n_values)
    children = np.random.SeedSequence(SEED).spawn(len(keys))
    settings = {
        "calibration_simulations": calibration_simulations,
        "bootstrap_samples": bootstrap_samples,
        "truth_draws": truth_draws,
    }
    jobs = [(key, child, settings) for key, child in zip(keys, children, strict=True)]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_run_job, jobs, chunksize=1))
    else:
        results = [_run_job(job) for job in jobs]
    return [row for chunk in results for row in chunk]


def _mean(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cell-level summary over replications; denominators are kept explicit."""
    cells: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (row["p"], row["strength"], row["N"], row["condition"], row["contamination"])
        cells[key].append(row)
    out: list[dict[str, Any]] = []
    for key, group in sorted(cells.items()):
        p, strength, n, condition, contamination = key
        entry: dict[str, Any] = {
            "p": p, "strength": strength, "N": n, "condition": condition,
            "contamination": contamination, "rows": len(group),
            "chance_top3_recall": CONTAMINATED_COUNT / n,
        }
        for metric in RECOVERY_METRICS:
            values = [r[f"shrunk_{metric}"] for r in group if r.get(f"shrunk_{metric}") is not None]
            entry[f"shrunk_{metric}"] = _mean(values)
            entry[f"shrunk_{metric}_n"] = len(values)
        entry["reached"] = sum(r["wf_reached"] is True for r in group)
        tails = [
            r["wf_reference_tail_probability"] for r in group
            if r["wf_reference_tail_probability"] is not None
        ]
        entry["tail_finite"] = len(tails)
        entry["tail_flagged"] = sum(t <= TAIL_FLAG for t in tails)
        entry["workflow_errors"] = sum(r["wf_workflow_status"] == "error" for r in group)
        recall = [
            r["wf_influence_top_k_recall"] for r in group
            if r["wf_influence_top_k_recall"] is not None
        ]
        entry["top3_recall"] = _mean(recall)
        entry["top3_recall_n"] = len(recall)
        out.append(entry)
    return out


def main() -> None:
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
