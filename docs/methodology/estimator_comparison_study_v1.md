# Estimator comparison study v1 (pre-specification)

Status: frozen before any result was generated. Changes after results exist go
in a v2 file.

## Question

SDNA's stated aim is to be more informative than EBICglasso (and Bayesian
Gaussian graphical models) at small samples, where those methods are often said
to need roughly 200 or more observations. At N = 50-300, does SDNA's shrinkage
partial-correlation estimate (`sdna.estimation.fit_network`) recover the true
network at least as well as EBICglasso, and at what N does EBICglasso catch up?

This compares **estimates of a known network**. It does not test fragility or
influence diagnostics.

## Estimators

1. **SDNA:** `fit_network(X).partial_correlation` (analytic shrinkage toward
   the identity, unchanged v0.1 code).
2. **EBICglasso (Python re-implementation, "EBIC-py"):** an approximation of
   `qgraph::EBICglasso` / `bootnet` defaults, not that code. Sample correlation
   matrix `S`; 100 penalties log-spaced from `max abs offdiag(S)` down to
   `0.01 x` that value; `sklearn.covariance.graphical_lasso` at each penalty
   (cold starts, public API); select the penalty minimizing
   `EBIC = -2L + E log n + 4 gamma E log p`, with
   `L = n/2 (log det K - tr(S K))`, `E` the number of nonzero upper-triangle
   entries of `K`, and `gamma = 0.5`; output partial correlations
   `-K_ij / sqrt(K_ii K_jj)` with no extra thresholding.
   **Known difference:** scikit-learn's graphical lasso penalizes the diagonal,
   whereas `qgraph` does not. No R is available in this environment, so this
   approximation is not validated against `qgraph`, and a Bayesian estimator
   (BGGM) is **not** included. Conclusions apply to EBIC-py only; the existing
   R comparator scripts remain the route to a faithful check.
3. **Ordinary partial correlation** (unshrunk), when `N > p + 1`, as a
   reference.

## Data

Truth network: alternating-sign ring on `p` nodes, as in
`edge_recovery_study_v1.md`; true edges are the `p` ring pairs.

- **Part A, Gaussian ring:** `p in {5, 8, 12}`, precision weight
  `w in {0.35 (strong), 0.18 (weak)}`.
- **Part B, Likert composites** (`composite_dgp_v2`, contamination `none`):
  `p in {6, 12}`, strength `in {strong, weak}`, condition `in
  {continuous_control, severe_ceiling}`; truth is the composite-level partial
  correlation, true-edge rule as in `composite_score_study_v2.md`.
- `N in {30, 50, 100, 150, 200, 300}`, 100 replications per cell. Part A: 3 x 2
  x 6 x 100 = 3,600 datasets; Part B: 2 x 2 x 2 x 6 x 100 = 4,800 datasets. All
  estimators use the same dataset in each replication (matched). Seed root
  `20261008`, children spawned per (cell, replication) in lexicographic order.

## Outcomes

Computed per dataset and averaged within cell; undefined values are None and
excluded with the count reported.

1. **Recovery (all estimators):** sign agreement on true edges (an estimated
   zero counts as wrong), edge AUC of `abs(estimate)` for separating true
   edges from non-edges (ties count half), top-k precision with expected
   credit under random tie-breaking, Spearman rank correlation with truth over
   all pairs (None for a constant estimate), and magnitude ratio.
2. **Selection (EBIC-py only, because SDNA does not select edges):**
   sensitivity, specificity of the nonzero edge set, and the share of datasets
   returning an empty network.
3. **Paired contrasts:** per-dataset difference SDNA minus EBIC-py in edge AUC
   and in sign agreement, with the mean difference and its standard error over
   the 100 independent replications in each cell, and the share of datasets
   where SDNA is higher / equal / lower.
4. **Parity point:** the smallest `N` in the grid at which the paired mean
   edge-AUC difference is within one standard error of zero or favors EBIC-py.

## Reading the results

No pass/fail threshold. Per cell the report states, from the paired mean
difference and its standard error: SDNA better, no clear difference, or EBIC-py
better. A claim that SDNA is "more informative at small N" is supported only
for the cells and metrics where it is better; it is not supported by SDNA
being merely competitive. SDNA outputs a dense estimate and cannot answer "which
edges exist" without an added selection rule; Outcome 2 therefore cannot be
compared, and that asymmetry is stated in the report. Results are simulation
evidence for this DGP family, with the stated caveat on EBIC-py, and do not
establish performance on real data.
