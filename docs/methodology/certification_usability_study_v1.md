# Certification-usability audit v1

**Status:** Pre-specified, implemented, and technically validated by hosted
run [`34895397606`](https://github.com/imh-ds/sdna/actions/runs/34895397606)
on main commit `7b22b3fca39888e1a452cb5a7ad8ec244ccd752e`. The audit does not
promote a search cap or change the v0.1 production baseline.

This page is the user-facing description of Task 25. The approved design
specification is
[`2026-09-14-task25-certification-usability-audit-design.md`](../superpowers/specs/2026-09-14-task25-certification-usability-audit-design.md),
and the implementation plan is
[`2026-09-14-task25-certification-usability-audit.md`](../superpowers/plans/2026-09-14-task25-certification-usability-audit.md).
The decision record is in
[`docs/development/decisions.md`](../development/decisions.md), under
ADR-024.

## Purpose and boundary

Task 24 found that larger search caps reached 44 additional paired rows at
cap 3 and 68 additional paired rows at cap 4, relative to cap 2. Those rows
were not certified in the accepted Task 24 artifact. This audit determines
whether the apparent reach gain produces usable certified evidence and, when
it does not, identifies the certification bottleneck.

The v0.1 production baseline remains **search cap 2**. This audit is
diagnostic only: it does not optimize the workflow, increase the matrix,
change the estimator, alter the certification target, or promote cap 3 or cap
4.

## Matched population and endpoint

For each candidate cap `c` in `{3, 4}`, the primary population is

`U_to_R(c) = {paired rows unreached at cap 2 and reached at cap c}`.

The primary endpoint is certification yield:

`certified rows / all rows in U_to_R(c)`.

The denominator is the complete matched population. A downstream calibration,
Wald, bootstrap, or other error remains in the denominator and is reported as
an error state; it is never converted to zero or silently removed. Row
identities are retained so an independent reviewer can reproduce exactly
which paired rows feed each contrast.

The Phase A read-only audit uses the accepted Task 24 artifact from run
`34871220664` and reports the populations that can be identified from the
existing CSV. It also lists fields that the artifact cannot recover, such as
the number of certification combinations checked and whether the combination
budget was exhausted.

## Frozen Phase B protocol

Phase B is an instrumented rerun only because the existing artifact lacks the
diagnostics needed to explain `not_certified` rows. It repeats the complete
Task 24 paired matrix with exactly the same contract:

- data seed `20260910`;
- six scenarios, `N=[50,100,150]`, `p=[5,10,20]`, one clean parameter, three
  contaminating observations, and ten replications per cell;
- 540 rows per arm and 1,620 rows total;
- caps 2, 3, and 4, with cap 2 remaining the production comparator;
- certification target `0.5` and combination budget `1000`;
- 25 calibration simulations, 100 bootstrap resamples, confidence level
  `0.95`, and the frozen calibration, tail, Wald, and bootstrap procedures;
- the operational runtime ceiling of `900` seconds.

The rerun may add only these per-row diagnostics:

| Field | Meaning |
| --- | --- |
| `certification_combinations_checked` | Number of certification combinations evaluated |
| `certification_combination_budget` | Frozen maximum allowed combinations (`1000`) |
| `certification_budget_exhausted` | Whether the maximum was reached before certification |
| `certification_failure_reason` | Structured reason for certification status |

The structured reason values distinguish unreached rows,
prior-stage errors, certified rows, budget exhaustion, other
non-certification, and certification errors. In particular,
`not_applicable_prior_error` is not the same as an observed certification
failure, and `combination_budget_exhausted` is not the same as
`not_certified_other`.

The instrumented output must reproduce every original Task 24 field, paired
row identity, child seed, data digest, status, and scientific value. Runtime
elapsed time is intentionally excluded from the reproduction comparison
because it is an execution measurement rather than a scientific result.

## Validation and interpretation

The manual-only workflow runs Phase A, the instrumented Phase B runner, and
the summary validator. It downloads the accepted Task 24 artifact, records
the source run and commit, validates the frozen source before using it, and
uploads results, metadata, summaries, manifests, command records, and both
human-readable reports. Artifacts are retained for 90 days. The workflow has
no `push`, `pull_request`, or weekly schedule trigger; it is started only by
an explicit `workflow_dispatch`.

The Phase B summary reports certification yield for each `U_to_R` population,
reason counts, budget exhaustion, downstream statuses, strata, exact pair
keys, and provenance. The summary and metadata are checked against the
results and the frozen Task 24 artifact before the run can be accepted as
technical evidence.

## Hosted result

The hosted run produced 1,620 instrumented rows (540 per arm) in 311.335
seconds, below the 900-second ceiling. Its strict reference comparison and
all artifact checks passed. Phase A identified 44 `U_to_R(3)` rows and 68
`U_to_R(4)` rows. Neither population contained a certified row, so
certification yield was `0/44 = 0.0` for cap 3 and `0/68 = 0.0` for cap 4.

All population records—44 cap-3 records and 68 cap-4 records—were classified
as `combination_budget_exhausted`; there were no certification errors or
prior workflow errors in these populations. The exact certification search
checked 3,900 combinations across the 44 cap-3 records and 6,300 across the
68 cap-4 records before the next complete subset size would exceed the
configured budget of `1000`. Their calibration status was right-censored, while Wald,
bootstrap, and overall workflow statuses were `ok` for every row. Thus the
observed limitation is the certification search budget, not a downstream
workflow failure.

The hosted artifact is
`sdna-certification-usability-34895397606`. Its principal checksums are:

| File | SHA-256 |
| --- | --- |
| `results.csv` | `4ec0068d8fe2b2b62df45fccbbf71f884c50589e319e48c3a2400111ae051918` |
| `summary.json` | `139a803c804e5382515a64b62f4fc764b90b6e0e568f7f579e2b651b0f3af1f6` |
| `summary.md` | `e61a141a7775482c5e43f79126f3a1be4aebf8eb52db264a7c9f673f91dc2975` |

This is diagnostic evidence, not an authorization to increase the
certification budget or promote a cap. Cap 2 remains the v0.1 production
baseline; any future change requires a separate pre-specified decision.

Regardless of the result, cap 2 remains the v0.1 production baseline. A
future cap-promotion decision would require a separate, explicitly approved
methodological decision supported by the audit evidence and any additional
validation it calls for.
