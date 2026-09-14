# Task 25: Certification usability audit

**Status:** Approved design; implementation begins only after this
specification is reviewed.

## Goal

Determine whether the additional rows reached by search caps 3 and 4 are
usable evidence or merely reachable candidates that fail exact certification.
The study starts with a row-level audit of the accepted Task 24 artifact and
defines a conditional instrumented rerun only if the existing artifact does
not contain enough information to identify the certification bottleneck.

This is a diagnostic study. It does not change the v0.1 production baseline,
promote a search cap, increase a workload budget, or modify the estimator.

## Context and relationship to Task 24

Task 24 compared the frozen cap-2 workflow with paired cap-3 and cap-4
full-workflow arms. The hosted artifact showed 44 cap-3 and 68 cap-4 rows that
were unreached at cap 2 but reached at the larger cap; none of those newly
reached rows was certified. This result establishes an availability gain, but
not whether the gain produces valid, certifiable evidence.

The hosted Task 24 record is:

- Actions run: [`34871220664`](https://github.com/imh-ds/sdna/actions/runs/34871220664);
- merge commit: `338b0d95cdb312b2805affb0de458e06508d80f0`;
- artifact: `sdna-cap-expansion-34871220664`;
- result checksum: `110d0b4f266b253251ac1a64bb4195b61722008d426b74c75802d3de57b43d87`.

The Task 24 artifact remains the source of truth for its own results. Task 25
must not overwrite it or silently reinterpret its denominators.

## Study phases

### Phase A: Existing-artifact row-level audit

Use the downloaded Task 24 artifact without regenerating data. For each
candidate cap `c` in `{3, 4}`, define the newly reached population as the
matched pairs whose cap-2 row has `fragility_status=unreached` and whose cap-c
row has `fragility_status=reached`:

`U_to_R(c) = {key : baseline_cap2 is unreached and cap-c is reached}`.

The pair key is the frozen Task 24 key
`(scenario, N, p, parameter_id, replication)`. Every key in `U_to_R(c)` must
identify exactly one cap-2 row and one cap-c row. Rows with workflow,
certification, calibration, Wald, or bootstrap errors remain in the audit
population and are reported as failures; they are not silently removed from
the denominator.

For every member of `U_to_R(c)`, report:

- cap, scenario, `N`, `p`, parameter ID, and replication;
- cap-2 and candidate data seeds, child seeds, and dataset digest;
- candidate certification status, `certified`, and exact fragility value;
- whether certification combination counts, budget, and a dedicated failure
  reason are unavailable in the Task 24 CSV;
- candidate calibration status, reference-tail probability, and reference
  reached fraction;
- candidate Wald and bootstrap statuses and rejected-resample count;
- workflow status, error stage, error type, and error message; and
- whether the row is certified, not certified, or failed before a completed
  certification result.

Phase A must explicitly report which information is unavailable in the Task
24 CSV. In particular, `not_certified` is known to be the current
certification-budget outcome from the implementation, but the CSV does not
store a dedicated reason code or the configured budget beside each row.

### Phase B: Conditional instrumented rerun

Run Phase B only when Phase A cannot distinguish the relevant certification
failure mechanisms. The rerun uses the Task 24 matrix and workflow contract
unchanged:

- the same six scenarios, `N=[50,100,150]`, `p=[5,10,20]`, and ten replications;
- the same three arms and search caps 2, 3, and 4;
- one generated dataset per pairing key shared by all arms;
- the same global seed `20260910` and deterministic data/child seed rules;
- the same relative target `0.5`;
- the same certification combination budget `1000`;
- the same calibration, Wald, and bootstrap settings; and
- the same 900-second operational ceiling.

The only allowed implementation change is to record certification diagnostics
that were absent from the Task 24 CSV. The instrumented artifact must add:

- `certification_combinations_checked`;
- `certification_combination_budget`;
- `certification_budget_exhausted`; and
- `certification_failure_reason`.

The reason values are fixed before execution:

- `not_applicable_unreached` when the candidate search does not reach the
  target;
- `not_applicable_prior_error` when an earlier workflow stage prevents
  certification from being attempted;
- `certified` when exact certification succeeds;
- `combination_budget_exhausted` when certification stops because the next
  complete subset size would exceed the declared budget;
- `not_certified_other` for a completed non-certification outcome that is not
  budget exhaustion; and
- `error` when certification raises an exception.

The rerun must preserve the existing Task 24 fields and status semantics. It
must not convert a certification error into `not_certified`, and it must not
change a calibration, Wald, bootstrap, or workflow result merely to expose a
diagnostic field.

## Estimands and endpoints

### Primary endpoint

For each candidate cap `c`, report certification yield among newly reached
rows:

`certification_yield(c) = certified candidate rows in U_to_R(c) / |U_to_R(c)|`.

The denominator is the complete `U_to_R(c)` population, including rows that
later fail certification or another downstream stage. Report the numerator,
denominator, and exact row identities. Do not replace a zero numerator with a
missing value or a missing downstream result with zero.

The primary report must also show the cap-2-to-c transition table and the
candidate certification status counts for the same matched rows. A binomial
confidence interval is not required for this diagnostic; if one is added, its
method and denominator must be declared before execution and it must not be
used as an automatic promotion rule.

### Secondary endpoints

For each candidate cap and the `U_to_R(c)` population, report:

- counts and rates for `certified`, `not_certified`, and certification errors;
- certification combinations checked and budget-exhaustion counts;
- calibration status counts, including finite, right-censored, and observed
  unreached states;
- Wald and bootstrap completion rates and bootstrap rejection totals;
- workflow errors by stage and declared error type;
- stratification by scenario, `N`, and `p` with explicit denominators; and
- comparison of the newly reached population with the cap-2 matched rows,
  without treating cap-2's unreached rows as zero-valued estimates.

All secondary results are descriptive. No multiplicity-adjusted hypothesis
test, post-hoc threshold, or cap-selection score is part of this study.

## Reproducibility and acceptance rules

Phase A is accepted only if the audit verifies the Task 24 artifact checksum,
schema, unique pairing keys, three-arm membership, and exact identification of
every `U_to_R(c)` row. The output must include the input artifact checksum and
the audit code commit.

Phase B is accepted only if it produces 1,620 rows with 540 rows per arm,
reproduces the Task 24 pairing keys, data seeds, child seeds, dataset digests,
and existing stage outcomes within the established cross-runtime numeric
tolerance, and passes the instrumented schema and semantic-status validator.
Any mismatch in pairing identity, seed derivation, digest, or existing stage
status invalidates the rerun as a reproduction and must be reported rather
than repaired post hoc.

Both phases must record repository commit, Python and NumPy versions, input
manifest checksum, artifact checksums, runtime, and budget status. The
instrumented workflow is manual-only; it is not a pull-request gate and has
no recurring schedule.

## Interpretation and decision rules

The study answers where the cap-expansion availability gain is lost:

- If failures are predominantly `combination_budget_exhausted`, a separate
  pre-specified certification-budget sensitivity study may be considered.
- If failures are predominantly certification errors, the error mechanism must
  be diagnosed as a software or numerical issue before any cap decision.
- If rows complete certification but fail calibration, Wald, bootstrap, or
  another declared endpoint, that downstream limitation must remain attached
  to the result.
- If newly reached rows certify under the frozen contract, the finding may
  motivate a later cap-decision study, but it does not promote a cap here.

The final report must state the observed mechanism and its denominator. It
must not claim that a larger cap is better merely because it reaches more
rows. Cap 2 remains the v0.1 production baseline unless a separate decision
record explicitly changes it.

## Non-goals

- changing the Task 24 artifact or v0.1 production configuration;
- increasing the certification combination budget;
- changing the search target, shrinkage, calibration tail treatment, Wald
  comparator, or bootstrap procedure;
- optimizing search, certification, or numerical code;
- selecting a new cap using an unregistered score or threshold;
- treating `not_certified` as equivalent to numerical failure; or
- pooling Phase A audit results and Phase B rerun results as independent
  simulation evidence.
