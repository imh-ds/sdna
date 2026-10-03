# Edge-recovery study v1 (pre-specification)

Status: frozen before any result was generated. Do not edit estimands or the
grid after results exist; add a v2 file instead.

## Question

At low sample sizes, does the base SDNA estimator (shrinkage partial-correlation
network, `sdna.estimation.fit_network`) preserve the **sign** and **rank order**
of true edges, and how strongly does shrinkage attenuate their magnitude? This
is the base layer beneath any fragility claim. It is not a fragility study.

## Data-generating process

Continuous Gaussian data from a fixed sparse network on `p` nodes: a ring
`i -- i+1 (mod p)` with precision off-diagonals alternating `-0.35, +0.35, ...`
(so partial correlations alternate positive/negative, about +/-0.29), built with
`simulations.dgp.construct_precision(p, edges, diagonal_margin=0.5)`. Truth is
the partial-correlation matrix of that precision matrix. For odd `p` the sign
pattern around the closing edge is not balanced; this is accepted and the truth
is computed exactly regardless.

## Grid and replications

- `p in {5, 8, 12}`, `N in {50, 100, 150}`, 200 replications per cell
  (1,800 datasets). Seeds come from `SeedSequence(20261003).spawn`, one child
  per (p, N, replication) in lexicographic order.
- No contamination, no ordinal data, no calibration: this study measures the
  estimator only.

## Metrics (all per dataset, then averaged within cell)

Computed by `simulations/edge_recovery.py` over the `p(p-1)/2` unique pairs:

1. `sign_agreement`: fraction of true edges whose estimated sign matches.
2. `rank_correlation`: Spearman correlation of estimates with truth over all pairs.
3. `edge_auc`: AUC of `abs(estimate)` for separating true edges from true non-edges.
4. `top_k_precision`: fraction of the `k` largest `abs(estimate)` pairs that are
   true edges, with `k` = number of true edges.
5. `magnitude_ratio`: mean `abs(estimate)` over true edges divided by mean
   `abs(truth)` (1.0 = no attenuation).
6. Shrinkage intensity `lambda`.

Each metric is reported for the shrinkage estimator and for the ordinary
(unshrunk) partial correlation where estimable (`N > p + 1`). Undefined values
are None and are excluded from means with the excluded count reported; they
are never recoded as zero.

## Reading the results

No pass/fail threshold is set. Reference points chosen before the run:
chance `sign_agreement` is 0.5; chance `edge_auc` and chance `rank_correlation`
are 0.5 and about 0 respectively; chance `top_k_precision` is the edge density
(`p / (p(p-1)/2)`). Results are descriptive operating characteristics of this
one DGP and do not establish performance on real data.
