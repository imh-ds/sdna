# Reach-boundary study evidence v1

## Purpose and status

This report records the first execution of the pre-specified reach-boundary
diagnostic in
[`reach_boundary_study_v1.md`](../methodology/reach_boundary_study_v1.md).
The study is reach-only diagnostic evidence. It does not revise the frozen
v0.1 primary matrix, certify greedy results, or provide calibration,
bootstrap, AUC, or inferential evidence.

The manual-only hosted workflow is committed in
[`reach-boundary.yml`](../../.github/workflows/reach-boundary.yml). The
tables below are from the successful hosted run; the local rehearsal is
reported separately as a reproducibility comparison.

## Hosted execution provenance

| Field | Value |
|---|---|
| Workflow run | [`34784346096`](https://github.com/imh-ds/sdna/actions/runs/34784346096) |
| Commit | `d32f5478b1eb943f93357515cba0fa5cb78ccd1e` |
| Ref | `main` |
| Python | `3.11.16` |
| NumPy | `2.4.6` |
| Package | `0.1.0a0` |
| Manifest checksum | `6fbb95ac26c45bf6f1a0791c528b80b70870c0457d756ffbe626d2719773c794` |
| Rows | `2,430` |
| Statuses | `2,430 ok`, `0 error` |
| Runtime | `14.249 seconds` |
| Artifact | `sdna-reach-boundary-34784346096` |

The hosted workflow completed the full run, summary, manifest/provenance
validation, and 90-day artifact upload. The hosted artifact is the
authoritative evidence record for this study.

## Local reproducibility comparison

The preceding local rehearsal used commit `16bfe14f`, Python `3.12.14`, and
NumPy `2.5.1`, and completed in `23.865 seconds`. Against the hosted CSV, it
had identical row keys, seeds, statuses, and reach values for all 2,430 rows.
Floating diagnostics were also numerically close: the largest absolute
difference was `8.1e-11` for condition number, and every compared diagnostic
was within `1e-12` relative/absolute tolerance. This supports reproducibility
of the discrete reach conclusions while retaining the environment metadata
needed to interpret small floating-point differences.

## Arm counts and reach

| Arm | Rows | Reached | Censored | Errors | Reach rate | Median condition number | Hosted runtime (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `baseline_cap2` | 540 | 280 | 260 | 0 | 51.9% | 1.168 | 2.645 |
| `cap3` | 540 | 316 | 224 | 0 | 58.5% | 1.168 | 3.296 |
| `cap4` | 540 | 343 | 197 | 0 | 63.5% | 1.168 | 3.892 |
| `target07_cap2` | 540 | 340 | 200 | 0 | 63.0% | 1.168 | 2.429 |
| `heavy_df8` | 90 | 14 | 76 | 0 | 15.6% | 1.260 | 0.532 |
| `collinear_rho90` | 90 | 0 | 90 | 0 | 0.0% | 101.125 | 0.598 |
| `collinear_rho99` | 90 | 0 | 90 | 0 | 0.0% | 336.693 | 0.597 |

The baseline arm's scenario totals are `44/90`, `80/90`, `71/90`, `66/90`,
`19/90`, and `0/90` for `clean_planted_edge`,
`single_influential_case`, `coalition_contamination`, `mixture_subgroup`,
`heavy_tails`, and `collinearity_stress`, respectively. These totals reproduce
the hosted primary reach counts and preserve the primary row grid. The
machine-readable summary retains every arm/scenario/cell diagnostic; no cells
were selected for omission from the artifact.

## Paired transitions versus `baseline_cap2`

The cap arms reuse the same generated data and row keys as the baseline. The
severity arms use the same row keys and seeds but intentionally generate their
declared alternative DGPs.

| Candidate | Matched | 0 -> 0 | 0 -> 1 | 1 -> 0 | 1 -> 1 | Baseline errors | Candidate errors | Reach difference | Median new count | Median extra deletions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `cap3` | 540 | 224 | 36 | 0 | 280 | 0 | 0 | +6.7 pp | 3.0 | 0.0 |
| `cap4` | 540 | 197 | 63 | 0 | 280 | 0 | 0 | +11.7 pp | 3.0 | 0.0 |
| `target07_cap2` | 540 | 200 | 60 | 0 | 280 | 0 | 0 | +11.1 pp | 2.0 | 0.0 |
| `heavy_df8` | 90 | 68 | 3 | 8 | 11 | 0 | 0 | -5.6 pp | 0.0 | 0.0 |
| `collinear_rho90` | 90 | 90 | 0 | 0 | 0 | 0 | 0 | 0.0 pp | n/a | n/a |
| `collinear_rho99` | 90 | 90 | 0 | 0 | 0 | 0 | 0 | 0.0 pp | n/a | n/a |

Errors are reported separately from censoring. In the hosted run there were no
numerical errors; `0 -> 0` includes jointly unreached searches, not failed
rows.

## Interpretation boundaries

The hosted run supports these bounded observations:

- Increasing the cap from two to three and four deletions creates 36 and 63
  newly reached paired rows, respectively. The cap-2 result is therefore
  search-cap sensitive for this diagnostic, but remains the frozen v0.1
  primary result.
- Raising the target to 70% creates 60 newly reached rows. This is a target
  sensitivity result, not evidence for replacing the 50% estimand.
- The less-heavy-tail arm has lower reach than the baseline heavy-tail arm in
  this realization, and both collinearity severity arms have zero reach. The
  condition-number summaries show a large numerical-stress signal for the
  collinearity arms, but do not establish a causal mechanism or authorize
  stronger regularization.
- The study does not establish exact minima beyond the bounded greedy search.
  A reached row remains a greedy upper bound unless separately certified.

These are descriptive paired transitions, not p-values, pass/fail thresholds,
or population performance estimates. The full arm/scenario/cell tables in
`summary.json` and `summary.md` are the auditable record, including all
declared cells and runtime values.

## Decision and limitations

For v0.1, retain the cap-2 primary matrix and its explicit reach limitations.
Do not silently promote cap-3, cap-4, the 70% target, or a stress-arm change
into the production workflow. If improved availability is scientifically
required, draft a separate cap-expansion specification that includes the full
simulation workflow, certification budget, runtime, and the same paired
failure/censoring contract.

The remaining limitations are:

- reach is outcome-dependent and is not assumed missing at random;
- the study is reach-only and supplies no new calibration, bootstrap, AUC, or
  exact-minimum evidence;
- the stress-arm sample sizes are 90 rows and the per-cell denominators are
  ten, so the results are diagnostic rather than stable population estimates;
- GitHub emitted a non-blocking Node.js 20 deprecation warning for the v4
  checkout, setup-python, and upload-artifact actions; the run passed, but
  those action versions should be revisited before the hosted runner removes
  its compatibility fallback.
