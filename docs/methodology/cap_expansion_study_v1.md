# Paired full-workflow search-cap expansion study v1

**Status:** Pre-specified, implemented, and technically validated by hosted
run [`34871220664`](https://github.com/imh-ds/sdna/actions/runs/34871220664)
on merge commit `338b0d95cdb312b2805affb0de458e06508d80f0`. The hosted artifact
is accepted as technical evidence for this study; it does not promote a cap
or change the v0.1 production baseline.

This page is the user-facing description of Task 24. The approved design
specification is [`2026-09-14-task24-cap-expansion-design.md`](../superpowers/specs/2026-09-14-task24-cap-expansion-design.md),
and the implementation plan is
[`2026-09-14-task24-cap-expansion.md`](../superpowers/plans/2026-09-14-task24-cap-expansion.md).
The decision was introduced in commit `bb7a851` and is recorded in
[`docs/development/decisions.md`](../development/decisions.md).

## Purpose and boundary

The hosted reach-boundary diagnostic found paired availability changes for
search caps 3 and 4, but it intentionally evaluated reach only. Task 24 tests
whether those changes persist through the complete workflow: greedy SDNA
search, exact certification, model-based calibration, the ordinary-partial
Wald comparator, the shrinkage bootstrap, truth-aware influence metrics, and
runtime accounting.

The frozen v0.1 primary workflow remains `search_cap=2`. This study does not
change that default, the v0.1 estimand, or the existing reach-only evidence.
No cap is promoted automatically by a technically successful run.

## Frozen matrix and arms

The committed configuration is
[`cap_expansion_v1.json`](../../simulations/configs/cap_expansion_v1.json).
It declares exactly three arms:

| Arm | Search cap | Role |
| --- | ---: | --- |
| `baseline_cap2` | 2 | Frozen v0.1 comparator |
| `cap3` | 3 | Candidate sensitivity arm |
| `cap4` | 4 | Candidate sensitivity arm |

All arms use seed `20260910`, the six v0.1 scenarios, `N=[50,100,150]`,
`p=[5,10,20]`, one clean partial-correlation parameter, contamination count
3, and ten replications per cell. This yields 540 rows per arm and 1,620
rows total. The complete-workflow budgets are 25 calibration simulations, 100
bootstrap resamples, certification combination budget 1000, and confidence
level 0.95. The primary cap comparison uses relative fragility target 0.5.

## Pairing and reproducibility

The three arm members share the key
`(scenario, N, p, parameter_id, replication)`. One dataset is generated per
key and its stable digest is recorded in every arm row. Data, calibration, and
bootstrap seeds are recorded separately; calibration and bootstrap child seeds
are shared across arms so that the intended contrast is the search cap rather
than an avoidable random draw.

The implementation is in
[`tools/run_cap_expansion.py`](../../tools/run_cap_expansion.py), with the
frozen manifest contract in
[`tools/cap_expansion_manifest.py`](../../tools/cap_expansion_manifest.py) and
the reusable stage execution in
[`simulations/full_workflow.py`](../../simulations/full_workflow.py).

## Status, censoring, and metric populations

Unreached search, numerical error, finite result, right-censored reference
tail, and rejected bootstrap resample are separate states. With
`require_reached=False`, the default calibration mode retains unreached
reference draws as a right-censored tail contribution. Strict mode remains
available with `require_reached=True` and requires the observed and reference
targets needed by that mode to be reached. The result records which mode was
used.

Pooled arm metrics use all rows eligible for that arm's endpoint. A paired
contrast uses only rows where both arm members are jointly valid for the
specific metric. The evidence report therefore presents pooled and
jointly-valid metrics with separate denominators; missing, censored, failed,
or invalid values are never converted to zero.

The cap-specific validator and report are in
[`tools/summarize_cap_expansion.py`](../../tools/summarize_cap_expansion.py).
They check the exact row count, arm balance, key uniqueness, paired seeds and
digests, stage statuses, manifest checksum, metadata counts, and summary
agreement before an artifact is accepted as technical evidence.

## Runtime and interpretation

The hosted operational ceiling is 15 minutes for the 1,620-row study. This is
a scheduling/reproducibility guardrail, not a scientific threshold. A budget
exceedance remains in the artifact and is reported separately; it does not
authorize optimization or cap promotion.

The manual-only workflow is
[`cap-expansion.yml`](../../.github/workflows/cap-expansion.yml). It runs on
Python 3.11, records GitHub and package provenance, validates the artifact,
and uploads the CSV, metadata, manifest, summaries, command record, and
human-readable report. It is not a pull-request gate and has no weekly
schedule.

The confirmed hosted run produced 1,620 rows (540 per arm) in 370.44 seconds,
under the 900-second ceiling. It reported 964 reached and 656 unreached
fragility rows; 852 certified, 112 not certified, and 656 skipped-as-unreached
rows; and 462 finite, 502 right-censored, and 656 observed-unreached
calibration rows. The artifact checksums are:

| File | SHA-256 |
| --- | --- |
| `results.csv` | `110d0b4f266b253251ac1a64bb4195b61722008d426b74c75802d3de57b43d87` |
| `summary.json` | `6695edf0cabcf02dc9f74b541302b4134266ad8f6eeaa80f8a2e4c2c63c3a717` |
| `summary.md` | `faefe202925f2ad2594c963d8517cb0cf446c47fd223f75f4e0d17f03b5bcee1` |

The paired transitions from cap 2 were 44 unreached-to-reached rows for cap
3 and 68 for cap 4, with no reached-to-unreached rows. Those newly reached
rows were not certified. Therefore cap 2 remains the v0.1 production
baseline, while caps 3 and 4 remain diagnostic sensitivity arms. The complete
decision, provenance, and cross-runtime validator correction are recorded in
[`docs/development/decisions.md`](../development/decisions.md), including the
follow-up validator commit `785761a` and its regression coverage.
