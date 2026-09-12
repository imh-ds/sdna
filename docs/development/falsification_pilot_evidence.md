# Falsification pilot evidence

## Run definition

This evidence was generated from the fixed-seed pilot configuration at commit
`006625d`. The run used all six configured scenarios, `N=[50, 100, 150]`,
`p=[5, 10, 20]`, and ten replications per cell, for 540 rows total. To keep
the validation run practical, it used the documented execution overrides
`calibration_simulations=2` and `bootstrap_samples=5`; the committed pilot
limits were `search_cap=2` and `certification_combination_budget=1000`.

The run used Python 3.12.1 and NumPy 2.5.2. It completed in 11.7 seconds on
the development machine. This is workflow evidence, not a publication-level
simulation result; the reduced calibration/bootstrap counts must be restored
before drawing substantive operating-characteristic conclusions.

## Scenario-level results

The summary metrics use finite, reached exact-fragility rows only. A rate
below 100% therefore indicates censoring from an unreached greedy search or an
unavailable reference comparison, not a zero-valued measurement.

| Scenario | Reached / certified | Reference tail available | Fragility vs `abs(rho)` | Fragility vs `abs(Wald z)` | Mean exact fragility | Influence recall |
|---|---:|---:|---:|---:|---:|---:|
| `clean_planted_edge` | 44 / 90 (48.9%) | 33 / 90 (36.7%) | 0.971 | 0.971 | 0.500 | n/a |
| `single_influential_case` | 80 / 90 (88.9%) | 44 / 90 (48.9%) | 0.902 | 0.909 | 0.613 | 0.567 |
| `coalition_contamination` | 71 / 90 (78.9%) | 24 / 90 (26.7%) | 0.864 | 0.852 | 1.268 | 0.689 |
| `mixture_subgroup` | 66 / 90 (73.3%) | 48 / 90 (53.3%) | 0.969 | 0.969 | 0.530 | 0.151 |
| `heavy_tails` | 19 / 90 (21.1%) | 17 / 90 (18.9%) | 0.998 | 0.998 | 0.211 | n/a |
| `collinearity_stress` | 0 / 90 (0.0%) | 0 / 90 (0.0%) | n/a | n/a | n/a | n/a |

The pilot also reported zero greedy-overestimation rate among rows that were
reached and certified. Because the pilot search cap is two deletions, this
does not establish that greedy search is exact beyond that bounded region.

## Interpretation boundaries

Finite in this pilot, subject to the censoring noted below:

- Fragility/magnitude and fragility/Wald rank associations for the first five
  scenarios.
- Influence-recovery summaries for `single_influential_case`,
  `coalition_contamination`, and `mixture_subgroup`.
- Reach, certification, and reference-reach rates for all scenarios.
- The clean false-flag rate, which was 0/33 among clean rows with an available
  reference-tail probability at the configured 0.05 threshold.

Censored or unavailable:

- Every scenario has some censored rows; `heavy_tails` reached only 19/90 and
  `collinearity_stress` reached none of its 90 rows.
- Influence recovery is not defined for clean and heavy-tail rows because
  those generators do not provide planted contaminated cases.
- Exact fragility is not defined for the unreached rows and for all
  collinearity rows.
- Reference-tail probabilities are available only when the observed and
  reference searches produce the required reached counts.

Structurally undefined rather than negative:

- Incremental AUC and contamination partial-rank association are `null` for
  every scenario. The current scenario-level grouping contains one
  contamination class per scenario, so these metrics do not have the two
  classes required for estimation. This must not be interpreted as evidence
  that fragility adds no information.

## Next methodological step

Before numerical optimization, add a paired cross-scenario contrast summary
that matches clean and contaminated rows by `N`, `p`, and replication, then
computes incremental AUC and partial-rank association on that
explicit contrast. Keep the current scenario-level summaries unchanged. The
next run should use the committed certification/search limits and record the
same timing metadata before any estimator optimization is considered.
