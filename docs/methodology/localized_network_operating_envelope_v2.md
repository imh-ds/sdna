# Task 27: Localized Network Operating Envelope (v2 acceptance addendum)

**Status:** Acceptance-contract clarification before hosted execution. No
empirical results are reported here.

This addendum preserves the frozen study design in
[`localized_network_operating_envelope_v1.md`](localized_network_operating_envelope_v1.md).
The root seed, matrix, estimands, and interpretation limits are unchanged.
Where v1's technical acceptance text requires deterministic fields to
reproduce under a matched rerun, this page specifies the executable procedure.

## Result and numerical-diagnostic contract

Each result row carries `condition_number`, the 2-norm condition number of the
shrinkage-regularized sample correlation matrix that SDNA inverts. It is
recorded only when fitting succeeds. Cell summaries report mean, minimum, and
maximum condition number, each with valid-row and scheduled-row counts. The
estimated shrinkage intensity (`lambda`) receives the same cell summaries.
Fit failures retain missing numerical diagnostics and remain counted in the
scheduled denominator; they are not encoded as zero.

An influence-stage failure is a valid scheduled workflow outcome for a
contaminated row. The row retains its completed core-stage results and
`workflow_status=error`, `error_stage=influence`, and the exception metadata.
It contributes to failure counts, not to influence-recovery metrics. An
influence error on a clean row is invalid because that stage is not run for
clean data.

## Matched-rerun acceptance procedure

1. Dispatch the manual workflow with `matched_rerun_run_id` blank. It produces
   the baseline matrix artifacts. If all baseline shards are complete, the
   summary status is `awaiting_matched_rerun`; this is an intermediate artifact
   state, not final technical acceptance.
2. Dispatch the same workflow again at the same commit and provide the
   completed baseline workflow run ID in `matched_rerun_run_id`. The workflow
   downloads those baseline shard artifacts and compares them with the current
   complete rerun artifacts.
3. Final `acceptance_status=complete` requires all matrix checks from v1 and an
   exact match of all deterministic row fields. The comparator requires
   identical Git commit, package version, Python version, NumPy version, and
   manifest checksum across both runs. It excludes only `elapsed_seconds`,
   which is expected to vary. Missing/invalid shards or any deterministic-field
   mismatch prevent acceptance and are recorded in `matched_rerun` details.

The comparator uses the current CSV schema, including the condition-number
diagnostic. It does not compare timestamps or infer empirical performance.
The baseline run may finish successfully while explicitly awaiting its rerun;
only the second workflow can produce final complete acceptance. No numerical
threshold, cap promotion, default change, or scientific success criterion is
introduced by this clarification.

## Decision provenance

The append-only Task 27 decision-log entry records the review findings,
rationale, implementation commits, and files that an independent reviewer
should inspect. Hosted evidence and checksums remain pending until the
accepted artifacts are produced.
