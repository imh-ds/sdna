# Task 24: Full paired search-cap expansion study

**Status:** Approved design; implementation begins only after this specification is reviewed.

## Goal

Pre-specify a complete, paired validation study to determine whether the
observed reach boundary is materially attributable to the greedy search cap.
The study compares the frozen v0.1 baseline (`search_cap=2`) with candidate
caps 3 and 4 while holding the simulated data, row keys, and random seeds
fixed across arms. It is a methodological sensitivity study, not an
automatic production-cap change.

The study follows the hosted reach-boundary diagnostic in
[`reach_boundary_study_v1.md`](../../methodology/reach_boundary_study_v1.md),
but upgrades each arm from a reach-only check to the complete simulation
workflow: SDNA search, exact certification, calibration, the Wald comparator,
and the shrinkage bootstrap.

## Context and relationship to v0.1

The v0.1 primary matrix is frozen at `search_cap=2`. The reach-boundary study
showed paired availability gains for caps 3 and 4, but it intentionally did
not make calibration, certification, bootstrap, or runtime claims. Therefore,
this study must not silently revise the v0.1 matrix or retroactively select a
more favorable cap. Its result is evidence for a later decision about the
operating envelope.

The production baseline remains cap 2 throughout this task. No result from
this study promotes cap 3 or cap 4 automatically.

## Frozen study design

### Arms

Run exactly these three arms:

| Arm | `search_cap` | Role |
| --- | ---: | --- |
| `baseline_cap2` | 2 | Frozen v0.1 comparator |
| `cap3` | 3 | Candidate sensitivity arm |
| `cap4` | 4 | Candidate sensitivity arm |

No other cap, target, stress configuration, or optimization variant may be
added to the primary artifact. Additional exploratory runs, if needed, must
be separate artifacts and must not be pooled with this study.

### Matrix and workload

Each arm uses the frozen v0.1 matrix:

- seed: `20260910`;
- scenarios: all six v0.1 scenarios;
- sample sizes: `N = [50, 100, 150]`;
- predictor counts: `p = [5, 10, 20]`;
- population partial correlation: `0.2`;
- contamination case: `3`;
- replications per cell: `10`;
- configured fragility targets: `[0.9, 0.7, 0.5, 0.3]`;
- primary cap-comparison target: `0.5`;
- calibration simulations per row: `25`;
- bootstrap resamples per row: `100`;
- certification combination budget: `1000`;
- bootstrap confidence level: `0.95`.

The six scenarios × three sample sizes × three predictor counts × ten
replications produce 540 simulation rows per arm and 1,620 rows across the
three-arm study. The declared row count is an acceptance condition, not an
estimate.

### Pairing and random-number semantics

The three arm members of a row are defined by the same key:

`(scenario, N, p, population_parameter_id, contamination_case, replication)`.

For each key:

1. generate one simulated predictor/outcome dataset;
2. run the three estimator workflows on that same dataset;
3. vary only `search_cap` between the arms; and
4. use named, independently derived random-number streams for calibration and
   bootstrap work.

The data-generation seed and all child seeds must be recorded in every arm's
row. Where a stochastic downstream operation is otherwise identical, its
child seed is shared across cap arms so that arm differences are attributable
to the search cap rather than an avoidable random draw. Search-cap-dependent
candidate enumeration may differ; that is the intended treatment contrast.

The artifact must include enough provenance to verify that paired rows used
identical generated data. A digest of the generated data, or an equivalent
stable dataset identity, is required in addition to the row key and seeds.

## Estimands and reported endpoints

### Primary endpoint

The primary estimand is the paired change in availability at fragility target
`0.5`:

- transition counts for cap 2 → cap 3 and cap 2 → cap 4;
- paired reach-rate differences with confidence intervals or an explicitly
  documented descriptive interval method; and
- stratified summaries by scenario, `N`, and `p` in addition to the pooled
  summary.

The transition table must distinguish `unreached`, `reached`, `numerical
error`, and any other declared non-finite status. An unreached row is not a
zero fragility estimate.

### Secondary endpoints

For each arm, and for paired contrasts where valid, report:

- calibration availability and calibration-status counts;
- exact-certification availability, selected subset size, and certification
  status counts;
- bootstrap success, rejection, and explicit resample-failure counts;
- false-flag behavior against the known simulation truth, with the truth
  metadata and target definition stated in the artifact;
- the SDNA/Wald comparator contrast, with the comparator's intentional
  ordinary-partial behavior labeled rather than treated as a matched-tail
  result;
- pooled metrics and jointly-valid-pair metrics separately;
- denominators for every rate and contrast;
- per-row, per-arm, and total wall-clock runtime; and
- complete-workflow status, including any exception or declared failure.

Pooled arm metrics may use all rows eligible for that arm's estimand. A paired
contrast may use only rows for which both compared arm members are jointly
valid for that contrast. These are different populations and must never be
presented as interchangeable denominators.

## Tail, censoring, and failure rules

The study uses the current calibration contract:

- `require_reached=False` is the default operational mode, so a reference
  tail may be represented as right-censored when the reference target is not
  reached;
- strict mode, `require_reached=True`, remains available and must require all
  reference counts needed by that mode to be observed;
- the artifact must record which mode was used for each result; and
- no implementation may silently substitute strict-mode results for the
  default right-censored results.

The following states remain distinct:

- numerical failure or exception;
- search not reaching the relevant target;
- an available finite result;
- a right-censored reference tail; and
- a rejected or failed bootstrap resample.

Denominators are declared per endpoint. All generated rows are the denominator
for reach status and technical-failure rates. Finite, reached rows are the
denominator for finite fragility/certification summaries. Jointly-valid pair
metrics require both arm members to satisfy the endpoint's validity contract.
No missing, censored, failed, or invalid result is coerced to zero.

## Reproducibility and artifact contract

The implementation must produce one machine-readable artifact containing:

- the declared study configuration and arm list;
- schema/version information;
- repository commit and Python/package environment information;
- global seed and per-row data/calibration/bootstrap seeds;
- row keys and stable generated-data identities;
- arm-specific `search_cap` values;
- status and failure fields for every workflow stage;
- endpoint values and their denominators;
- runtime fields; and
- a manifest/checksum for the artifact and any companion summary files.

The output must be deterministic under the same commit, configuration, and
runtime contract. A validation command must check the declared 1,620-row
count, arm balance, key uniqueness, cap membership, seed/data pairing,
required status fields, and manifest/checksum consistency before an artifact is
accepted as evidence.

## Practical simulation limits

The full workflow uses the benchmarked limits above rather than increasing
simulation depth during this task. These limits are intended to make the
three-arm comparison practical while preserving the same workload contract as
the frozen primary matrix.

The hosted manual workflow has an operational ceiling of 15 minutes for the
complete 1,620-row study. This is a reproducibility and scheduling guardrail,
not a scientific threshold and not a claim that slower execution is invalid.
If the ceiling is exceeded, the artifact must be retained as a budget
exceedance, the cap remains unpromoted, and any optimization or workload
change requires a separately reviewed task and specification.

The workflow must report total and arm-level runtime, not only a pass/fail
timeout. The study must not add parallelism, cache-dependent behavior, or
algorithmic tuning solely to make the ceiling pass.

## Interpretation and decision rules

The study is technically successful only if all declared rows are represented,
all arms are balanced and paired, the status/failure contract is satisfied,
and the artifact passes provenance and schema validation. Technical success
does not imply that a larger cap is preferable.

After the run, a separate decision-log entry must evaluate:

- paired availability changes at the primary target;
- whether gains are concentrated in specific scenarios, sample sizes, or
  predictor counts;
- changes in certification and calibration availability;
- jointly-valid-pair behavior and denominator loss;
- bootstrap failure/rejection behavior;
- comparator and false-flag behavior;
- runtime and any budget exceedance; and
- whether the resulting operating envelope supports retaining cap 2,
  adopting a candidate cap in a future version, or designing another bounded
  study.

No production default, v0.1 estimand, or published claim changes as part of
the execution itself. Any cap change requires an explicit subsequent decision
and updated validation documentation.

## Workflow and review boundary

The GitHub Actions workflow is manual-only and uploads the complete artifact,
manifest, machine-readable summaries, and human-readable evidence report. It
is not a pull-request gate and has no weekly schedule. The workflow must run
from a reviewed commit and record that commit in the artifact.

Implementation should add only the runner/configuration, validation and
summary code, tests, documentation, and manual workflow required by this
specification. It must not implement a cap-selection heuristic or silently
replace the frozen v0.1 cap-2 workflow.

## Non-goals

- selecting or promoting a new production search cap;
- changing the v0.1 primary matrix;
- optimizing the greedy search or certification algorithm;
- increasing calibration or bootstrap depth without a new specification;
- treating the reach-only boundary artifact as full-workflow evidence; or
- pooling exploratory arms or post hoc configurations into the primary study.
