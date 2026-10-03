"""Run the frozen edge-recovery study (docs/methodology/edge_recovery_study_v1.md)."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from simulations.edge_recovery import recovery_row, ring_truth

SEED = 20261003
P_VALUES = (5, 8, 12)
N_VALUES = (50, 100, 150)
REPLICATIONS = 200
METRICS = ("sign_agreement", "rank_correlation", "edge_auc", "top_k_precision", "magnitude_ratio")


def run(replications: int = REPLICATIONS) -> list[dict[str, Any]]:
    cells = [(p, n) for p in P_VALUES for n in N_VALUES]
    children = np.random.SeedSequence(SEED).spawn(len(cells) * replications)
    rows: list[dict[str, Any]] = []
    index = 0
    for p, n in cells:
        covariance, truth = ring_truth(p)
        for replication in range(replications):
            rng = np.random.default_rng(children[index])
            index += 1
            X = rng.multivariate_normal(np.zeros(p), covariance, size=n)
            rows.append({"p": p, "N": n, "replication": replication, **recovery_row(X, truth)})
    return rows


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in P_VALUES:
        for n in N_VALUES:
            cell = [r for r in rows if r["p"] == p and r["N"] == n]
            entry: dict[str, Any] = {
                "p": p, "N": n, "rows": len(cell),
                "mean_lambda": float(np.mean([r["lambda"] for r in cell])),
            }
            for kind in ("shrunk", "ordinary"):
                for metric in METRICS:
                    values = [r[f"{kind}_{metric}"] for r in cell
                              if r[f"{kind}_{metric}"] is not None]
                    entry[f"{kind}_{metric}"] = float(np.mean(values)) if values else None
                    entry[f"{kind}_{metric}_n"] = len(values)
            out.append(entry)
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
