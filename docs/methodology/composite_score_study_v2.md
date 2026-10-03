# Composite-score validation study v2 (pre-specification)

Status: frozen before any v2 result was generated. v1
(`composite_score_study_v1.md`, evidence in `composite_score_evidence_v1.md`)
is unchanged. Changes after results exist go in a v3 file.

## Why v2

v1 left four gaps: it tested one contamination type (all-top-category
straight-liners), which is a poor test of influence detection under ceiling
skew; one edge strength (about 0.2); one network size (p = 6); and it could not
speak to the power of the fragility tail flag. v2 widens each, still for
five-item Likert composites at N = 50-150 and the unchanged v0.1 workflow.
Target estimand is again the composite-score network, not the latent network.

## Data-generating process

Same as v1 except as listed here.

1. **Network size:** `p in {6, 12}` composites (ring of `p` nodes, alternating
   signs). Items per composite K = 5, loading 0.7.
2. **Edge strength:** ring precision weight `w in {0.35, 0.18}` ("strong",
   "weak"; latent partial correlations about 0.29 and 0.15). Composite-level
   truth is smaller still.
3. **Conditions (4):** `continuous_control`, `symmetric`, `moderate_ceiling`,
   `severe_ceiling`, with the v1 cutpoints. `moderate_heterogeneous` is dropped
   because it matched `moderate_ceiling` in v1.
4. **Contamination (4 levels)**, always 3 randomly chosen respondents
   (without replacement) replaced; indices drawn before conditions so they are
   shared:
   - `none`.
   - `straight_top`: all items set to category 5 (continuous control: all
     latent items 2.0). Replicates v1.
   - `focal_discordant`: all five items of composite 0 set to category 1 and all
     five items of composite 1 set to category 5 (continuous control: latent
     items -2.0 and +2.0); all other composites keep their generated values.
     Because the focal edge (0, 1) has a positive true partial correlation,
     these respondents are extreme and discordant on exactly the focal pair.
   - `random_responder`: every item drawn uniformly from categories 1-5
     (continuous control: uniform on [-2, 2]); draws come from a separate
     seeded stream per dataset so that they are matched across conditions.
5. **Truth:** composite-level partial correlations from 1,000,000 uncontaminated
   draws per (p, strength, condition), as in v1. **True-edge rule (fixed now):**
   true edges are the `p` ring pairs `(i, i+1 mod p)`; the code must assert that
   every ring pair has `abs(truth)` above and every other pair below the
   threshold `0.5 x min ring abs(truth)` for that (p, strength, condition), and
   use that threshold for the edge-recovery metrics. If the assertion fails the
   cell is reported as not classifiable rather than altered.

## Design

- Grid: `p` (2) x strength (2) x `N in {50, 100, 150}` x condition (4) x
  contamination (4), 30 replications per cell: 192 cells, 5,760 datasets.
- **Matched design:** for each (p, strength, N, replication) one seed child
  generates latent draws, item errors, contaminated indices, and the
  random-responder stream; all condition-by-contamination cells reuse them.
  Seed root `20261006`, children spawned per (p, strength, N, replication) in
  lexicographic order.
- Focal edge (0, 1) for the SDNA workflow; it is a true edge in every cell.
- Workflow: `run_full_workflow`, relative target 0.5, `search_cap=2`,
  certification budget 1,000, 25 calibration simulations, 100 bootstrap
  draws, confidence 0.95, `calibration_require_reached=False`. Runs use the
  pinned kernel `OPENBLAS_CORETYPE=Haswell` where supported, and the local
  CPU and BLAS are recorded. Every scheduled row stays in its denominator with
  its status.

## Outcomes and reporting rules

All outcomes are reported with numerators and denominators and are never
recoded as zero when missing, unreached, or errored. Rows from different
contamination levels and conditions share datasets, so pooled intervals are
optimistic; the report states the number of distinct datasets behind each
pooled figure and does not present pooled Wilson intervals as independent.

1. **Edge recovery** (contamination `none`): sign agreement on true edges,
   edge AUC, top-k precision, rank correlation, magnitude ratio, with
   matched differences from `continuous_control`, by p and strength.
   Robustness: the same metrics under each contamination type.
2. **Planted-case detection:** top-3 exact-LOO recall on the focal edge by
   contamination type, condition, p, strength, N; chance level 3/N reported.
3. **Tail-flag power and size:** share of finite reference-tail probabilities
   at or below 0.05, for `none` (size) and each contamination type (power),
   with finite-tail counts; plus reach rates.
4. **Interaction questions** (descriptive only): whether detection depends on
   ceiling severity, edge strength, or p.

## Reading the results

No pass/fail thresholds. Reference points set now: chance sign agreement and
edge AUC 0.5; chance recall 3/N; `continuous_control` as the within-study
benchmark; tail-flag size should be small and power is whatever it is. Each
outcome gets one descriptive statement: comparable to control, degraded, or
indistinguishable from chance. The study cannot establish performance on real
data, other item counts or loadings, reverse-worded items, acquiescence, missing
data, or the latent network, and does not change any default.
