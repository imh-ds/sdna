# Edge-recovery evidence v1

Protocol: [`edge_recovery_study_v1.md`](../methodology/edge_recovery_study_v1.md)
(frozen before the run). Runner: `tools/run_edge_recovery.py` at commit
`62ed281` on branch `codex/viability-checks`; Python 3.14.3, NumPy 2.3.5;
1,800 datasets (9 cells x 200 replications), run locally in about 2 seconds.
Raw rows are regenerable with `python tools/run_edge_recovery.py <dir>` and are
not committed.

## Results (means over 200 datasets per cell)

`lambda` = mean shrinkage intensity. "mag" = `magnitude_ratio` (1.0 = no
attenuation). Ordinary (unshrunk) partial correlations were estimable in all
1,800 datasets (`N > p + 1` everywhere); no metric was undefined.

| p | N | lambda | Shrunk sign | Shrunk rank corr | Shrunk edge AUC | Shrunk top-k prec. | Shrunk mag | Ordinary edge AUC | Ordinary top-k prec. | Ordinary mag |
|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 5 | 50 | 0.30 | 0.98 | 0.85 | 0.87 | 0.81 | 0.69 | 0.86 | 0.79 | 0.99 |
| 5 | 100 | 0.16 | 1.00 | 0.90 | 0.96 | 0.92 | 0.82 | 0.95 | 0.90 | 0.98 |
| 5 | 150 | 0.11 | 1.00 | 0.92 | 0.99 | 0.98 | 0.89 | 0.99 | 0.97 | 1.00 |
| 8 | 50 | 0.41 | 0.98 | 0.71 | 0.88 | 0.72 | 0.58 | 0.85 | 0.68 | 1.00 |
| 8 | 100 | 0.26 | 1.00 | 0.77 | 0.97 | 0.88 | 0.74 | 0.96 | 0.85 | 0.99 |
| 8 | 150 | 0.18 | 1.00 | 0.79 | 0.99 | 0.95 | 0.81 | 0.99 | 0.93 | 0.99 |
| 12 | 50 | 0.54 | 0.98 | 0.61 | 0.90 | 0.68 | 0.46 | 0.84 | 0.59 | 1.01 |
| 12 | 100 | 0.34 | 1.00 | 0.66 | 0.97 | 0.85 | 0.65 | 0.95 | 0.80 | 0.99 |
| 12 | 150 | 0.25 | 1.00 | 0.67 | 0.99 | 0.93 | 0.75 | 0.99 | 0.90 | 1.01 |

Chance references (pre-specified): sign agreement 0.5, edge AUC 0.5, rank
correlation about 0, top-k precision equal to edge density (0.50 at p=5, 0.29 at
p=8, 0.18 at p=12).

## Findings

1. **Direction is recovered.** For true edges of partial correlation about
   +/-0.29, the estimated sign matched in 98-100% of cases at every N=50-150 cell.
2. **Edges are separable from non-edges.** Edge AUC was 0.87-0.99, well above
   0.5, and top-k precision exceeded chance by a wide margin in every cell
   (for example 0.68 against chance 0.18 at the hardest cell, p=12, N=50).
3. **Magnitude is attenuated, as designed.** Shrinkage shrinks true edges to
   46-89% of their size, worst at large `p`/small `N`. Estimates should be read
   as ordered/directional, not as calibrated effect sizes. The unshrunk estimator
   is nearly unbiased in magnitude (0.98-1.01).
4. **Shrinkage helps ranking where it matters.** The shrunk estimator had equal
   or slightly better edge AUC and top-k precision than the ordinary
   estimator in all nine cells (largest gap at p=12, N=50: AUC 0.90 vs 0.84,
   top-k 0.68 vs 0.59), at the cost of the attenuation above.
5. **Lambda depends on signal, not just `N`/`p`.** Here `lambda` was 0.11-0.54.
   In the earlier v0.1 falsification pilot (one weak edge of 0.2 among nulls)
   it was 0.66-0.97 and observed edges were close to zero. Heavy attenuation in
   that pilot reflects a weak-signal, near-null network, not a general property
   of the estimator at those sample sizes.

## Limits

One Gaussian DGP, one ring topology with moderate edges (about 0.29), no
contamination, no non-normality, no ordinal data. Weaker true edges (for
example 0.1-0.15) were not studied and would shrink harder. This is
descriptive evidence about the base estimator, not about fragility diagnostics
and not about real survey data.
