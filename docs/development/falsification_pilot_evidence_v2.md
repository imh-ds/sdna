# Falsification pilot evidence v2

## Purpose and provenance

This report records the hosted execution of the pre-specified v0.1 primary
validation matrix. It is a new evidence record; the earlier
[`falsification_pilot_evidence.md`](falsification_pilot_evidence.md) remains
available as the preceding local pilot report and is not overwritten.

The artifact was produced by the manually dispatched
[`SDNA v0.1 primary validation`](https://github.com/imh-ds/sdna/actions/runs/34774537731)
workflow on the merged `main` commit `e29bfd9548333c561b6cec79456c86038ee07c64`.
The artifact metadata reports:

- Python `3.11.16`;
- NumPy `2.4.6`;
- package version `0.1.0a0`;
- configuration checksum
  `3dbc697c4165f15174143a51ad251a677ec1c65e559eecd841f69c7c8a81118d`;
- 540 result rows and 96.9 seconds of hosted runtime.

The runner completed the full workflow: simulation, calibration, Wald
comparison, shrinkage-bootstrap comparison, row-level metadata, JSON summary,
Markdown summary, and the profile-aware primary validator. The artifact was
accepted as a primary run (`smoke=false`). This is executable bounded evidence,
not publication-level validation or a claim that the method is calibrated for
all data-generating processes.

## Frozen run definition

The machine-readable source is
[`falsification_pilot.json`](../../simulations/configs/falsification_pilot.json),
as specified in
[`validation_matrix_v1.md`](../methodology/validation_matrix_v1.md).

| Setting | Value |
|---|---|
| Root seed | `20260910` |
| Scenarios | six registered scenarios |
| `N` | `50`, `100`, `150` |
| `p` | `5`, `10`, `20` |
| Replications per scenario/cell | `10` |
| Primary target | relative attenuation `0.5` |
| Greedy search cap | `2` deletions |
| Certification budget | `1000` combinations |
| Calibration simulations | `25` per row |
| Bootstrap draws | `100` per row |
| Bootstrap confidence | `0.95` |
| Calibration reach mode | `require_reached=False` |

The design contains `6 × 3 × 3 × 10 = 540` rows. All six scenarios have 90
rows, and every `N × p` cell has ten rows.

## Technical acceptance

The hosted artifact passed the primary profile checks:

- all 540 expected rows were produced;
- all six scenarios and all 54 scenario/cell combinations were present;
- configuration checksum and provenance metadata were valid;
- schema, finite-value, range, and summary invariants passed;
- no simulation or workflow error occurred;
- no bootstrap resamples were rejected in any row.

This run does not by itself constitute a duplicate matched-environment rerun.
The reproducibility contract is encoded in the configuration, row seeds, and
metadata; an explicitly matched rerun remains the appropriate confirmation if
bitwise or field-level reproducibility is needed.

## Scenario-level results

The counts below are calculated directly from the hosted `results.csv`. A
reached row has a finite observed exact-fragility result in this run. A
reference-tail value is finite only when the observed search reached. The
reference search itself uses right-censored draws when `require_reached=False`;
therefore `mean reference reached` is the mean of the row-level
`reference_reached_fraction` values and is not the denominator for reference
tail availability.

| Scenario | Reached | Censored | Certified | Exact finite | Tail finite | Mean reference reached | Clean flags / finite tails |
|---|---:|---:|---:|---:|---:|---:|---:|
| `clean_planted_edge` | 44/90 (48.9%) | 46/90 (51.1%) | 44/90 (48.9%) | 44/90 | 44/90 | 48.6% | 1/44 (2.3%) |
| `single_influential_case` | 80/90 (88.9%) | 10/90 (11.1%) | 80/90 (88.9%) | 80/90 | 80/90 | 59.8% | n/a |
| `coalition_contamination` | 71/90 (78.9%) | 19/90 (21.1%) | 71/90 (78.9%) | 71/90 | 71/90 | 29.6% | n/a |
| `mixture_subgroup` | 66/90 (73.3%) | 24/90 (26.7%) | 66/90 (73.3%) | 66/90 | 66/90 | 68.9% | n/a |
| `heavy_tails` | 19/90 (21.1%) | 71/90 (78.9%) | 19/90 (21.1%) | 19/90 | 19/90 | 22.8% | n/a |
| `collinearity_stress` | 0/90 (0.0%) | 90/90 (100.0%) | 0/90 (0.0%) | 0/90 | 0/90 | 0.0% | n/a |

The clean false-flag rate is descriptive: one of the 44 finite clean
reference-tail values was at or below `0.05`. It is not a validated
confirmatory type-I-error estimate. The `reference_reached` fraction is lower
than one in most reached rows because some reference searches remain censored;
those draws are retained above the bounded search cap in the
plus-one-corrected denominator.

### Per-cell reach and validity denominators

Each count has denominator ten. `Tail finite` is the number of rows with a
finite observed reference-tail probability. `Clean flags / tails` is reported
only for the clean scenario; `—` means the metric is structurally undefined.

| Scenario | N | p | Reached | Censored | Certified | Exact finite | Tail finite | Mean reference reached | Clean flags / tails |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `clean_planted_edge` | 50 | 5 | 6 | 4 | 6 | 6 | 6 | 62.8% | 0/6 |
| `clean_planted_edge` | 50 | 10 | 5 | 5 | 5 | 5 | 5 | 38.8% | 0/5 |
| `clean_planted_edge` | 50 | 20 | 8 | 2 | 8 | 8 | 8 | 60.0% | 1/8 |
| `clean_planted_edge` | 100 | 5 | 3 | 7 | 3 | 3 | 3 | 47.2% | 0/3 |
| `clean_planted_edge` | 100 | 10 | 4 | 6 | 4 | 4 | 4 | 39.6% | 0/4 |
| `clean_planted_edge` | 100 | 20 | 6 | 4 | 6 | 6 | 6 | 62.4% | 0/6 |
| `clean_planted_edge` | 150 | 5 | 2 | 8 | 2 | 2 | 2 | 29.2% | 0/2 |
| `clean_planted_edge` | 150 | 10 | 4 | 6 | 4 | 4 | 4 | 45.2% | 0/4 |
| `clean_planted_edge` | 150 | 20 | 6 | 4 | 6 | 6 | 6 | 52.0% | 0/6 |
| `single_influential_case` | 50 | 5 | 10 | 0 | 10 | 10 | 10 | 42.8% | — |
| `single_influential_case` | 50 | 10 | 10 | 0 | 10 | 10 | 10 | 64.8% | — |
| `single_influential_case` | 50 | 20 | 10 | 0 | 10 | 10 | 10 | 55.6% | — |
| `single_influential_case` | 100 | 5 | 9 | 1 | 9 | 9 | 9 | 61.6% | — |
| `single_influential_case` | 100 | 10 | 9 | 1 | 9 | 9 | 9 | 64.4% | — |
| `single_influential_case` | 100 | 20 | 6 | 4 | 6 | 6 | 6 | 60.4% | — |
| `single_influential_case` | 150 | 5 | 8 | 2 | 8 | 8 | 8 | 64.4% | — |
| `single_influential_case` | 150 | 10 | 10 | 0 | 10 | 10 | 10 | 57.6% | — |
| `single_influential_case` | 150 | 20 | 8 | 2 | 8 | 8 | 8 | 66.4% | — |
| `coalition_contamination` | 50 | 5 | 5 | 5 | 5 | 5 | 5 | 11.2% | — |
| `coalition_contamination` | 50 | 10 | 6 | 4 | 6 | 6 | 6 | 21.6% | — |
| `coalition_contamination` | 50 | 20 | 10 | 0 | 10 | 10 | 10 | 33.6% | — |
| `coalition_contamination` | 100 | 5 | 8 | 2 | 8 | 8 | 8 | 22.8% | — |
| `coalition_contamination` | 100 | 10 | 8 | 2 | 8 | 8 | 8 | 43.2% | — |
| `coalition_contamination` | 100 | 20 | 9 | 1 | 9 | 9 | 9 | 43.6% | — |
| `coalition_contamination` | 150 | 5 | 9 | 1 | 9 | 9 | 9 | 24.8% | — |
| `coalition_contamination` | 150 | 10 | 7 | 3 | 7 | 7 | 7 | 21.2% | — |
| `coalition_contamination` | 150 | 20 | 9 | 1 | 9 | 9 | 9 | 44.0% | — |
| `mixture_subgroup` | 50 | 5 | 8 | 2 | 8 | 8 | 8 | 88.0% | — |
| `mixture_subgroup` | 50 | 10 | 9 | 1 | 9 | 9 | 9 | 91.2% | — |
| `mixture_subgroup` | 50 | 20 | 7 | 3 | 7 | 7 | 7 | 62.8% | — |
| `mixture_subgroup` | 100 | 5 | 7 | 3 | 7 | 7 | 7 | 70.8% | — |
| `mixture_subgroup` | 100 | 10 | 8 | 2 | 8 | 8 | 8 | 60.4% | — |
| `mixture_subgroup` | 100 | 20 | 9 | 1 | 9 | 9 | 9 | 71.2% | — |
| `mixture_subgroup` | 150 | 5 | 6 | 4 | 6 | 6 | 6 | 61.2% | — |
| `mixture_subgroup` | 150 | 10 | 3 | 7 | 3 | 3 | 3 | 37.6% | — |
| `mixture_subgroup` | 150 | 20 | 9 | 1 | 9 | 9 | 9 | 76.8% | — |
| `heavy_tails` | 50 | 5 | 3 | 7 | 3 | 3 | 3 | 29.2% | — |
| `heavy_tails` | 50 | 10 | 4 | 6 | 4 | 4 | 4 | 46.4% | — |
| `heavy_tails` | 50 | 20 | 2 | 8 | 2 | 2 | 2 | 21.6% | — |
| `heavy_tails` | 100 | 5 | 1 | 9 | 1 | 1 | 1 | 11.2% | — |
| `heavy_tails` | 100 | 10 | 3 | 7 | 3 | 3 | 3 | 30.0% | — |
| `heavy_tails` | 100 | 20 | 2 | 8 | 2 | 2 | 2 | 21.2% | — |
| `heavy_tails` | 150 | 5 | 0 | 10 | 0 | 0 | 0 | 3.2% | — |
| `heavy_tails` | 150 | 10 | 1 | 9 | 1 | 1 | 1 | 12.4% | — |
| `heavy_tails` | 150 | 20 | 3 | 7 | 3 | 3 | 3 | 30.0% | — |
| `collinearity_stress` | 50 | 5 | 0 | 10 | 0 | 0 | 0 | 0.0% | — |
| `collinearity_stress` | 50 | 10 | 0 | 10 | 0 | 0 | 0 | 0.0% | — |
| `collinearity_stress` | 50 | 20 | 0 | 10 | 0 | 0 | 0 | 0.0% | — |
| `collinearity_stress` | 100 | 5 | 0 | 10 | 0 | 0 | 0 | 0.0% | — |
| `collinearity_stress` | 100 | 10 | 0 | 10 | 0 | 0 | 0 | 0.0% | — |
| `collinearity_stress` | 100 | 20 | 0 | 10 | 0 | 0 | 0 | 0.0% | — |
| `collinearity_stress` | 150 | 5 | 0 | 10 | 0 | 0 | 0 | 0.0% | — |
| `collinearity_stress` | 150 | 10 | 0 | 10 | 0 | 0 | 0 | 0.0% | — |
| `collinearity_stress` | 150 | 20 | 0 | 10 | 0 | 0 | 0 | 0.0% | — |

## Falsification summaries

The following values use finite reached rows for fragility associations and
exact-fragility means. They are descriptive summaries of the selected,
reached population. The influence metrics are shown only for scenarios with
generator-known planted cases.

| Scenario | Fragility / `abs(rho)` Spearman | Fragility / `abs(Wald z)` Spearman | Mean exact fragility | Greedy overestimate rate | Influence recall | Certification / reach |
|---|---:|---:|---:|---:|---:|---:|
| `clean_planted_edge` | 0.971 | 0.971 | 0.500 | 0.000 | n/a | 44/90 (48.9%) |
| `single_influential_case` | 0.902 | 0.909 | 0.613 | 0.000 | 0.567 | 80/90 (88.9%) |
| `coalition_contamination` | 0.864 | 0.852 | 1.268 | 0.000 | 0.689 | 71/90 (78.9%) |
| `mixture_subgroup` | 0.969 | 0.969 | 0.530 | 0.000 | 0.151 | 66/90 (73.3%) |
| `heavy_tails` | 0.998 | 0.998 | 0.211 | 0.000 | n/a | 19/90 (21.1%) |
| `collinearity_stress` | n/a | n/a | n/a | n/a | n/a | 0/90 (0.0%) |

The zero greedy-overestimate rate is conditional on rows reached and
certified under `search_cap=2`; it does not establish greedy exactness outside
that bounded region. Scenario-level incremental AUC and contamination
partial-rank metrics are structurally undefined because each individual
scenario contains only one contamination class. The cross-scenario contrasts
below supply both classes.

## Matched-cell contrasts

Rows are matched by scenario pair, `N`, `p`, `parameter_id`, and replication.
The matching key identifies the simulation pairing; it does not make every
metric a paired-difference estimator. The pooled population includes each
individually valid row, so one member may contribute when its counterpart is
censored. The joint population includes only pairs for which both rows have
finite reached fragility. Neither population treats censoring as zero.

The aggregate results below combine the 90 matched keys in each contrast.
`Censored pairs` counts pairs with at least one unavailable fragility result.

| Contrast | Matched pairs | Censored pairs | Individually valid rows | Jointly valid pairs | Pooled baseline AUC | Pooled augmented AUC | Joint baseline AUC | Joint augmented AUC | Pooled partial rank | Joint partial rank |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `clean_vs_single_influential_case` | 90 | 51 | 124 | 39 | 0.632 | 0.685 | 0.613 | 0.661 | -0.249 | -0.350 |
| `clean_vs_coalition_contamination` | 90 | 54 | 115 | 36 | 0.753 | 0.752 | 0.759 | 0.759 | -0.087 | -0.139 |
| `clean_vs_mixture_subgroup` | 90 | 56 | 110 | 34 | 0.509 | 0.611 | 0.493 | 0.639 | 0.154 | 0.107 |

The AUC values are learned-weight, in-sample benchmarks. They are not
out-of-sample prediction estimates, and the differences between pooled and
joint values illustrate why the reporting populations must remain separate.

### Per-cell paired denominators and metrics

The table makes the rows feeding each contrast auditable at the same `N × p`
resolution as the reach table. `Valid clean` and `Valid target` are row counts
out of ten; `Joint pairs` is a count out of ten. AUC entries are shown as
`baseline → augmented`.

| Contrast | N | p | Matched | Censored pairs | Valid clean | Valid target | Joint pairs | Pooled AUC | Joint AUC | Pooled partial rank | Joint partial rank |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `clean_vs_single_influential_case` | 50 | 5 | 10 | 4 | 6 | 10 | 6 | 0.783 → 0.833 | 0.667 → 0.750 | -0.267 | -0.446 |
| `clean_vs_single_influential_case` | 50 | 10 | 10 | 5 | 5 | 10 | 5 | 0.680 → 1.000 | 0.960 → 1.000 | -0.919 | -0.654 |
| `clean_vs_single_influential_case` | 50 | 20 | 10 | 2 | 8 | 10 | 8 | 0.650 → 0.887 | 0.562 → 0.859 | -0.661 | -0.667 |
| `clean_vs_single_influential_case` | 100 | 5 | 10 | 7 | 3 | 9 | 3 | 0.722 → 0.722 | 0.667 → 0.667 | 0.083 | 0.000 |
| `clean_vs_single_influential_case` | 100 | 10 | 10 | 7 | 4 | 9 | 3 | 0.694 → 0.694 | 0.778 → 0.778 | -0.022 | 0.111 |
| `clean_vs_single_influential_case` | 100 | 20 | 10 | 6 | 6 | 6 | 4 | 0.750 → 0.750 | 0.750 → 0.750 | 0.109 | 0.101 |
| `clean_vs_single_influential_case` | 150 | 5 | 10 | 9 | 2 | 8 | 1 | 0.688 → 0.688 | 1.000 → 1.000 | 0.033 | 0.000 |
| `clean_vs_single_influential_case` | 150 | 10 | 10 | 6 | 4 | 10 | 4 | 0.800 → 0.800 | 1.000 → 1.000 | 0.180 | 1.000 |
| `clean_vs_single_influential_case` | 150 | 20 | 10 | 5 | 6 | 8 | 5 | 0.635 → 0.635 | 0.600 → 0.600 | -0.405 | 0.000 |
| `clean_vs_coalition_contamination` | 50 | 5 | 10 | 6 | 6 | 5 | 4 | 0.867 → 0.867 | 0.812 → 0.812 | -0.122 | -0.164 |
| `clean_vs_coalition_contamination` | 50 | 10 | 10 | 7 | 5 | 6 | 3 | 0.667 → 0.933 | 0.667 → 1.000 | -0.756 | -0.884 |
| `clean_vs_coalition_contamination` | 50 | 20 | 10 | 2 | 8 | 10 | 8 | 0.694 → 0.656 | 0.719 → 0.719 | 0.036 | 0.105 |
| `clean_vs_coalition_contamination` | 100 | 5 | 10 | 8 | 3 | 8 | 2 | 0.875 → 0.875 | 0.750 → 0.750 | 0.354 | 0.000 |
| `clean_vs_coalition_contamination` | 100 | 10 | 10 | 7 | 4 | 8 | 3 | 0.688 → 0.688 | 0.778 → 0.889 | 0.078 | 0.111 |
| `clean_vs_coalition_contamination` | 100 | 20 | 10 | 5 | 6 | 9 | 5 | 0.778 → 0.778 | 0.800 → 0.800 | 0.157 | 0.164 |
| `clean_vs_coalition_contamination` | 150 | 5 | 10 | 8 | 2 | 9 | 2 | 0.889 → 0.889 | 1.000 → 1.000 | 0.211 | 0.000 |
| `clean_vs_coalition_contamination` | 150 | 10 | 10 | 7 | 4 | 7 | 3 | 0.929 → 0.929 | 1.000 → 1.000 | 0.275 | 0.474 |
| `clean_vs_coalition_contamination` | 150 | 20 | 10 | 4 | 6 | 9 | 6 | 0.741 → 0.741 | 0.708 → 0.792 | -0.235 | -0.320 |
| `clean_vs_mixture_subgroup` | 50 | 5 | 10 | 5 | 6 | 8 | 5 | 0.667 → 0.667 | 0.700 → 0.700 | -0.041 | -0.064 |
| `clean_vs_mixture_subgroup` | 50 | 10 | 10 | 5 | 5 | 9 | 5 | 0.978 → 0.978 | 0.960 → 0.960 | -0.306 | -0.427 |
| `clean_vs_mixture_subgroup` | 50 | 20 | 10 | 5 | 8 | 7 | 5 | 0.652 → 0.866 | 0.600 → 0.920 | 0.494 | 0.451 |
| `clean_vs_mixture_subgroup` | 100 | 5 | 10 | 8 | 3 | 7 | 2 | 0.643 → 0.643 | 0.750 → 0.750 | 0.038 | 0.000 |
| `clean_vs_mixture_subgroup` | 100 | 10 | 10 | 6 | 4 | 8 | 4 | 0.734 → 0.734 | 0.781 → 0.781 | 0.091 | 0.171 |
| `clean_vs_mixture_subgroup` | 100 | 20 | 10 | 5 | 6 | 9 | 5 | 0.722 → 0.722 | 0.800 → 0.800 | 0.070 | 0.123 |
| `clean_vs_mixture_subgroup` | 150 | 5 | 10 | 9 | 2 | 6 | 1 | 0.583 → 0.583 | 0.500 → 0.500 | 0.000 | 0.000 |
| `clean_vs_mixture_subgroup` | 150 | 10 | 10 | 9 | 4 | 3 | 1 | 0.667 → 0.667 | 0.500 → 0.500 | 0.000 | 0.000 |
| `clean_vs_mixture_subgroup` | 150 | 20 | 10 | 4 | 6 | 9 | 6 | 0.611 → 0.722 | 0.611 → 0.722 | -0.416 | -0.451 |

These are small per-cell denominators. They are useful for auditing workflow
behavior and identifying where the estimator is unavailable, but they are not
stable estimates of population performance.

## Interpretation and v0.1 boundary decision

The run demonstrates that the pre-specified simulation and reporting workflow
executes end to end under the frozen limits. It does not demonstrate uniform
availability of the fragility estimand:

- `single_influential_case` has the highest reach (80/90), while
  `clean_planted_edge` reaches 44/90;
- `heavy_tails` reaches only 19/90, including a 0/10 cell at `N=150, p=5`;
- `collinearity_stress` reaches 0/90 across the entire matrix;
- reach differs by scenario and cell, so complete-case metrics are subject to
  outcome-dependent selection rather than missing-at-random assumptions.

For v0.1, these low-reach scenarios are retained as explicit practical
boundaries of the bounded method, not silently removed and not treated as an
implementation failure. The current evidence supports finite fragility,
influence, and contrast interpretation only with the displayed denominators.
In particular, `heavy_tails` and `collinearity_stress` do not provide enough
available rows for broad fragility operating-characteristic claims, and the
collinearity scenario provides no finite fragility evidence in this run.

No search-cap increase, estimator retuning, or numerical optimization is
authorized by this result. Any redesign intended to improve reach must be a
separate pre-specified methodological task with its own target, comparison
against this baseline, and failure/censoring analysis.

## Limitations carried forward

- The search cap is two deletions; greedy exactness is not established beyond
  the certified bounded region.
- Reach-dependent selection limits interpretation of complete-case fragility
  and contrast metrics.
- Reference-tail probabilities are descriptive model-based quantities, not
  confirmatory p-values.
- Pooled and jointly valid contrast metrics are in-sample descriptive
  benchmarks, not independent predictive validation.
- Scenario-level incremental AUC and contamination partial rank remain
  structurally undefined for single-class scenarios.
- A matched-environment duplicate run has not been included in this hosted
  artifact.

## Recommended next methodological step

Review and formally accept this v2 evidence record as the baseline for v0.1.
Then specify a separate reach-boundary study before optimization: first decide
whether the scientific target is to improve availability under heavy tails and
near-collinearity, or to narrow the declared scope further; then compare any
candidate change against the frozen `e29bfd9` baseline using the same row-level
denominators and hosted artifact contract.
