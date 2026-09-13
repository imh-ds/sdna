# SDNA v0.1 reach-boundary study v1

## Status and purpose

This document pre-specifies a diagnostic study of the low reach observed in
the hosted v0.1 primary validation. It is a follow-on to
[`falsification_pilot_evidence_v2.md`](../development/falsification_pilot_evidence_v2.md)
and is not a revision of the frozen v0.1 primary matrix.

The study asks whether low reach is primarily:

1. a consequence of the current bounded search cap;
2. a consequence of the 50% attenuation target being difficult for a given
   data-generating process; or
3. associated with numerical stress in heavy-tailed or near-collinear data.

The study is diagnostic evidence. It does not authorize an estimator change,
search-cap change, post-hoc reinterpretation of the primary run, or production
optimization. Any promoted change requires a new validation specification.

## Baseline anchor

The baseline is the hosted primary run at code commit
`e29bfd9548333c561b6cec79456c86038ee07c64`, using
`simulations/configs/falsification_pilot.json` and configuration checksum
`3dbc697c4165f15174143a51ad251a677ec1c65e559eecd841f69c7c8a81118d`.

The baseline uses:

- root seed `20260910`;
- all six scenarios;
- `N=[50, 100, 150]` and `p=[5, 10, 20]`;
- ten replications per scenario/cell;
- relative fragility target `0.5`;
- `search_cap=2`;
- fixed full-sample shrinkage;
- certification budget `1000` in the primary workflow;
- calibration and bootstrap settings from the primary matrix.

The hosted baseline contains 540 rows. Its observed reach rates are 44/90 for
`clean_planted_edge`, 80/90 for `single_influential_case`, 71/90 for
`coalition_contamination`, 66/90 for `mixture_subgroup`, 19/90 for
`heavy_tails`, and 0/90 for `collinearity_stress`.

## Study design

### Common matrix and pairing

All arms use the same `N`, `p`, scenario, and replication grid as the primary
matrix. The diagnostic arm is paired to the baseline by
`(scenario, N, p, parameter_id, replication)`. The baseline arm must reuse the
primary row seeds. Search-cap arms must use the same generated `X` as the
baseline for each paired row. Data-generating-process sensitivity arms use the
same row seed but intentionally generate a different `X` under the declared
stress parameter.

The reach-boundary runner is reach-only. It runs the observed greedy search
and records the numerical diagnostics needed to interpret reach. It does not
run calibration, the Wald comparator, the shrinkage bootstrap, or exact
certification. Therefore it makes no new claims about reference tails,
bootstrap intervals, AUC, or exact minimum fragility.

### Frozen arms

All arms below are fixed before execution. No additional search cap, target,
tail parameter, or collinearity parameter may be added after inspecting the
results.

| Arm | Scenario scope | Target | Search cap | DGP override | Rows | Purpose |
|---|---|---:|---:|---|---:|---|
| `baseline_cap2` | all six scenarios | 0.5 | 2 | none | 540 | Reproduce the primary reach outcome |
| `cap3` | all six scenarios | 0.5 | 3 | none | 540 | Test one additional greedy deletion |
| `cap4` | all six scenarios | 0.5 | 4 | none | 540 | Test a second bounded search extension |
| `target07_cap2` | all six scenarios | 0.7 | 2 | none | 540 | Separate target difficulty from cap difficulty |
| `heavy_df8` | `heavy_tails` only | 0.5 | 2 | degrees of freedom `8` | 90 | Compare a less-heavy declared tail regime |
| `collinear_rho90` | `collinearity_stress` only | 0.5 | 2 | adjacent correlation `0.90` | 90 | Compare a less-severe declared collinearity regime |
| `collinear_rho99` | `collinearity_stress` only | 0.5 | 2 | adjacent correlation `0.99` | 90 | Compare a more-severe declared collinearity regime |

The study therefore contains 2,430 reach-only rows. `heavy_tails` with the
existing default degrees of freedom `5` and `collinearity_stress` with the
existing adjacent correlation `0.95` are represented by the baseline arm; the
severity arms are not substitutes for those baseline scenarios.

The `target07_cap2` arm is a diagnostic sensitivity arm. It must not be
reported as evidence for the primary 50% attenuation estimand. Likewise, the
three DGP severity levels are operating-boundary probes, not a license to
rename the v0.1 scope after seeing the result.

## Required row-level outputs

Every arm row must retain the arm identity, paired baseline key, seed, `N`,
`p`, scenario, target, and DGP override. It must also record:

- `reached` and `greedy_count`;
- the configured cap and whether the final search step exhausted that cap;
- the full edge value and final trajectory edge value;
- the complete greedy trajectory or an equivalent auditable representation;
- fitted shrinkage;
- fitted rank;
- minimum eigenvalue of the unshrunk correlation;
- minimum eigenvalue of the shrunk correlation;
- shrunk-correlation condition number;
- elapsed seconds;
- an error status and message if a row fails numerically.

Failed rows must remain visible in the artifact. A numerical exception is not
converted to `reached=False`, and an unreached search is not converted to a
finite deletion count.

## Primary and secondary endpoints

The primary endpoint is observed-search reach by arm and scenario/cell:

```text
reach_rate = reached_rows / all_generated_rows
```

For each candidate arm versus `baseline_cap2`, report:

- the paired transition counts `0 -> 0`, `0 -> 1`, `1 -> 0`, and `1 -> 1`;
- the paired reach difference, `candidate_rate - baseline_rate`;
- the count of newly reached rows, `0 -> 1`;
- the median candidate greedy count among rows newly reached by the candidate;
- the median extra deletions for rows reached in both arms;
- censoring and failure counts with their denominators.

Secondary endpoints are:

- final trajectory value relative to the target boundary;
- fitted condition number and minimum eigenvalue distributions;
- row-level runtime and total runtime;
- certification is not an endpoint of this reach-only study and must not be
  inferred from a reached greedy result.

Reach rates and paired differences are descriptive. No p-values, false-discovery
claims, or automatic pass/fail threshold are defined. The paired transitions
are the primary comparison because the cap arms share the same simulated data.

## Interpretation rules

The following interpretations are fixed before execution:

- If `cap3` or `cap4` changes many baseline `0 -> 1` rows while diagnostics
  remain finite, the baseline is search-cap sensitive. This supports a new
  search-boundary proposal; it does not retroactively make the cap-2 primary
  results uncensored.
- If increasing the cap produces few or no new reaches, the observed boundary
  is not explained by the first two cap extensions. The target difficulty or
  the DGP regime remains the leading explanation, subject to the trajectory
  and numerical diagnostics.
- If `target07_cap2` reaches substantially more rows, the 50% target is a
  stricter availability requirement for these scenarios. The 70% result is a
  sensitivity description, not a replacement estimand.
- If reach loss tracks high condition numbers or small shrunk-correlation
  eigenvalues while cap changes do not restore reach, record numerical stress
  as a limitation. Do not silently regularize more strongly in this study.
- If the DGP severity arms change reach, record the method's stress-regime
  boundary. Do not select a preferred degrees-of-freedom or correlation value
  after inspecting the results.
- A numerical error, an unreached search, and a certified result are distinct
  states and must remain distinct in all summaries.

No arm is promoted automatically. Before any full simulation workflow is run
with a changed cap, target, or DGP parameter, a new decision-log entry must
name the arm, its intended estimand, and the validation matrix that will be
used to compare it with this baseline.

## Technical acceptance

The reach-boundary artifact is technically accepted only if:

- all 2,430 expected rows are present with the declared arm/cell counts;
- the baseline arm reproduces the primary matrix's scenario/cell counts and,
  under a matched Python/NumPy environment, its row-level reach statuses;
- cap arms use the same paired row seeds and data as `baseline_cap2`;
- all declared DGP overrides are present only in their named arms;
- all successful numeric diagnostics are finite and in their valid ranges;
- failures are represented explicitly rather than coerced into censoring;
- no undeclared arm or parameter appears;
- the artifact records the Git commit, Python version, NumPy version, manifest
  checksum, and runtime metadata.

Technical acceptance does not imply favorable methodological performance.

## Reproducibility and artifact contract

The future runner must retain:

- the machine-readable arm manifest and checksum;
- the baseline commit and primary configuration checksum;
- row seeds and paired row keys;
- CSV rows, JSON summary, and Markdown summary;
- Python, NumPy, package, and platform metadata;
- the exact command and profile used to generate the artifact.

The study artifact belongs in a manually invoked workflow or an explicitly
recorded local run. It is not a pull-request gate and is not a weekly job.
Generated results remain outside Git unless a later decision explicitly adds a
small, reviewable fixture.

## Non-goals

- No production optimization or vectorization.
- No change to the v0.1 primary configuration.
- No adaptive selection of arms based on intermediate results.
- No inference that an unreached cap-4 search has an exact minimum larger than
  four.
- No claim that reach is missing at random.
- No extension to missing, ordinal, longitudinal, or causal data.

## Next decision after execution

Use the paired transition and numerical-diagnostic tables to choose one of
three bounded conclusions:

1. retain cap-2 and document the observed availability boundary;
2. draft a new cap-expansion specification with a full-workflow runtime and
   certification budget; or
3. narrow the declared v0.1 stress-scenario scope while preserving the
   scenarios as failure-boundary tests.

The choice must be recorded before implementation changes are made.
