# Certification-budget sensitivity study v1

**Status:** Pre-specified and implemented; hosted execution and empirical
findings are pending. This study is not a cap-promotion or production-budget
decision.

This page is the Task 26 protocol. The approved
[specification](../superpowers/specs/2026-09-14-task26-certification-budget-sensitivity-design.md)
and [implementation plan](../superpowers/plans/2026-09-14-task26-certification-budget-sensitivity.md)
are binding. The frozen
[study manifest](../../simulations/configs/certification_budget_sensitivity_v1.json),
[runner](../../tools/run_certification_budget_sensitivity.py),
[validator and aggregator](../../tools/summarize_certification_budget_sensitivity.py),
and [manual-only workflow](../../.github/workflows/certification-budget-sensitivity.yml)
are the executable record. ADR-025 is in [the decision log](../development/decisions.md).

## Question, population, and provenance

The study asks whether changing only the certification-combination budget
changes certification yield or its failure mode for exact Task 25 newly
reached records at candidate caps 3 and 4. The Task 25/24 data-generating,
estimation, and inference protocol remains fixed.

The population authority is Task 25 artifact
`sdna-certification-usability-34895397606`, Actions run `34895397606`, commit
`7b22b3fca39888e1a452cb5a7ad8ec244ccd752e`. Its `results.csv` SHA-256 is
`4ec0068d8fe2b2b62df45fccbbf71f884c50589e319e48c3a2400111ae051918`; its
immutable manifest SHA-256 is
`b47842e33092b9431220204f46c77723f2465f86a1685e1cd1c90e601bedd4ff`.

The nested Task 24 source is artifact `sdna-cap-expansion-34871220664`,
Actions run `34871220664`, commit
`338b0d95cdb312b2805affb0de458e06508d80f0`. Its `results.csv` SHA-256 is
`110d0b4f266b253251ac1a64bb4195b61722008d426b74c75802d3de57b43d87`; its
manifest SHA-256 is
`415576f1fec5ccd2a47e0ad411d29e4d48c6e8e370609ae495ccc877fe74e974`.
That value is the nested Task 24 manifest checksum, not the Task 25 checksum.

The selected populations contain 44 cap-3 records (`U_to_R(3)=44`) and 68
cap-4 records (`U_to_R(4)=68`). Their denominators remain separate even when
a pairing key is in the overlap; this is not a claim of 112 unique keys. The
selection rule is exactly Task 25's cap-specific newly reached population,
identified by its canonical pairing keys. No rows are added or removed by
downstream status or post-hoc filtering. The unchanged production baseline is
cap 2, is not rerun, and is outside the budget comparison.

## Fixed sensitivity protocol

The pre-specified budget grid is `[1000, 5000, 10000, 20000]`; `1000` is the
Task 25 baseline. No arm may be added after results are inspected. At sample
sizes 50, 100, and 150, size-two subset counts are 1,225, 4,950, and 11,175,
respectively, so the grid exposes distinct combinatorial boundaries. It does
not imply that 20,000 is universally sufficient.

Only the budget varies. Arms preserve source artifacts, pairing keys, six
scenarios, sample-size grid, parameters, contamination settings, seed
`20260910`, estimator, target `0.5`, fixed-shrinkage and exact-LOO behavior,
calibration (`25` simulations and `calibration_require_reached=False`),
bootstrap (`100` replicates at `0.95`), right-censored calibration, the
ordinary-partial Wald comparator, bootstrap procedures, stage order, and error
handling. One deterministic dataset is shared by each pairing key across
candidate caps and budgets; budget order cannot change data, seeds, digests,
or non-certification outputs.

Each arm has an `1800`-second computation ceiling. A row-level
`combination_budget_exhausted` result is a valid completed outcome, unlike an
arm-level `timeout`, `failed`, or `incomplete` status. A timed-out arm records
its budget, start time, elapsed time, timeout ceiling, expected and completed
rows, last key when known, whether certification itself exhausted its budget,
environment, source checksums, and status. An incomplete arm is not scored as
zero certification yield: diagnostics remain available but yield is
unavailable, so it cannot support a complete sensitivity conclusion.

## Evidence artifacts and validation

Each completed arm has 112 rows: 44 at cap 3 and 68 at cap 4. `results.csv`
has one `(pairing_key, candidate_cap, budget)` row with source digest and
seeds, certification status/reason, exact minimum, combinations checked,
exhaustion flag, elapsed time, and downstream statuses/errors. Arm metadata,
checkpoint/status, validation, and environment records accompany it.

The aggregate retains the selection manifest and emits combined `results.csv`,
`summary.json`, and `summary.md`. It records source identities and checksums,
invariants, grid, cap-specific counts, overlap, arm statuses, endpoints,
reason counts, runtime, and `complete_sensitivity_result`. Completion requires
all four arms and 448 cap-budget rows. Validation checks frozen sources and
selection, preserves separate cap denominators, and matches finite Task 25
numeric fields at tolerance `1e-12`. Keys, categories, booleans, nullability,
seeds, digests, and row membership match exactly; only certification
diagnostics and elapsed time may differ.

The Actions workflow is manual-only (`workflow_dispatch`): it validates and
serializes selection, runs four fixed arms, uploads success/failure artifacts,
and aggregates available evidence. It is not a push, pull-request, or schedule
workflow.

## Interpretation limits and pending hosted evidence

Task 26 has no hosted empirical results here. Hosted run ID, implementation
commit, artifact names and checksums, runtime, arm statuses, yields, reason
counts, and any acceptance finding are pending until manual execution and
artifact validation complete.

An increased yield supports only budget sensitivity for this Task 25 population
under the unchanged protocol. It does not justify cap promotion, production
budget change, or post-hoc budget selection. Zero yield through 20,000 means
only that no selected record certified in this range. A timeout or incomplete
arm is a practical computational limit, not a statistical zero; a further
budget or optimization study needs a new pre-specification.
