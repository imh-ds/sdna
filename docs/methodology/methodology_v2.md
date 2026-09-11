# SDNA methodology v2

## Purpose and status

Structured Deletion Network Analysis (SDNA) is an experimental diagnostic for
asking whether estimated partial-correlation edges are broadly supported across
observations or disproportionately changed by particular cases or coalitions.
This v2 document describes the tested Python implementation at version
`0.1.0a0`. It records implementation behavior and methodological limits; it is
not a claim that the method provides causal discovery, confirmatory graph
recovery, or a universal edge-validity test.

The original proposal is preserved for provenance in the
[`original supplement`](../archive/SDNA_methodology_supplement_original.md).
The decisions and rationale behind the corrections below are recorded in
[`docs/development/decisions.md`](../development/decisions.md).

## Scope boundary

v0.1 accepts complete continuous data with independent, exchangeable rows. It
does not silently generalize to ordinal/polychoric estimators, pairwise
missing-data handling, longitudinal dependence, EMA/ESM, or VAR/GVAR models.
Those settings require separate estimands, deletion schemes, and validation.

The method is descriptive and diagnostic. It does not establish that an edge
is true, causal, stable in a new sample, or free of confounding.

## Estimation

For an `N x p` data matrix `X`, SDNA standardizes each column using its sample
mean and sample standard deviation (`ddof=1`). It computes the empirical
correlation matrix `R`, estimates a shrinkage intensity `lambda` toward the
identity, and forms

```text
Rs = (1 - lambda) R + lambda I.
```

The precision matrix is `Omega = inverse(Rs)`. The off-diagonal partial
correlation is

```text
rho[i,j] = -Omega[i,j] / sqrt(Omega[i,i] * Omega[j,j]).
```

The fitted result retains the standardized data and all intermediate matrices,
the shrinkage value, and numerical diagnostics. When a subset is refit for a
deletion analysis, the full-sample `lambda` is held fixed so that the primary
change reflects the deleted observations rather than a changing regularization
parameter.

## Individual-case influence

The canonical deletion effect for case `k` and edge `(i,j)` is

```text
Delta_LOO[k,i,j] = rho_without_k[i,j] - rho_full[i,j].
```

`exact_loo_influence` computes this by refitting after each single-row
deletion, with full-sample fixed shrinkage. Its `N x p x p` tensor is the
authoritative individual-case influence output.

`analytic_influence` computes a first-order chain-rule approximation through
correlation, shrinkage, inversion, and the partial-correlation transform. It
can accelerate ranking and search, but it is not an exact deletion effect and
must be labeled as an approximation in reports.

## Edge fragility

An edge fragility count is the number of deleted cases needed to meet an
explicit target. The implementation supports three separate targets:

- `relative`: `abs(rho_after) <= value * abs(rho_full)`;
- `absolute`: `abs(rho_after) <= value`;
- `sign_reversal`: `rho_after * rho_full <= tolerance`.

`greedy_fragility` uses analytic influence to rank candidates, then verifies
each accepted deletion with an exact fixed-shrinkage refit. A reached greedy
count is a candidate upper bound, not automatically the combinatorial minimum.
If the search cap is exhausted without reaching the target, the result is
censored (`reached=False`, `greedy_count=None`).

`certify_fragility` can enumerate all smaller subsets within a combination
budget. Only that bounded exhaustive check can set `certified=True` and report
`exact_minimum`. `fragility_profile` repeats the explicit relative-target
search over a caller-supplied grid, preserving target-specific results.

The neutral term “edge fragility count” is intentional. The v0.1 API does not
freeze a branded “Network Fragility Index.”

## Model-based reference calibration

Calibration asks whether the observed edge-fragility result is unusual relative
to a clean exchangeable Gaussian reference that reproduces the observed fitted
network in expectation. It is not a test of whether the edge is zero.

The reference generator uses the fitted *unshrunk* empirical correlation `R`.
Each simulated dataset is fit with the observed full-sample fixed `lambda`, so
the same shrinkage operator is applied once to the simulated sample. Simulated
fragility searches use the same edge, target, and search-cap settings as the
observed search.

The result includes simulated refitted edge estimates, reach indicators, and a
lower-tail comparison named `reference_tail_probability`, using the plus-one
correction when all required fragility counts are observed. This is a
model-based descriptive reference probability, not a formal frequentist
`p_value`; it does not by itself address multiplicity or guarantee calibration.
See [`calibration_v2.md`](calibration_v2.md) for the operational details.

## Network- and case-level summaries

The fitted edge value remains an effect-size summary. Case-level summaries
include:

- `case_leverage`, the sum over unique undirected edges of each case’s
  absolute exact-LOO changes;
- `edge_concentration`, the share of an edge’s total absolute exact-LOO change
  held by the largest `ceil(0.05 * N)` cases by default.

These are descriptive diagnostics. The core does not attach inferential
probabilities, cluster influence signatures, or issue automatic fragile/not-
fragile labels.

## Interpretation and reporting

Reports should state the data scope, full-sample shrinkage rule, influence
method, fragility target, search cap, certification status, and calibration
generator. A concise per-edge report can include the fitted partial
correlation, greedy count and selected cases, certification metadata, and any
reference-tail probability with its simulation settings.

Claims about `bootnet`, EBICglasso, or BGGM require actual comparator
implementations with documented settings. The repository’s Python bootstrap is
a shrinkage-bootstrap benchmark and should not be presented as a direct
implementation of another package’s workflow.

## Deferred extensions

Temporal and intensive-longitudinal analyses are future method projects. In a
VAR/GVAR workflow, deleting an occasion changes lagged observations, temporal
coefficient estimates, residual covariance, and the contemporaneous network;
the cross-sectional derivative cannot simply be carried over. Missing-data,
ordinal, R-package, and automatic classification extensions are likewise
deferred until the v0.1 operating behavior is characterized.
