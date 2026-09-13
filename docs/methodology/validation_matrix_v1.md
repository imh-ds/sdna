# SDNA v0.1 validation matrix v1

## Status and purpose

This document pre-specifies the bounded v0.1 validation run before the next
full execution. It freezes the simulation cells, randomization, estimands,
missingness rules, reporting populations, and interpretation boundaries. The
machine-readable source is
[`simulations/configs/falsification_pilot.json`](../../simulations/configs/falsification_pilot.json).

This is an operating-characteristic and workflow-validation plan for an
experimental diagnostic. It is not a publication-level power analysis, a
confirmatory test plan, or evidence that SDNA is causal, universally calibrated,
or valid for data outside the declared scope.

Once the pre-specified run begins, changes to the matrix, primary metrics,
reach handling, or interpretation rules require a new version of this document,
a new configuration, and a decision-log entry. Results from the reduced CI
matrix are execution evidence and do not replace this validation run.

## Declared method scope

The validation covers the v0.1 data boundary:

- complete continuous observations;
- independent, exchangeable rows;
- empirical partial-correlation networks with full-sample shrinkage held fixed
  during deletion, calibration, and shrinkage-bootstrap analyses;
- exact leave-one-out influence as the authoritative individual-case effect;
- greedy fragility as a verified candidate upper bound, with exact certification
  only when the bounded exhaustive search succeeds.

The run does not validate ordinal or polychoric data, missing-data handling,
longitudinal dependence, VAR/GVAR deletion, causal discovery, multiplicity
control across a network, or automatic fragile/not-fragile classification.

## Frozen simulation design

The primary matrix is the committed falsification-pilot configuration:

| Setting | Frozen value |
|---|---|
| Root seed | `20260910` |
| `N` values | `50`, `100`, `150` |
| `p` values | `5`, `10`, `20` |
| Scenarios | all six registered scenarios |
| Replications per scenario/cell | `10` |
| Clean population partial correlation | `0.2` |
| Coalition contamination count | `3` |
| Fragility targets | relative `0.9`, `0.7`, `0.5`, `0.3` |
| Primary fragility target | relative `0.5` |
| Greedy search cap | `2` deletions |
| Certification combination budget | `1000` |
| Calibration simulations | `25` per row |
| Bootstrap draws | `100` per row |
| Bootstrap confidence | `0.95` |
| Calibration reach mode | `require_reached=False` |

The six scenario families are:

| Scenario | Truth and purpose | Primary evidence |
|---|---|---|
| `clean_planted_edge` | Known nonzero focal population edge without planted contamination | Clean reference-tail availability and false-flag rate; fragility/magnitude association |
| `single_influential_case` | Weak/null focal edge with one shifted case | Influence recovery, fragility behavior, and reach/censoring |
| `coalition_contamination` | Weak/null focal edge with a known shifted coalition of three cases | Coalition influence recovery, fragility behavior, and matched contrast |
| `mixture_subgroup` | Subgroup generated from a distinct covariance structure | Subgroup recovery, fragility behavior, and matched contrast where the generator supplies planted cases |
| `heavy_tails` | Continuous heavy-tailed observations | Numerical stability, reach/censoring, and robustness boundary |
| `collinearity_stress` | Valid near-collinear covariance structure | Numerical stability, reach/censoring, and practical boundary |

There are `6 × 3 × 3 × 10 = 540` primary result rows. The configuration's
`parameter_id` is retained even when the current matrix has one parameter slot;
future multi-parameter contrasts must align slots explicitly rather than infer
pairings from row order.

## Randomization and reproducibility

The runner derives independent row seeds from the root seed with
`numpy.random.SeedSequence`. Each row then spawns separate calibration and
bootstrap streams. The run must retain:

- the exact configuration and its checksum;
- the Git commit, package version, Python version, and NumPy version;
- row seeds and the simulation metadata envelope;
- the CSV results, JSON summary, and Markdown summary.

A rerun with the same commit, configuration, and software environment must
agree on deterministic result fields. Wall-clock timings and timestamps are
allowed to differ and are compared separately. A changed seed, configuration,
dependency environment, or commit is a new execution profile, not a silent
replication of the pre-specified run.

## Estimands and reporting populations

The primary fragility estimand is the number of deletions needed for the focal
edge's absolute partial correlation to reach 50% of its full-sample absolute
value, under the fixed full-sample shrinkage rule. The result is a bounded
greedy-search quantity; it is not treated as the exact combinatorial minimum
unless certification succeeds.

The following populations are kept distinct:

1. **All generated rows:** used for row counts, observed edge summaries, and
   reach/censoring rates.
2. **Reached rows:** used for finite observed fragility, certification, and
   fragility associations. Unreached searches remain censored and are never
   converted to zero or to an observed count.
3. **Individually valid matched rows:** used for pooled cross-scenario contrast
   metrics when that row has finite reached fragility.
4. **Jointly valid matched pairs:** used only when both members of a matched
   clean/contaminated cell have finite reached fragility.

Matched cells are keyed by scenario pair, `N`, `p`, `parameter_id`, and
replication. Pooled and jointly valid metrics must be labeled separately. A
matched cell identifies the simulation pairing; it does not make every pooled
metric a paired-difference estimator.

## Calibration and comparator rules

Calibration uses the fitted empirical unshrunk correlation and the observed
full-sample shrinkage value. With `require_reached=False`, an unreached
reference search is retained as a right-censored draw above the bounded search
cap. It remains in the denominator of the plus-one-corrected empirical tail
probability and does not contribute to the numerator. An unreached observed
search produces no finite reference-tail probability.

The reference-tail probability is a descriptive model-based quantity, not a
formal frequentist p-value. It does not correct for screening multiple edges or
establish the exact minimum outside the greedy search cap. Strict complete-reach
calibration may be run as a sensitivity analysis, but it is not substituted for
the pre-specified censored analysis.

The Wald comparator remains an ordinary-partial, full-sample benchmark with
re-estimated shrinkage. The Python bootstrap remains a shrinkage-bootstrap
benchmark and is not reported as a `bootnet` result. Comparator outputs are
context, not interchangeable estimates of the SDNA deletion estimand.

## Primary and secondary outputs

The primary report will include, by scenario and `N × p` cell where applicable:

- row count, observed-search reach rate, and reference-search reach fraction;
- finite fragility counts and certification rate, with denominators shown;
- clean reference-tail availability and false-flag rate at the descriptive
  `0.05` threshold;
- fragility rank association with absolute observed partial correlation;
- influence recovery for scenarios with generator-known planted cases;
- pooled and jointly valid matched-cell contrast metrics;
- bootstrap rejection counts and confidence-exclusion status.

Secondary descriptive outputs include association with absolute Wald statistics,
partial rank associations controlling for magnitude, `N`, and `p`, learned
in-sample incremental AUC, greedy-overestimation rates among certified rows, and
the comparison between ordinary and SDNA-oriented summaries.

Incremental AUC is an in-sample learned-weight benchmark, not an out-of-sample
prediction estimate. It is reported only when both contamination classes and
the required finite fields are present. Metrics with insufficient finite rows,
one binary class, or no jointly valid pairs are reported as `null` with their
valid-row or valid-pair counts.

## Acceptance and interpretation rules

Technical acceptance is binary:

- all 540 expected rows are produced with the expected scenario/cell counts;
- the configuration checksum and provenance metadata are valid;
- schema, finite-value, range, and invariant validation passes;
- no unhandled numerical or workflow error occurs;
- deterministic fields are reproducible under an explicitly matched rerun.

Methodological interpretation is not reduced to a single pass/fail score. The
validation report must show reach, censoring, certification, rejected bootstrap
draws, and valid denominators before interpreting any association or contrast.
Low reach is a practical limitation to report, not a reason to silently remove
the scenario. In particular, no minimum reach threshold is assumed without a
separate justification of the target operating behavior.

The following are not permitted within this pre-specified run:

- changing the search cap, target, shrinkage rule, or scenario parameters after
  inspecting results;
- treating censored fragility as zero, as a finite count, or as evidence that
  the exact minimum exceeds the cap;
- treating a descriptive reference tail as a confirmatory p-value;
- selecting only favorable cells or metrics for the principal report;
- optimizing production numerical routines based on this run before recording
  the baseline evidence and a separate decision.

## Execution profiles

The repository has three intentionally different workload profiles:

| Profile | Source | Purpose | Interpretation |
|---|---|---|---|
| PR smoke | `simulations/configs/smoke.json` with `--smoke` | Fast schema and end-to-end gate | Technical only |
| Reduced validation | `simulations/configs/validation_matrix.json` through the manual Actions workflow | Hosted reproducibility and artifact rehearsal | Not operating-characteristic evidence |
| v0.1 primary validation | `simulations/configs/falsification_pilot.json` | Execute the frozen 540-row matrix | Bounded methodological evidence with stated limitations |

The reduced workflow must not be described as the primary validation result. The
primary matrix is manually invoked after this specification is accepted and its
artifact is retained alongside the exact configuration and provenance.

The current `tools.validate_smoke` command is intentionally limited to the PR
and reduced-validation profiles: it requires `metadata.smoke=True` and derives
an expected replication count capped at five. It must not be used unchanged to
accept the 10-replication primary artifact. Before primary execution, the
repository needs a profile-aware validator (or an equivalent primary-run
preflight) that validates the full configured replication count while retaining
the same schema, range, provenance, and summary invariants.

## Deferred work

After the primary matrix is executed and interpreted, the next decision is
whether the observed reach/censoring and numerical boundaries justify a separate
algorithmic or optimization task. No optimization is part of this
pre-specification. Extensions to longitudinal, ordinal, missing-data, or
causal settings require new estimands and new validation plans.
