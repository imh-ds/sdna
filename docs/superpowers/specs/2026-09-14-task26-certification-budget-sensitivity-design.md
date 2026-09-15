# Task 26: Certification-budget sensitivity study

**Status:** Approved design; written-spec review required before implementation

**Date:** 2026-09-14

## Purpose

Task 25 established a reproducible certification-usability audit for the newly
reached rows at candidate caps 3 and 4. Every population record was
non-certified because the complete-subset search exhausted the certification
budget before reaching the next complete subset size. Task 26 tests whether
that result is a consequence of the fixed budget rather than a lack of
certifiable evidence.

The study is a bounded sensitivity analysis of the certification budget. It is
not a production protocol change, a cap-selection procedure, or an
optimization exercise.

## Study question

For the exact Task 25 newly reached populations at candidate caps 3 and 4,
does increasing the certification-combination budget from the Task 25 value
of 1,000 change certification yield or the observed failure mode, while every
other data-generating, estimation, and inference choice is held fixed?

The study will estimate certification yield separately for each candidate cap
and budget. The denominator is fixed to the number of Task 25 newly reached
records for that cap, including records that remain non-certified at every
larger budget.

## Source identity and provenance

The selected population and source data are anchored to the accepted Task 25
hosted artifact:

| Item | Required identity |
| --- | --- |
| Task 25 Actions run | `34895397606` |
| Task 25 source commit | `7b22b3fca39888e1a452cb5a7ad8ec244ccd752e` |
| Task 25 artifact | `sdna-certification-usability-34895397606` |
| Task 25 `results.csv` SHA-256 | `4ec0068d8fe2b2b62df45fccbbf71f884c50589e319e48c3a2400111ae051918` |
| Nested Task 24 source run | `34871220664` |
| Nested Task 24 source commit | `338b0d95cdb312b2805affb0de458e06508d80f0` |
| Nested Task 24 artifact | `sdna-cap-expansion-34871220664` |
| Nested Task 24 source `results.csv` SHA-256 | `110d0b4f266b253251ac1a64bb4195b61722008d426b74c75802d3de57b43d87` |
| Task 25 manifest SHA-256 | `415576f1fec5ccd2a47e0ad411d29e4d48c6e8e370609ae495ccc877fe74e974` |

The implementation must obtain and record the complete checksums from the
validated artifacts in the generated metadata. A run must fail validation if
the Task 25 artifact,
its manifest, or its nested source artifact does not match the required
identity and schema.

The Task 25 artifact is the population-selection authority. The implementation
must validate it before deriving any study rows. It must not regenerate the
population using a different seed, source snapshot, eligibility rule, or
post-hoc filtering rule.

## Population definition

The study includes exactly the Task 25 `U_to_R(3)` and `U_to_R(4)` records,
identified by the canonical pairing key used by the certification-usability
workflow. The expected population counts are:

| Candidate cap | Expected Task 25 newly reached records |
| ---: | ---: |
| 3 | 44 |
| 4 | 68 |

The two populations may overlap by pairing key. The report must therefore
present them as separate cap-specific populations and must not describe them
as 112 unique records. The exact pairing keys must be emitted in the study
metadata and compared against the validated Task 25 artifact.

Cap 2 is the unchanged production baseline. It is not rerun in this focused
sensitivity study and is not part of the budget comparison. Its Task 25/source
record remains the reference for demonstrating that the study did not alter
the production protocol.

## Fixed budget grid

The certification-combination budgets are exactly:

```text
[1000, 5000, 10000, 20000]
```

The Task 25 budget of 1,000 is retained as the first arm. The larger fixed
values probe successive complete-subset boundaries without allowing the
observed result to determine a later budget. No additional budget may be
added after inspecting interim certification results.

The grid is motivated by the certification implementation's exact stopping
rule. For a sample size `N`, the search checks complete subset sizes and stops
before a size when `checked + size_total > max_combinations`. For example,
the selected records include sample sizes for which:

- `N=50` has 50 size-one subsets and 1,225 size-two subsets;
- `N=100` has 100 size-one subsets and 4,950 size-two subsets; and
- `N=150` has 150 size-one subsets and 11,175 size-two subsets.

Consequently, 1,000, 5,000, 10,000, and 20,000 expose distinct practical
search boundaries for at least part of the selected population. These values
are a pre-specified diagnostic range, not a claim that 20,000 is universally
sufficient for certification.

## Protocol invariants

Every budget arm must preserve the following Task 25/Task 24 choices:

- the source data, source artifact, pairing keys, six scenario definitions,
  sample-size grid, parameter, contamination settings, and data-generating
  seed (`20260910`);
- the same estimator and target (`0.5`), with the same minimum-sample and
  exact-LOO behavior;
- the same full workflow stage order and error handling;
- calibration size `25`, `bootstrap_reps=100`, confidence level `0.95`, and
  `calibration_require_reached=False`;
- the same right-censored reference-tail treatment, Wald comparator, ordinary
  partial behavior, shrinkage calculation, bootstrap procedure, and
  reproducibility checks; and
- the same candidate caps (3 and 4) and the same Task 25 newly reached
  population membership.

Only the certification-combination budget may vary. The budget must be passed
as an explicit configuration value and recorded in every result row and in
the run manifest.

Each selected pairing key must use one shared deterministic dataset for all
candidate caps and budget arms. Child seeds must remain derived from the
canonical source key and be independent of budget order. Reordering the
budget list must not change any data, estimator output, calibration output,
Wald output, bootstrap output, or source digest.

## Execution design

The recommended implementation is a focused, manual-only GitHub Actions
workflow with one fixed-budget job per grid value:

1. A preparation step downloads and validates the accepted Task 25 artifact
   and its nested source artifact, derives the exact 44/68 selected keys, and
   publishes the selection manifest.
2. Four matrix jobs run the same selected keys at one budget each. Each job
   uploads its result, manifest, validation report, and runtime/status record
   even when the job fails or times out.
3. An aggregation job downloads the completed budget artifacts and produces a
   combined sensitivity report. It must distinguish a completed arm from a
   failed or timed-out arm and must never convert an incomplete arm into a
   zero certification yield.

The workflow is manual-only. It must not run on push, pull request, or a
weekly schedule. It is evidence-generation infrastructure rather than a
routine merge gate.

The study is intentionally focused rather than a rerun of all 1,620 Task 25
rows. A complete run has 112 records per budget (44 at cap 3 and 68 at cap 4)
and 448 cap-budget records across the four arms. This keeps the diagnostic
question tractable while retaining the exact rows responsible for Task 25's
observed failure mode.

## Timeout and incomplete-run semantics

Each budget arm has a fixed computational ceiling of 1,800 seconds. The
corresponding Actions matrix job may use a 40-minute job timeout to allow
artifact upload and status publication after the computation ceiling is
reached.

Timeout is an explicit arm outcome. A timed-out arm must record:

- the budget, start time, elapsed time, and timeout ceiling;
- the number of expected and completed cap-budget rows;
- the last completed pairing key, if available;
- whether the certification search itself exhausted its configured budget;
- the runtime environment and source checksums; and
- a machine-readable arm status of `timeout`.

An arm with status `timeout`, `failed`, or `incomplete` is excluded from
certification-yield denominators and cannot support a conclusion that the
budget produced zero certified records. The aggregate report must fail its
“complete sensitivity result” check unless all four arms complete with the
expected 112 rows each. Partial artifacts remain valuable for diagnosing the
practical runtime limit and must be retained.

The certification function's ordinary `combination_budget_exhausted` result
is not a workflow timeout. It is a valid completed row-level outcome and must
remain distinguishable from the arm-level `timeout` status.

## Required outputs

The aggregate artifact must contain at least:

- `results.csv`, with one row per `(pairing_key, candidate_cap, budget)` and
  explicit certification diagnostics;
- `summary.json`, containing source identities, complete checksums, protocol
  invariants, budget grid, expected/observed counts, arm statuses, and
  pass/fail validation checks;
- `summary.md`, explaining the question, population overlap, per-cap/per-budget
  results, exhaustion behavior, runtime, and limitations;
- `selection_manifest.json`, containing the exact Task 25 pairing keys and
  their cap membership; and
- one machine-readable status record per budget arm.

Required row-level fields include the canonical pairing key, candidate cap,
budget, sample size, certification status, certification reason,
`exact_minimum`, `combinations_checked`, budget-exhaustion flag, elapsed time,
and all relevant downstream status/error fields. The output must preserve the
Task 25 source digest, data seed, and inference seeds for each row.

## Validation and acceptance criteria

The implementation is acceptable only when the following checks are automated:

1. The Task 25 artifact and nested Task 24 source artifact validate against
   the required identities, schemas, and complete checksums.
2. The selected pairing keys exactly match Task 25's `U_to_R(3)` and
   `U_to_R(4)` populations: 44 and 68 records respectively.
3. Every completed budget arm has exactly 112 rows: 44 cap-3 rows and 68
   cap-4 rows. The aggregate complete result has exactly 448 rows.
4. No pairing key is silently added, removed, deduplicated across candidate
   caps, or reassigned to a cap. Overlap is reported rather than collapsed.
5. For every row, all Task 25 fields unrelated to certification diagnostics
   and elapsed time match the source row at the stated numeric tolerance
   (`1e-12` for floating-point comparisons).
6. The budget value is the only intended protocol change. Budget-dependent
   certification diagnostics may change; data, seeds, digests, calibration,
   Wald, bootstrap, and workflow statuses must not change.
7. The budget arms are run in a deterministic order-independent way and
   record Python, NumPy, package, and operating-environment versions.
8. Row-level `combination_budget_exhausted` is distinct from arm-level
   failure, incompleteness, and timeout.
9. A complete aggregate report is emitted only when all four fixed arms finish
   with their expected rows. An incomplete report remains diagnostically
   usable but cannot be interpreted as a full sensitivity result.
10. The production cap-2 configuration and existing Task 25 artifacts remain
    unchanged.

Local tests must cover selection identity, budget propagation, shared-dataset
reproducibility, exact Task 25 field matching, budget-dependent certification
diagnostics, overlap reporting, and timeout/incomplete status handling. The
manual Actions workflow must run the same checks and upload artifacts on both
success and failure paths.

## Interpretation rules

If certification yield increases at a larger budget, the supported conclusion
is limited to: that fixed budget changes yield for the specified Task 25
selected population under the unchanged protocol. It does not justify
promoting cap 3 or cap 4, changing the production budget, or selecting a
budget post hoc.

If yield remains zero through 20,000, the supported conclusion is that no
selected record certified within this pre-specified diagnostic range. It is
not evidence that certification is impossible at every larger budget.

If an arm times out or fails, the result identifies a practical computational
limit for that arm. It is not a statistical zero and must be reported as
incomplete. Any later budget or optimization study requires a new
pre-specification and decision-log entry.

## Non-goals

Task 26 does not:

- alter the default certification budget or cap-2 production behavior;
- choose a new budget based on observed certification outcomes;
- optimize subset enumeration or estimator runtime;
- rerun the complete Task 25 population;
- add a cap-promotion rule or a new certification threshold; or
- replace the Task 25 hosted evidence artifact.

## Review gate

Before implementation, an independent review of this written specification
must confirm that the population identity, fixed budget grid, protocol
invariants, timeout semantics, expected row counts, and interpretation rules
are sufficiently precise to make the resulting evidence auditable. Any
approved changes must be recorded in the decision log and in the eventual
implementation commit history.
