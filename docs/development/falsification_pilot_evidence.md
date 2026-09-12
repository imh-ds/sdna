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

## Paired cross-scenario contrasts

The paired contrast layer matches clean and contaminated rows by `N`, `p`,
and replication. It excludes censored exact-fragility rows from the metric
calculations while retaining their counts. The AUC values are learned-weight,
in-sample benchmarks rather than out-of-sample predictive estimates.

| Contrast | Matched pairs | Censored pairs | Valid fragility rows | Baseline AUC | Augmented AUC | Partial rank |
|---|---:|---:|---:|---:|---:|---:|
| `clean_vs_single_influential_case` | 90 | 51 | 124 | 0.632 | 0.685 | -0.249 |
| `clean_vs_coalition_contamination` | 90 | 54 | 115 | 0.753 | 0.752 | -0.087 |
| `clean_vs_mixture_subgroup` | 90 | 56 | 110 | 0.509 | 0.611 | 0.154 |

These contrasts resolve the structural single-class limitation in the
scenario-level summaries. They do not remove censoring: in each contrast the
clean and contaminated reach rates differ, and the paired metrics use only
the finite reached rows.

## Budget sensitivity

The same fixed-seed 540-row pilot was rerun with the committed
`calibration_simulations=25` and `bootstrap_samples=100` settings. The
certification/search limits were unchanged.

| Execution profile | Calibration / bootstrap | Runtime | Paired contrast result |
|---|---:|---:|---|
| Reduced validation | 2 / 5 | 11.7 s | Same estimates reported above |
| Committed pilot | 25 / 100 | 56.4 s | Same estimates to 3 decimals |

The committed-budget run produced the following reference-tail availability
counts out of 90 rows per scenario: clean 30, single influential 39,
coalition 23, mixture 44, heavy tails 17, and collinearity 0. The reduced run
counts were 33, 44, 24, 48, 17, and 0 respectively. This difference is
expected because the reference-tail probability is censored if any of the
calibration reference searches fails to reach; it is not evidence of a change
in the underlying fragility contrast. No bootstrap resamples were rejected in
either execution profile.

## Next methodological step

Freeze the bounded pilot configuration and use these results to pre-specify
which contrast metrics are descriptive, censored, or undefined. Numerical
optimization remains deferred; the observed 56.4-second committed pilot is
now the baseline against which any future optimization must be compared.
