"""POST-HOC exploratory check (not pre-specified): does the glasso path rank edges well?

EBIC-py can return an empty network at small N, which scores at chance on ranking by
construction. This asks whether the underlying graphical-lasso family ranks true edges
well when its penalty path is used as a ranking (edges that enter the model at a larger
penalty rank higher), compared with SDNA and with EBIC-selected output, on fresh datasets.
"""

from __future__ import annotations

import argparse
import json
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.covariance import graphical_lasso
from sklearn.exceptions import ConvergenceWarning

from sdna.estimation import fit_network
from simulations.composite_dgp_v2 import STRENGTHS
from simulations.ebic_glasso import ebic_glasso
from simulations.edge_recovery import ring_truth
from simulations.metrics import auc

SEED = 20261009
P_VALUES = (8, 12)
N_VALUES = (30, 50, 100, 150, 200, 300)
REPLICATIONS = 100


def path_scores(X: Any, n_lambda: int = 100, ratio: float = 0.01) -> Any:
    """Entry penalty per pair (larger = enters earlier); zero if never selected."""
    p = X.shape[1]
    S = np.corrcoef(X, rowvar=False)
    upper = np.triu_indices(p, k=1)
    lam_max = float(np.abs(S[upper]).max())
    alphas = np.exp(np.linspace(np.log(lam_max), np.log(lam_max * ratio), n_lambda))
    entry = np.zeros(len(upper[0]))
    for alpha in alphas:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", ConvergenceWarning)
                _, precision = graphical_lasso(S, alpha=float(alpha), max_iter=200)
        except (FloatingPointError, np.linalg.LinAlgError):
            continue
        entered = (np.abs(precision[upper]) > 1e-10) & (entry == 0.0)
        entry[entered] = alpha
    return entry


def _job(args: tuple[Any, ...]) -> dict[str, Any]:
    (p, strength, n, _rep), child = args
    seed = int(child.generate_state(1, dtype=np.uint32)[0])
    covariance, truth = ring_truth(p, STRENGTHS[strength])
    X = np.random.default_rng(seed).multivariate_normal(np.zeros(p), covariance, size=n)
    upper = np.triu_indices(p, k=1)
    labels = (np.abs(truth[upper]) > 1e-8).astype(int)
    sdna = np.abs(fit_network(X).partial_correlation[upper])
    ebic = np.abs(ebic_glasso(X)[0][upper])
    return {
        "p": p, "strength": strength, "N": n,
        "sdna_auc": auc(labels, sdna),
        "ebic_selected_auc": auc(labels, ebic),
        "glasso_path_auc": auc(labels, path_scores(X)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--replications", type=int, default=REPLICATIONS)
    args = parser.parse_args()
    keys = [
        (p, s, n, r)
        for p in P_VALUES for s in STRENGTHS for n in N_VALUES for r in range(args.replications)
    ]
    children = np.random.SeedSequence(SEED).spawn(len(keys))
    jobs = list(zip(keys, children, strict=True))
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(_job, jobs, chunksize=4))
    summary = []
    for p in P_VALUES:
        for s in STRENGTHS:
            for n in N_VALUES:
                g = [r for r in rows if (r["p"], r["strength"], r["N"]) == (p, s, n)]
                summary.append({
                    "p": p, "strength": s, "N": n, "rows": len(g),
                    **{k: float(np.mean([r[k] for r in g]))
                       for k in ("sdna_auc", "ebic_selected_auc", "glasso_path_auc")},
                })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
