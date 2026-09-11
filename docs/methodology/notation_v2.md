# SDNA notation v2

This notation matches the experimental v0.1 implementation. The symbol names
are descriptive rather than a commitment to a final paper-facing method name.

## Data and fitted network

Let `X` be an `N x p` matrix of complete continuous observations. After
column-wise sample standardization, let `Z` denote the standardized matrix.

```text
R = Z^T Z / (N - 1)
Rs = (1 - lambda) R + lambda I
Omega = Rs^(-1)
rho_ij = -Omega_ij / sqrt(Omega_ii Omega_jj),  i != j
```

The returned partial-correlation diagonal is set to one. `lambda` is the
full-sample shrinkage intensity and is held fixed in primary deletion/refit
analyses.

## Exact and analytic influence

For a case `k`, define the exact fixed-shrinkage leave-one-out effect as

```text
Delta_LOO[k,i,j] = rho_ij^(-k) - rho_ij^full.
```

The complete tensor `Delta_LOO` has shape `N x p x p` and is returned by
`exact_loo_influence`. The analytic tensor, written `Delta_tilde`, is a
first-order approximation derived by propagating the case influence through
the estimator. It is returned by `analytic_influence` and is never the
authoritative finite-deletion quantity.

## Fragility targets

Let `rho_full = rho_ij^full` and `rho_after(S)` be the edge estimate after
deleting case set `S`. A target predicate is evaluated as follows:

```text
relative:      |rho_after(S)| <= q |rho_full| + tolerance, 0 < q < 1
absolute:      |rho_after(S)| <= a + tolerance,             a >= 0
sign_reversal: rho_after(S) rho_full <= tolerance
```

The ideal combinatorial count is

```text
F_ij(target) = min |S| subject to the target predicate.
```

The greedy search does not redefine this estimand. Its `greedy_count` is an
upper bound when reached. `exact_minimum` is populated only after exhaustive
checking of all smaller subset sizes within the configured budget.

## Fragility profile

For a set of relative fractions `q`, the profile is the collection

```text
q -> F_ij(relative(q)).
```

Each fraction is searched independently because the selected coalition can
depend on the target. A search that does not reach its target before its cap is
censored rather than assigned the cap as a valid count.

## Calibration

Let `R` be the observed empirical, unshrunk correlation matrix and `lambda`
the observed full-sample shrinkage. Reference datasets are drawn from a
Gaussian distribution with correlation `R`; each is then fit using fixed
`lambda`. This avoids applying the shrinkage operation twice to an already
shrunk generating matrix.

For observed count `F_obs` and reference counts `F_1, ..., F_B`, when all counts
are reached, the descriptive lower-tail reference probability is

```text
reference_tail_probability =
    (1 + sum_b I(F_b <= F_obs)) / (B + 1).
```

The name deliberately avoids `p_value`: this quantity is conditional on the
chosen reference model and search procedure, and formal inferential
properties have not been established.

## Influence concentration diagnostics

Case leverage for case `k` is

```text
L_k = sum_{i < j} |Delta_LOO[k,i,j]|.
```

Each undirected edge is counted once. For edge `(i,j)`, let
`a_k = |Delta_LOO[k,i,j]|`, let `m = ceil(0.05 N)`, and let `a_(1) >= ... >=
a_(N)` be the sorted values. Edge concentration is

```text
C_ij = sum_{r=1}^m a_(r) / sum_{k=1}^N a_k,
```

with `C_ij = 0` when the denominator is zero. Both are descriptive exact-LOO
summaries and require an `InfluenceResult` whose method is `exact_loo`.

## Scope notation

The notation assumes independent exchangeable rows and continuous variables.
It does not define a valid operator for polychoric correlations, pairwise
missingness, or time-series deletion. Those extensions need their own
estimands and notation.
