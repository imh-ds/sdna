"""Run the frozen composite-score study (docs/methodology/composite_score_study_v1.md)."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from sdna.fragility import FragilityTarget
from simulations.composite_dgp import (
    CARELESS_COUNT,
    CONDITIONS,
    TRUTH_DRAWS,
    generate_composite_dataset,
)
from simulations.edge_recovery import recovery_row
from simulations.full_workflow import derive_workflow_seeds, run_full_workflow

SEED = 20261004
N_VALUES = (50, 100, 150)
REPLICATIONS = 50
EDGE_THRESHOLD = 0.05
TAIL_FLAG = 0.05
RECOVERY_METRICS = (
    "sign_agreement", "rank_correlation", "edge_auc", "top_k_precision", "magnitude_ratio",
)


def run(
    replications: int = REPLICATIONS,
    *,
    n_values: tuple[int, ...] = N_VALUES,
    calibration_simulations: int = 25,
    bootstrap_samples: int = 100,
    truth_draws: int = TRUTH_DRAWS,
) -> list[dict[str, Any]]:
    keys = [(n, rep) for n in n_values for rep in range(replications)]
    children = np.random.SeedSequence(SEED).spawn(len(keys))
    rows: list[dict[str, Any]] = []
    for (n, replication), child in zip(keys, children, strict=True):
        seed = int(child.generate_state(1, dtype=np.uint32)[0])
        for condition in CONDITIONS:
            for careless in (0, CARELESS_COUNT):
                dataset = generate_composite_dataset(n, condition, careless, seed, truth_draws)
                recovery = recovery_row(dataset.X, dataset.partial_correlation, EDGE_THRESHOLD)
                workflow = run_full_workflow(
                    dataset,
                    target=FragilityTarget("relative", 0.5),
                    search_cap=2,
                    calibration_simulations=calibration_simulations,
                    bootstrap_samples=bootstrap_samples,
                    bootstrap_confidence=0.95,
                    certification_combination_budget=1000,
                    seeds=derive_workflow_seeds(seed),
                    calibration_require_reached=False,
                )
                workflow = {f"wf_{k}": v for k, v in workflow.items()}
                rows.append({
                    "N": n, "replication": replication, "condition": condition,
                    "careless": careless, "seed": seed, **recovery, **workflow,
                })
    return rows


def _mean(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cells: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        cells[(row["condition"], row["N"])].append(row)
    out: dict[str, Any] = {"cells": [], "matched_contrasts": []}
    for (condition, n), cell in sorted(cells.items()):
        clean = [r for r in cell if r["careless"] == 0]
        dirty = [r for r in cell if r["careless"] != 0]
        entry: dict[str, Any] = {
            "condition": condition, "N": n,
            "clean_rows": len(clean), "careless_rows": len(dirty),
        }
        for group, label in ((clean, "clean"), (dirty, "careless")):
            for metric in RECOVERY_METRICS:
                vals = [r[f"shrunk_{metric}"] for r in group if r[f"shrunk_{metric}"] is not None]
                entry[f"{label}_shrunk_{metric}"] = _mean(vals)
                entry[f"{label}_shrunk_{metric}_n"] = len(vals)
            entry[f"{label}_reached"] = sum(r["wf_reached"] is True for r in group)
            entry[f"{label}_certified"] = sum(r["wf_certified"] is True for r in group)
            tails = [
                r["wf_reference_tail_probability"] for r in group
                if r["wf_reference_tail_probability"] is not None
            ]
            entry[f"{label}_tail_finite"] = len(tails)
            entry[f"{label}_tail_flagged"] = sum(t <= TAIL_FLAG for t in tails)
            entry[f"{label}_right_censored"] = sum(
                r["wf_calibration_status"] == "right_censored" for r in group
            )
            entry[f"{label}_workflow_errors"] = sum(
                r["wf_workflow_status"] == "error" for r in group
            )
        recall = [
            r["wf_influence_top_k_recall"] for r in dirty
            if r["wf_influence_top_k_recall"] is not None
        ]
        rank = [
            r["wf_first_planted_reciprocal_rank"] for r in dirty
            if r["wf_first_planted_reciprocal_rank"] is not None
        ]
        entry["careless_top3_recall"] = _mean(recall)
        entry["careless_top3_recall_n"] = len(recall)
        entry["careless_first_rank_reciprocal"] = _mean(rank)
        entry["chance_top3_recall"] = CARELESS_COUNT / n
        out["cells"].append(entry)

    control = {
        (r["N"], r["replication"]): r
        for r in rows
        if r["condition"] == "continuous_control" and r["careless"] == 0
    }
    for condition in CONDITIONS:
        if condition == "continuous_control":
            continue
        for n in sorted({r["N"] for r in rows}):
            contrast: dict[str, Any] = {"condition": condition, "N": n}
            for metric in ("sign_agreement", "edge_auc", "top_k_precision", "magnitude_ratio"):
                diffs = []
                for r in rows:
                    if r["condition"] != condition or r["N"] != n or r["careless"] != 0:
                        continue
                    base = control[(n, r["replication"])]
                    a, b = r[f"shrunk_{metric}"], base[f"shrunk_{metric}"]
                    if a is not None and b is not None:
                        diffs.append(a - b)
                contrast[f"mean_diff_{metric}"] = _mean(diffs)
                contrast[f"mean_diff_{metric}_n"] = len(diffs)
            out["matched_contrasts"].append(contrast)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--replications", type=int, default=REPLICATIONS)
    args = parser.parse_args()
    rows = run(args.replications)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "rows.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.output_dir / "summary.json").write_text(
        json.dumps(summarize(rows), indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
