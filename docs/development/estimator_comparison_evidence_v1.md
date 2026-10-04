# Estimator comparison evidence v1

Protocol: [`estimator_comparison_study_v1.md`](../methodology/estimator_comparison_study_v1.md)
(frozen before the run). Runner: `tools/run_estimator_comparison.py` at commit
`907cdab` on branch `codex/estimator-comparison`; local run, 10 worker
processes, `OPENBLAS_CORETYPE=Haswell`, Python 3.14.3, NumPy 2.3.5,
scikit-learn 1.8.0, Windows 11; 37 min 27 s. 8,400 of 8,400 scheduled datasets
(Part A 3,600; Part B 4,800) completed; 84 cells of 100 replications each.
Raw rows are regenerable with
`python -m tools.run_estimator_comparison <dir> --workers 10` and are not
committed.

One implementation constraint was recorded before the run: scikit-learn's
public `graphical_lasso` has no warm-start argument, so the penalty path uses
cold starts (the protocol text was changed to say so before any result existed).

## Caveats that bound every conclusion

1. **The competitor is an approximation.** "EBIC-py" is a Python
   re-implementation of the EBICglasso recipe, not `qgraph`/`bootnet`. It
   penalizes the diagonal (qgraph does not) and is **not validated against
   qgraph**; no R is available here. Bayesian methods (BGGM) were not run.
2. **Dense versus sparse output.** SDNA returns a dense estimate and cannot say
   which edges exist; EBICglasso selects an edge set. Ranking and direction
   are comparable; edge selection is not (selection metrics are reported for
   EBIC-py only).
3. An empty EBIC-py network scores at chance on ranking and sign by
   construction. That is a property of its selection rule, which the post-hoc
   check below separates from the estimator.
4. Simulation evidence on a ring-network family with 0.15-0.29 latent partial
   correlations (Part B: composite-level truth 0.13-0.24); no real data.

## Results (means of cell means; each cell is 100 matched datasets)

Edge AUC (|estimate| separating true edges from non-edges; 0.5 is chance), sign
agreement (an estimated zero counts as wrong), and top-k precision (expected
credit under random tie-breaking). Ordinary = unshrunk partial correlation,
available when N > p + 1.

**Part A, Gaussian ring (p = 5, 8, 12; strong and weak edges)**

| N | AUC: SDNA / EBIC-py / ordinary | Sign: SDNA / EBIC-py | Top-k: SDNA / EBIC-py | EBIC-py empty network | EBIC-py sensitivity / specificity |
|--:|---|---|---|--:|---|
| 30 | 0.73 / 0.50 / 0.69 | 0.86 / 0.01 | 0.56 / 0.33 | 96% | 0.01 / 1.00 |
| 50 | 0.82 / 0.52 / 0.79 | 0.94 / 0.05 | 0.66 / 0.34 | 91% | 0.05 / 0.99 |
| 100 | 0.93 / 0.61 / 0.91 | 0.99 / 0.23 | 0.81 / 0.44 | 70% | 0.23 / 0.96 |
| 150 | 0.97 / 0.74 / 0.96 | 1.00 / 0.47 | 0.89 / 0.61 | 46% | 0.47 / 0.93 |
| 200 | 0.98 / 0.81 / 0.98 | 1.00 / 0.63 | 0.93 / 0.72 | 32% | 0.63 / 0.91 |
| 300 | 1.00 / 0.91 / 1.00 | 1.00 / 0.83 | 0.97 / 0.86 | 14% | 0.83 / 0.88 |

**Part B, Likert composites (p = 6, 12; strong/weak; continuous control and severe ceiling skew)**

| N | AUC: SDNA / EBIC-py / ordinary | Sign: SDNA / EBIC-py | Top-k: SDNA / EBIC-py | EBIC-py empty network | EBIC-py sensitivity / specificity |
|--:|---|---|---|--:|---|
| 30 | 0.64 / 0.50 / 0.61 | 0.73 / 0.00 | 0.43 / 0.29 | 98% | 0.00 / 1.00 |
| 50 | 0.71 / 0.50 / 0.69 | 0.84 / 0.01 | 0.52 / 0.29 | 96% | 0.01 / 1.00 |
| 100 | 0.82 / 0.52 / 0.80 | 0.94 / 0.03 | 0.64 / 0.31 | 90% | 0.03 / 1.00 |
| 150 | 0.89 / 0.55 / 0.88 | 0.98 / 0.10 | 0.74 / 0.34 | 83% | 0.10 / 0.99 |
| 200 | 0.93 / 0.60 / 0.92 | 0.99 / 0.21 | 0.80 / 0.42 | 70% | 0.21 / 0.98 |
| 300 | 0.97 / 0.70 / 0.96 | 1.00 / 0.41 | 0.88 / 0.56 | 52% | 0.41 / 0.96 |

**Paired contrasts (SDNA minus EBIC-py, per dataset; 95% interval = mean +/- 1.96 SE
over 100 independent replications):**

- Edge AUC: SDNA clearly higher in 76 of 84 cells, EBIC-py clearly higher in 0;
  no clear difference in 8 cells, all strong-edge: Gaussian N >= 150-300
  (p=5 N=150, 200, 300; p=8 N=200, 300; p=12 N=200, 300) and composite control p=6
  N=300. For **weak** edges, EBIC-py was still clearly behind at N = 300
  (Gaussian AUC 0.72-0.94 versus SDNA 0.99; p=12 weak: 47% of EBIC-py networks
  empty).
- Sign agreement: SDNA clearly higher in 78 of 84 cells, never lower.
  Top-k precision: SDNA clearly higher in 75, EBIC-py higher in 1.
- Parity point (protocol Outcome 4): reached only for strong edges, at about
  N = 150-200 for Gaussian data; not reached by N = 300 for weak edges or for
  most composite cells.

## Post-hoc check (exploratory, not pre-specified)

`tools/explore_glasso_path_ranking.py`, fresh seeds (`20261009`), Gaussian ring
p = 8 and 12, strong and weak, N = 30-300, 100 replications per cell: rank
edges by the largest penalty at which they enter the graphical-lasso path
(instead of by the EBIC-selected model). Edge AUC pooled over those four
(p, strength) groups:

| N | SDNA | EBIC-selected | Graphical-lasso path ranking |
|--:|--:|--:|--:|
| 30 | 0.725 | 0.502 | 0.733 |
| 50 | 0.825 | 0.504 | 0.828 |
| 100 | 0.928 | 0.571 | 0.931 |
| 150 | 0.966 | 0.708 | 0.966 |
| 200 | 0.983 | 0.780 | 0.985 |
| 300 | 0.996 | 0.913 | 0.996 |

## Interpretation

1. **Supported:** under the default EBIC selection (gamma = 0.5), EBICglasso-
   style output is often empty or near empty below N of about 150-200
   (96% empty at N = 30; still 14-52% empty at N = 300 for weak or skewed
   composite cases), so it conveys little about direction or rank at small N.
   SDNA's dense output keeps direction (sign 0.84-0.99) and useful ranking
   (edge AUC 0.71-0.93) at N = 50-100. This matches the premise that EBICglasso
   needs about 200 or more observations, and shows it can need more for weak
   edges and skewed composites.
2. **Not supported:** that SDNA's *estimator* is more accurate than the
   graphical-lasso family. Ranking edges by the lasso path matches SDNA within
   about 0.01 AUC at every N, and SDNA's gain over the unshrunk partial
   correlation is small (edge AUC +0.04 at N = 30, +0.03 at N = 50, +0.02 at
   N = 100, +0.01 at N = 150 in Gaussian data; +0.01 to +0.03 in composites).
   The gap to EBIC-py comes from EBIC's conservative edge selection, not from
   a better dense estimator. The same ranking is available from raw partial
   correlations when N > p + 1.
3. **Not tested:** the regime where the ordinary estimator is unavailable
   (p >= N - 1) and shrinkage is required (p was at most 12 here); a faithful
   `qgraph`/BGGM comparison; other selection rules for EBIC (smaller gamma) or
   other methods (for example GeneNet-style local false-discovery selection or
   Bayesian credible-interval selection); real data.

## What this means for SDNA's value

The package's estimator is a competent small-sample dense estimator, but it is
not shown to beat other dense estimators; the evidence for "more informative
than EBICglasso at small N" is specific to EBICglasso's selection rule. A
defensible claim is narrower: shrinkage partial correlations give a stable,
fast, closed-form network estimate at N = 30-150, which is the property that
makes exact leave-one-out and structured-deletion diagnostics cheap.
