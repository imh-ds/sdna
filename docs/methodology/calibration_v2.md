# SDNA calibration v2

## Question being calibrated

The calibration procedure asks:

> Is the observed edge more case-fragile than a clean exchangeable Gaussian
> edge produced by the fitted empirical correlation structure at the same
> sample size and dimension?

This is a model-based reference comparison. It is not a test that the observed
edge is zero and it does not produce a formal frequentist p-value.

## Reference generator

Fit the observed data once and retain:

- the empirical, unshrunk correlation matrix `R`;
- the full-sample shrinkage intensity `lambda_full`;
- the sample size `N` and number of variables `p`.

For each simulation `b`, draw `N` independent observations from a zero-mean
Gaussian distribution with correlation `R`. Fit that simulated data using
`lambda_full`, not a newly estimated shrinkage value. The resulting operation

```text
R_sim -> (1 - lambda_full) R_sim + lambda_full I
```

targets the observed fitted shrinkage network in expectation. Generating data
from the already-shrunk `Rs` and shrinking again would apply the operator twice
and is intentionally not used.

The empirical correlation must be positive semidefinite for this generator.
Numerical near-zero negative eigenvalues may be clipped and renormalized;
materially indefinite input raises `CalibrationError`.

## Matched observed and reference searches

The observed edge is analyzed first with the requested edge, target, fixed
shrinkage, and search cap. Every reference dataset uses the same settings. The
calibration result retains:

- observed reach status and greedy count;
- each reference reach status and greedy count;
- each refitted reference edge estimate;
- the descriptive lower-tail comparison when the observed count is available.

The API has two reach-handling modes. By default,
`require_reached=True` requires the observed search and every reference search
to reach the target, and raises `CalibrationError` otherwise. This is the
strict complete-reach mode. With `require_reached=False`, the observed search
must still reach, but unreached reference searches remain represented as
right-censored observations. An unreached reference means that the bounded
greedy search did not reach the target within the common search cap; it is not
evidence that the exact combinatorial minimum exceeds the cap.

## Reference tail probability

Let `T_obs` be the observed bounded-greedy count and let `T_b` be the count for
reference draw `b`. When a reference search is unreached at cap `c`, its count
is right-censored as `T_b > c`. In censored mode, when the observed search
reaches, the implementation reports

```text
p_ref = (1 + number of reached b with T_b <= T_obs) / (B + 1).
```

Thus, an unreached reference remains in the denominator and does not contribute
to the numerator. If the observed search is unreached, the tail probability is
`None`. When every search reaches, the censored and strict modes produce the
same calculation. These statements concern the bounded greedy-search
procedure, not the exact combinatorial fragility minimum, because greedy
search can miss another coalition within the cap.

The public name is `reference_tail_probability`. Smaller observed fragility
counts are treated as more fragile because fewer deletions are needed to reach
the target. The plus-one correction prevents a reported zero in finite
simulation samples.

`p_ref` is descriptive. It depends on the fitted reference model, the target,
the search algorithm, the reach requirement, and the simulation count. It does
not account automatically for screening many edges, and it must not be
reported as a confirmatory p-value without additional inferential development.

## Reproducibility requirements

Reports should record the random seed or supplied NumPy generator, `n_sim`,
edge, target kind and value, search cap, fixed shrinkage rule, package version,
and the reach statuses. Reference edge estimates should be inspected to check
that the simulated fitted effect is reasonably centered on the observed fitted
effect before interpreting fragility comparisons.

## What this does not calibrate

This procedure does not calibrate:

- an ordinal or polychoric network;
- pairwise-deletion or imputed-data uncertainty;
- temporal dependence or block deletion;
- adaptive-lambda deletion as the primary estimand;
- automatic fragile/not-fragile classifications;
- multiplicity across a whole network.

Temporal and intensive-longitudinal reference models are deferred until their
deletion pipeline is separately specified and validated.
