# SDNA decision log

This log records methodological and architecture decisions for the experimental
v0.1 implementation. It is append-only in spirit: later changes should add a
new entry rather than silently rewriting the rationale for an earlier choice.
The original supplement remains available in the
[`original supplement`](../archive/SDNA_methodology_supplement_original.md).

## ADR-001 — Exact LOO is the canonical individual-case influence result

- **Date:** 2026-09-11
- **Decision:** Treat `exact_loo_influence` as the authoritative case-level
  deletion output. Keep `analytic_influence` as an explicitly approximate
  accelerator.
- **Rationale:** Exact fixed-shrinkage refits define the deletion estimand
  directly and are practical at the intended experimental scale. The analytic
  chain-rule result is useful for ranking but does not equal a finite deletion
  effect.
- **Consequences:** User-facing influence claims must be based on exact LOO.
  Analytic results must carry `method="analytic"` and must not be described as
  exact or closed-form deletion effects.
- **Status:** Implemented in `src/sdna/influence.py`.

## ADR-002 — Use neutral edge-fragility terminology

- **Date:** 2026-09-11
- **Decision:** Use “edge fragility count” and the API names
  `greedy_fragility`, `certify_fragility`, and `fragility_profile`; do not use
  “Network Fragility Index” or “NFI” as the v0.1 API or a settled method name.
- **Rationale:** The implementation is experimental, and a neutral name avoids
  implying a standardized index or borrowing established terminology before
  the operating properties are known.
- **Consequences:** Reports should identify the target explicitly, such as a
  relative 50% attenuation target, rather than presenting one universal index.
- **Status:** Implemented in the public module and v2 documentation.

## ADR-003 — Greedy search is an upper bound unless certified

- **Date:** 2026-09-11
- **Decision:** A reached greedy result is a candidate coalition and an upper
  bound on the minimum number of deletions. Only bounded exhaustive search that
  checks all smaller subsets may set `certified=True` and report an exact
  minimum.
- **Rationale:** Greedy-with-refresh can still miss a smaller coalition. Search
  caps can also prevent the target from being reached.
- **Consequences:** `reached=False` with `greedy_count=None` represents a
  censored search. Documentation and tables must distinguish `greedy_count`
  from `exact_minimum`.
- **Status:** Implemented in `src/sdna/fragility.py`.

## ADR-004 — Calibrate from empirical unshrunk correlation with fixed lambda

- **Date:** 2026-09-11
- **Decision:** Generate clean Gaussian reference data from the fitted
  empirical correlation matrix `R`, then apply the observed full-sample
  shrinkage value to each simulated fit.
- **Rationale:** Simulating from an already-shrunk matrix and shrinking again
  attenuates the reference a second time. Using `R` targets the observed
  shrunk correlation in expectation under the fixed operator.
- **Consequences:** Calibration is a matched model-based reference, not a
  generic null and not an adaptive-lambda analysis. The implementation retains
  refitted reference edge estimates for checking the match.
- **Status:** Implemented in `src/sdna/calibration.py`.

## ADR-005 — Calibration output is descriptive

- **Date:** 2026-09-11
- **Decision:** Name the lower-tail comparison
  `reference_tail_probability`; do not call it a `p_value`.
- **Rationale:** The current simulation is a model-based reference comparison
  without established frequentist calibration, multiplicity control, or a
  formal null-testing guarantee.
- **Consequences:** Results should include the generator, fixed-lambda rule,
  simulation count, search mode, and reach status alongside the probability.
  The value must not be used as confirmatory evidence by itself.
- **Status:** Implemented in `src/sdna/results.py` and
  `src/sdna/calibration.py`.

## ADR-006 — Separate fragility targets

- **Date:** 2026-09-11
- **Decision:** Keep relative attenuation, absolute attenuation, and sign
  reversal as distinct `FragilityTarget` kinds with distinct stopping rules.
- **Rationale:** These targets answer different scientific questions. In
  particular, sign reversal is not equivalent to checking whether an edge is
  exactly zero.
- **Consequences:** Every fragility result must retain its target object.
  Sign stability is not a core v0.1 output.
- **Status:** Implemented in `src/sdna/results.py` and
  `src/sdna/fragility.py`.

## ADR-007 — Restrict v0.1 to complete continuous independent observations

- **Date:** 2026-09-11
- **Decision:** The core API makes no claims for ordinal/polychoric data,
  missing-data pairwise deletion, or dependent time-series observations.
- **Rationale:** The estimator and analytic influence derivation are defined
  for standardized continuous observations and an exchangeable row-deletion
  interpretation.
- **Consequences:** EMA/ESM, VAR/GVAR, imputation, and polychoric extensions
  require separate specifications and validation. They are future work, not
  silent generalizations of v0.1.
- **Status:** Documented in the v2 methodology and notation.

## ADR-008 — Do not make comparator-specific claims without implementations

- **Date:** 2026-09-11
- **Decision:** Describe the Python resampling benchmark as a shrinkage
  bootstrap. Make no direct claims about `bootnet`, EBICglasso, or BGGM based
  on analogy.
- **Rationale:** Different software and estimators target different quantities
  and settings. Fair comparison requires actual scripts, pinned versions, and
  a shared output schema.
- **Consequences:** Comparator-specific conclusions are deferred until the
  corresponding implementations and settings are available.
- **Status:** Python bootstrap/Wald comparators exist; external comparator
  scripts remain separately identified and are not used to support claims here.

## ADR-009 — Treat intensive longitudinal analysis as future work

- **Date:** 2026-09-11
- **Decision:** Do not state that the cross-sectional derivative carries over
  directly to EMA/ESM or VAR/GVAR workflows.
- **Rationale:** Deleting an occasion changes lagged pairs, temporal
  coefficients, residuals, and the contemporaneous precision network. That is a
  different deletion pipeline.
- **Consequences:** A temporal extension must derive its own deletion estimand,
  block/window strategy, and reference generator before implementation.
- **Status:** Deferred and explicitly bounded in v2 documentation.

## ADR-010 — Keep case leverage and edge concentration descriptive

- **Date:** 2026-09-11
- **Decision:** Provide exact-LOO case leverage and edge-concentration summaries
  without inferential probabilities, clustering, or automatic fragile/not-
  fragile labels.
- **Rationale:** These summaries help describe concentration of deletion
  effects, but their reference distributions, multiplicity behavior, and
  thresholding properties are not yet validated.
- **Consequences:** `case_leverage` and `edge_concentration` require exact LOO
  inputs and should be reported with the underlying influence definition.
  Influence-signature clustering is deferred.
- **Status:** Implemented in `src/sdna/diagnostics.py`.

## Review corrections 1–8

This section records the decisions made in response to the comprehensive
review of Tasks 1–17. These entries preserve the correction, rationale, and
implementation consequence rather than silently changing an earlier record.

### Correction 1 — Preserve the shrinkage value used for certification

- **Decision:** Store the fitted shrinkage value on `FragilityResult`; when
  certification is requested, reuse that value by default and reject an
  explicitly supplied mismatch.
- **Rationale:** Certification must evaluate the same estimand as the greedy
  result. Replacing its shrinkage value could certify a different network.
- **Consequence:** `certify_fragility` cannot silently certify with the wrong
  shrinkage parameter.

### Correction 2 — Execute the complete simulation workflow

- **Decision:** The simulation runner computes calibration, Wald, and
  shrinkage-bootstrap outputs using independent child seeds, and records the
  fragility target and simulation/bootstrap counts in each row.
- **Rationale:** Placeholder comparator fields do not demonstrate the intended
  end-to-end use case or provide an auditable randomization scheme.
- **Consequence:** A censored reference search is represented explicitly by a
  missing reference tail probability rather than an invented value.

### Correction 3 — Freeze a greedy-failure regression fixture

- **Decision:** Keep a deterministic 12-by-4 fixture whose greedy result uses
  four deletions while bounded exhaustive search finds an exact minimum of
  three.
- **Rationale:** The fixture makes the distinction between a greedy upper bound
  and a certified minimum executable and prevents a regression toward treating
  greedy search as exact.
- **Consequence:** The greedy/exhaustive distinction is permanently covered by
  regression tests.

### Correction 4 — Align exact LOO with estimator sample validation

- **Decision:** Require at least four rows before exact LOO influence is run,
  because each deletion leaves one fewer row and the estimator requires at
  least three.
- **Rationale:** The public validation rule should fail before the first
  deletion rather than producing an inconsistent per-refit error.
- **Consequence:** Small samples receive one predictable, explicit error.

### Correction 5 — Make mixture truth metadata describe the mixture

- **Decision:** Mixture simulation metadata reports the mixture-weighted
  covariance, precision, and partial-correlation truth; subgroup labels remain
  available separately for contamination diagnostics.
- **Rationale:** Reporting the base subgroup truth as the truth for a mixed
  sample is potentially misleading.
- **Consequence:** The reported truth corresponds to the population generating
  the simulated mixture while retaining subgroup provenance.

### Correction 6 — Learn incremental AUC scores instead of equal-weighting them

- **Decision:** Fit least-squares linear-probability scores using learned
  coefficients for the full and reduced models, then compute the incremental
  AUC from those scores.
- **Rationale:** An equal-weight sum of edge features is arbitrary and does not
  represent a fitted incremental model.
- **Consequence:** The metric is an in-sample benchmark and must not be
  described as out-of-sample predictive performance.

### Correction 7 — Redraw degenerate bootstrap samples

- **Decision:** Reject bootstrap resamples with zero sample standard deviation
  in any variable, redraw until the requested number of valid fits is reached,
  record `rejected_resamples`, and fail clearly after a bounded number of
  attempts.
- **Rationale:** A degenerate resample can invalidate correlation and shrinkage
  fitting. Returning fewer draws or allowing an opaque downstream failure would
  make uncertainty summaries incomplete.
- **Consequence:** `n_boot` counts successful nondegenerate draws, and the
  rejection count is available for audit.

### Correction 8 — Make comparator runs reproducible

- **Decision:** Commit comparator environment pins in `simulations/comparators/renv.lock`,
  accept explicit seeds in both R scripts, write the selected seed to their
  neutral outputs, and retain `sessionInfo()` artifacts.
- **Rationale:** Runtime version checks alone do not identify the environment or
  random stream used for a comparator result.
- **Consequence:** Comparator reruns have explicit environment, seed, and
  session metadata; the lockfile still requires restoration in a networked R
  environment before execution.

## ADR-011 — Bound falsification-pilot certification and record timing

- **Date:** 2026-09-11
- **Decision:** Run the falsification pilot with `search_cap=2` and a
  certification combination budget of `1000`. Record per-row elapsed seconds
  plus aggregate per-scenario elapsed seconds and row counts in simulation
  metadata.
- **Rationale:** The initial reduced pilot remained dominated by exact
  certification at the largest sample sizes. A two-deletion greedy bound and
  bounded certification budget keep the pilot finite while preserving an
  auditable distinction between reached, certified, and censored results.
  Timing evidence makes future optimization decisions measurable rather than
  speculative.
- **Consequences:** Pilot rows that require a larger exact certification are
  represented as uncertified/censored and their summary metrics remain
  explicitly null where appropriate. The estimator and fragility algorithms
  are unchanged; the pilot configuration is the practical pre-optimization
  limit.
- **Status:** Implemented in `simulations/configs/falsification_pilot.json`,
  `simulations/run_simulation.py`, and `tools/validate_smoke.py`.
