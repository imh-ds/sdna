# Composite-score validation study v1 (pre-specification)

Status: frozen before any result was generated. Changes after results exist go
in a v2 file. Implements Priority 2 of
`docs/development/ai_handoff_2026-10-03.md`.

## Question

When each network variable is the **mean of several 1-5 Likert items**, and item
responses pile up at the top category, does the *unchanged* v0.1 SDNA workflow
give usable, directionally informative output at low sample sizes?

Target estimand: the **composite-score network**, i.e. the partial-correlation
matrix of the composite variables under the data-generating process,
not the latent-variable network. Estimates are compared with composite-level
truth. This is not an ordinal or polychoric analysis and tests no new estimator.

## Data-generating process

1. Latent constructs `eta` (p = 6) are Gaussian with the partial-correlation
   structure of `tools/run_edge_recovery.ring_truth(6)` (alternating-sign ring,
   partial correlations about +/-0.29), rescaled to unit variances.
2. Each construct has K = 5 items: `x = 0.7 * eta + sqrt(1 - 0.49) * e`,
   `e ~ N(0,1)` independent (unit-variance items, composite omega about 0.83).
3. Item response = category 1-5 from the cutpoints below applied to `x`;
   composite = mean of the five integer responses.
4. Conditions (cutpoints on the unit-variance latent item scale; the upper-
   category share is `P(x > last cutpoint)` under a standard normal):
   - `continuous_control`: no thresholding; composite = mean of the five
     continuous `x`.
   - `symmetric`: (-1.5, -0.5, 0.5, 1.5); about 7% in category 5.
   - `moderate_ceiling`: (-2.0, -1.2, -0.5, 0.25); about 40% in category 5.
   - `severe_ceiling`: (-2.5, -1.8, -1.2, -0.4); about 66% in category 5.
   - `moderate_heterogeneous`: moderate cutpoints shifted by item offsets
     (-0.4, -0.2, 0, +0.2, +0.4) for items 1-5 of every construct.
5. Contamination factor `careless in {0, 3}` applied to every condition:
   3 randomly chosen respondents (without replacement) are replaced by
   straight-liners: all 30 items = category 5 (ordinal conditions) or all
   items = 2.0 on the latent scale (`continuous_control`). Straight-liners are
   the planted cases for influence recovery.
6. Truth for each condition is the partial-correlation matrix of the composites
   from 1,000,000 uncontaminated draws (seeded, chunked). Contaminated datasets
   use the same uncontaminated truth. Truth is fixed per condition, not per
   replication.

Not included (deferred, not tested): reverse-worded items, acquiescence or
response-style factors, local item dependence, missing data, `p` other than 6.

## Design

- `N in {50, 100, 150}`, 50 replications per (N, condition, careless) cell:
  3 x 5 x 2 x 50 = 1,500 datasets.
- **Matched design:** for each (N, replication) one seed child generates the
  latent draws, item errors, and straight-liner indices; all ten
  condition-by-contamination cells reuse them, so differences between cells
  are due to thresholding/contamination only. Seed root `20261004`, children
  spawned per (N, replication) in lexicographic order.
- Focal edge for the SDNA workflow: (0, 1), a true edge in every condition.
- Workflow settings (the frozen production baseline): `run_full_workflow` with
  relative target 0.5, `search_cap=2`, certification budget 1,000,
  `calibration_simulations=25`, `bootstrap_samples=100`, confidence 0.95,
  `calibration_require_reached=False`. Data are never dropped; failed or
  unreached stages stay in the denominator of 1,500 rows with their status.

## Outcomes and reporting rules

All outcomes are reported per condition and N with explicit denominators.
Missing, unreached, or errored results are never recoded as zero.

1. **Edge recovery** (clean datasets, `careless = 0`): shrinkage-estimator sign
   agreement, edge AUC, top-k precision, rank correlation, and magnitude ratio
   against composite-level truth (all 15 pairs), using
   `simulations/edge_recovery.py`, with the matched `continuous_control`
   alongside. Edge recovery on contaminated datasets is reported as a
   robustness secondary.
2. **Fragility availability** at the focal edge: counts of reached, certified,
   finite reference tail, right-censored tail, errors.
3. **Planted-case detection:** for `careless = 3`, top-3 recall of the
   straight-liners by absolute exact-LOO change in the focal edge, with chance
   level 3/N (reported). Also first-planted reciprocal rank.
4. **Tail flag:** share of finite reference-tail probabilities at or below 0.05,
   separately for clean and contaminated datasets, with denominators. This is
   descriptive; calibration draws are Gaussian while the data are bounded and
   discrete, so a mismatch is possible and is part of what is examined.
5. **Matched contrasts:** difference between each ordinal condition and
   `continuous_control` in outcomes 1-4 for the same (N, replication).

## Reading the results

No pass/fail threshold is set. Reference points chosen now: chance sign
agreement 0.5, chance edge AUC 0.5, chance top-3 recall 3/N, and the
`continuous_control` result as the within-study benchmark. The study can
support one of three descriptive statements per outcome: comparable to the
control, degraded relative to the control, or collapsed to chance. It cannot
establish performance on real data, other `p`, other item counts, or other
response-style processes, and does not validate the latent-network estimand.

## Amendment 1 (recorded before any composite-study result was generated)

Found while checking the generator, before running any workflow: measurement
error and thresholding make every composite-level partial correlation
non-zero (non-ring pairs are about -0.02 to +0.003), so "true edge = non-zero
truth" would classify all 15 pairs as edges and leave edge AUC and top-k
precision undefined. Clarification: the **true-edge set is the six designed
ring pairs** (composite-level truth about 0.17-0.24 in magnitude); the other
nine pairs are non-edges. Implemented as `edge_threshold=0.05` on
`abs(truth)`, which separates the two sets in every condition. Sign agreement
and magnitude ratio are computed on the six ring pairs against composite-level
truth signs and magnitudes; rank correlation uses all 15 pairs. No other part
of the protocol changes.
