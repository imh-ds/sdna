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

### Correction 9 — Treat unreached reference searches as right-censored

- **Decision:** When the observed fragility search reaches, retain unreached
  reference searches in the empirical tail-probability denominator and treat
  their counts as greater than any finite reached count. Keep the strict
  `require_reached=True` validation behavior for callers that require every
  search to reach.
- **Rationale:** An unreached reference search contains information: it did not
  reach the target within the same bounded search region. Dropping the whole
  calibration row discards that information and makes reference-tail
  availability depend on every reference draw reaching.
- **Consequence:** With `require_reached=False`, a finite observed count yields
  a tail probability even when some reference counts are censored; a missing
  observed count still yields `None`. The evidence report must distinguish
  observed reach from the reference-reach fraction.

### Correction 10 — Scope CI type checking and expand lint coverage

- **Decision:** Run Ruff across `src`, `tests`, `simulations`, `benchmarks`, and
  `tools`, while keeping strict mypy CI scoped to the distributable
  `src/sdna` package.
- **Rationale:** Ruff is clean across all five areas. Strict mypy currently
  reports known typing errors in the experimental simulation and validation
  harnesses, whose dynamically shaped records are not yet a stable package
  type contract. Failing CI on those known harness errors would obscure the
  clean package gate; omitting their lint coverage would leave a broader gap.
- **Consequence:** Harness code is CI-checked by Ruff and tests, while a
  separate typing-cleanup task is required before those directories can join
  the strict mypy gate. The scope is documented in
  `docs/development/ci_scope.md`.

### Correction 11 — Keep the Wald comparator intentionally ordinary-partial

- **Decision:** Keep `wald_partial_correlation` as an ordinary-partial,
  full-sample benchmark that re-estimates shrinkage through
  `fit_network(data)`. Do not add a fixed-shrinkage argument solely for API
  symmetry with the SDNA deletion and calibration routines.
- **Rationale:** The comparator is intended to provide ordinary uncertainty
  context, not to claim the fixed-shrinkage deletion estimand. Adding an
  unused parameter would imply comparability that the current Wald-like
  standard-error approximation does not provide.
- **Consequence:** Wald intervals and `z` statistics must be labeled as
  ordinary-partial benchmark outputs. Any future fixed-lambda Wald resampling
  requires a separate API and validation design.

### Correction 12 — Make matched simulation cells unambiguous

- **Decision:** Persist an ordinal `parameter_id` for every simulation job and
  include it with `N`, `p`, and replication in the cross-scenario contrast key.
  Treat parameter slots as aligned only when the caller configures them in the
  same order across the scenarios being contrasted.
- **Rationale:** Matching only on `N`, `p`, and replication silently makes
  multi-valued clean or contamination settings ambiguous and drops those rows
  from the contrast. An explicit parameter slot preserves one-to-one matching
  and makes the population feeding each contrast auditable.
- **Consequence:** Contrast reports now expose an unambiguous cell identity.
  Different parameter values are not inferred to be matched unless their
  parameter slots are deliberately aligned.

### Correction 13 — Record benchmark provenance in JSON artifacts

- **Decision:** Benchmark writers emit a metadata envelope containing the
  benchmark name, git commit, package/Python/NumPy versions, and the matrix
  settings used to generate the rows.
- **Rationale:** Timing results without environment and configuration metadata
  cannot be reliably reproduced or audited.
- **Consequence:** Benchmark JSON retains the row data while also recording
  the execution context and requested benchmark settings.

### Correction 14 — Invoke the smoke validator as a repository module

- **Decision:** The GitHub Actions smoke workflow invokes
  `python -m tools.validate_smoke` rather than executing the validator by file
  path.
- **Rationale:** Executing `tools/validate_smoke.py` directly places `tools/`
  ahead of the repository root on `sys.path`, so its import of the sibling
  `simulations` package fails in CI.
- **Consequence:** The smoke validator uses the same repository-root module
  resolution as the simulation runner and can import `simulations` after the
  editable package installation.

### Correction 15 — Reject ambiguous legacy contrast configurations

- **Decision:** Reject legacy configurations without an explicit `scenarios`
  list when they combine clean rows with more than one positive contamination
  count. Require the explicit scenario configuration for those multi-valued
  contrasts.
- **Rationale:** The legacy job layout does not repeat clean rows for each
  contamination condition, so multiple positive counts cannot be assigned a
  one-to-one matched cell without inventing a pairing rule. Raising an error is
  safer than silently dropping ambiguous contrast rows.
- **Consequence:** Existing single-contamination legacy runs remain supported.
  Multi-valued legacy contrast runs must use explicit scenario lists and their
  aligned parameter slots.

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

## ADR-012 — Keep reduced validation evidence outside the PR gate

- **Date:** 2026-09-13
- **Decision:** Add a committed fixed-seed reduced validation configuration
  covering all six simulation scenarios across `N=[50, 100]`, `p=[5, 10]`, and
  two replications per cell. Run it through a manually dispatchable GitHub
  Actions workflow, and retain the configuration, run provenance, results, and
  summaries as a 30-day artifact.
- **Rationale:** A broader scenario matrix provides recurring evidence that the
  complete simulation and summary workflow remains executable when explicitly
  invoked, while keeping the pull-request gate small and responsive. A
  committed configuration and fixed seed make changes in output attributable to
  code or environment rather than an unrecorded workload choice.
- **Consequence:** The workflow is a reproducibility and workflow check, not a
  publication-level validation run or a required PR status check. Larger or
  more inferentially complete matrices remain explicitly invoked research
  runs, with their own documented configuration and interpretation limits.
- **Status:** Implemented in
  `simulations/configs/validation_matrix.json` and
  `.github/workflows/validation-matrix.yml`.

## ADR-013 — Freeze the v0.1 primary validation matrix before execution

- **Date:** 2026-09-13
- **Decision:** Treat `simulations/configs/falsification_pilot.json` as the
  pre-specified v0.1 primary matrix: six scenarios, `N=[50, 100, 150]`,
  `p=[5, 10, 20]`, ten replications per cell, calibration simulations `25`,
  bootstrap draws `100`, `search_cap=2`, certification budget `1000`, and
  fixed root seed `20260910`. Document its estimands, censoring rules, matched
  populations, technical acceptance checks, and interpretation boundaries in
  `docs/methodology/validation_matrix_v1.md`.
- **Rationale:** The reduced Actions matrix verifies execution and artifact
  provenance but is too small to serve as the primary methodological evidence.
  Freezing the larger bounded pilot before its next execution prevents
  post-hoc selection of cells, metrics, or reach handling while preserving the
  practical runtime limits established by Task 19.
- **Consequence:** The primary run remains bounded methodological evidence,
  not publication-level validation. Reach-dependent censoring, null metrics,
  and matched-cell populations must be reported explicitly. Any change to the
  matrix or interpretation rules requires a new specification version and a
  new decision-log entry.
- **Status:** Specification committed; primary matrix execution remains the
  next separate validation action.

## ADR-014 — Validate primary runs under an explicit profile

- **Date:** 2026-09-13
- **Decision:** Add a `primary` profile to the simulation artifact validator.
  The existing `validate_smoke` function remains the compatibility wrapper for
  smoke runs, while the manually invoked primary-validation workflow validates
  the full configured replication count and requires `metadata.smoke=False`.
- **Rationale:** The smoke validator intentionally caps expected replications at
  five and requires smoke metadata. Reusing it unchanged for the 10-replication
  primary matrix could either reject a valid primary artifact or encourage an
  unsafe smoke-capped acceptance check. An explicit profile makes the workload
  and provenance contract visible at the command boundary.
- **Consequence:** PR/reduced runs and primary runs share schema and invariant
  checks but cannot be confused by their replication or metadata expectations.
  The primary workflow remains manual-only and uploads its validated evidence
  separately.
- **Status:** Implemented in `tools/validate_smoke.py` and
  `.github/workflows/primary-validation.yml`.

## ADR-015 — Execute the pre-specified primary matrix without tuning

- **Date:** 2026-09-13
- **Decision:** Execute the frozen `falsification_pilot.json` matrix with the
  `primary` validation profile before considering any estimator optimization or
  matrix revision. The local run produced 540 rows, completed in approximately
  55.3 seconds, and passed the profile-aware schema, provenance, and summary
  invariants.
- **Rationale:** The pre-specification is only useful if the declared workload
  can be executed and audited under its full replication count. Running it
  before tuning preserves a baseline against which future changes can be
  compared.
- **Consequence:** The run confirms executable bounded evidence, not favorable
  operating characteristics or publication-level validity. Reach-dependent
  censoring, undefined metrics, and scenario-specific limitations remain part
  of the interpretation. The same primary run is available through the manual
  GitHub Actions workflow after it is merged.
- **Status:** Local primary execution completed; hosted workflow is available
  for explicit dispatch.

## ADR-016 — Treat low reach as a declared v0.1 boundary pending redesign

- **Date:** 2026-09-13
- **Decision:** Retain all six scenario families in the v0.1 primary evidence,
  including `heavy_tails` and `collinearity_stress`, but interpret their
  unreached rows as censored and report their finite denominators explicitly.
  Do not increase the search cap, retune the estimator, or optimize numerical
  routines in response to the primary result without a new pre-specified
  study.
- **Rationale:** The hosted 540-row run passed the complete simulation and
  artifact-validation workflow, while reach varied materially by scenario:
  `heavy_tails` reached 19/90 and `collinearity_stress` reached 0/90. This is
  evidence of a practical availability boundary, not evidence that the
  corresponding finite-case estimands are uniformly valid or that the runner
  failed. Removing low-reach scenarios or post-hoc widening the search cap
  would confound availability and method behavior.
- **Consequences:** v0.1 claims are restricted to reached/certified rows and
  the displayed pooled or jointly valid denominators. The collinearity stress
  scenario supplies no finite fragility evidence in the primary run. A future
  reach-improvement or scope-narrowing proposal requires a separate target,
  baseline comparison, and validation specification.
- **Status:** Recorded in
  [`falsification_pilot_evidence_v2.md`](falsification_pilot_evidence_v2.md);
  redesign deferred.

## ADR-017 — Pre-specify a reach-boundary study before optimization

- **Date:** 2026-09-13
- **Decision:** Evaluate the v0.1 reach limitation with a separate, manual,
  reach-only study before changing the estimator, search cap, or numerical
  implementation. Freeze the seven arms in
  [`reach_boundary_study_v1.md`](../methodology/reach_boundary_study_v1.md):
  the cap-2 baseline, cap-3 and cap-4 sensitivity arms, a 70% target
  sensitivity arm, and declared heavy-tail/collinearity severity arms.
- **Rationale:** The primary evidence establishes outcome-dependent censoring
  but cannot distinguish search-cap limitation from target difficulty or
  numerical stress. Paired cap arms on the same simulated data and explicit
  DGP severity arms provide that decomposition without retroactively changing
  the frozen v0.1 estimand or selecting favorable cells.
- **Consequences:** The next implementation adds a separate reach-boundary
  artifact and transition summary. It must report numerical failures separately
  from unreached searches, use the same primary row keys and seeds for paired
  cap comparisons, and avoid calibration/bootstrap/AUC claims. No arm is
  promoted automatically; any changed v0.1 workflow requires a new validation
  specification and decision entry.
- **Status:** Specification committed; execution and any redesign decision are
  deferred to the next task.

## ADR-018 — Keep the reach-boundary diagnostic manual-only and retain cap 2 pending hosted confirmation

- **Date:** 2026-09-13
- **Decision:** Add a manual-only GitHub Actions workflow for the complete
  2,430-row reach-boundary study, with 90-day artifact retention and strict
  manifest/provenance validation. Retain `search_cap=2` as the v0.1 primary
  workflow pending hosted confirmation; do not promote cap 3, cap 4, the 70%
  target, or a stress-arm change from this diagnostic rehearsal.
- **Rationale:** The local execution passed all technical acceptance checks and
  showed paired cap sensitivity, but it was run under Python 3.12 rather than
  the workflow's required Python 3.11 environment. A manually dispatched,
  artifact-uploading workflow provides the reproducible hosted record without
  adding a recurring job or changing the primary matrix. The observed reach
  differences are useful for designing a future cap-expansion study, but do
  not establish a new full-workflow runtime or certification budget.
- **Consequences:** The reach-boundary workflow is not a pull-request gate and
  is not scheduled weekly. The evidence report distinguishes local rehearsal
  from the pending hosted run and keeps errors, censoring, and reached greedy
  results as separate states. Any production cap change requires a new
  pre-specified validation task and comparison against the frozen cap-2
  baseline.
- **Status:** Workflow and local evidence report committed; hosted dispatch and
  final hosted evidence update remain the next repository-level action.

## ADR-019 — Accept the hosted reach-boundary artifact as the v0.1 boundary record

- **Date:** 2026-09-13
- **Decision:** Accept hosted run
  [`34784346096`](https://github.com/imh-ds/sdna/actions/runs/34784346096)
  on commit `d32f5478b1eb943f93357515cba0fa5cb78ccd1e` as the technical
  reach-boundary evidence record. Retain cap 2 as the v0.1 primary workflow;
  treat cap 3, cap 4, the 70% target, and the stress arms as diagnostic
  sensitivity results only.
- **Rationale:** The hosted Python 3.11 run produced all 2,430 declared rows,
  passed manifest/provenance/schema validation, had zero numerical errors, and
  reproduced the local rehearsal's row keys, seeds, statuses, and reach
  values. Cap 3 and cap 4 newly reached 36 and 63 paired rows, respectively,
  while the collinearity arms reached none. This separates an observed
  cap-sensitive availability boundary from a justification to alter the
  primary estimand.
- **Consequences:** The complete hosted artifact and paired transition tables
  are now the baseline for any future cap-expansion proposal. No estimator,
  cap, target, or regularization change is authorized by this result alone.
  The report records a non-blocking GitHub warning that the v4 Actions used in
  the workflow target Node.js 20 and were forced onto Node.js 24; this is a
  maintenance item, not a failed validation result.
- **Status:** Hosted evidence accepted; redesign or scope change deferred to a
  separately pre-specified methodological task.

## ADR-020 — Pin CI tooling and update Actions runtimes

- **Date:** 2026-09-13
- **Decision:** Pin the CI development-tool versions in
  [`constraints-ci.txt`](../../constraints-ci.txt), provide an optional Ruff
  pre-commit hook, and update all repository workflows to the current
  Node.js-24-native releases of checkout, setup-python, and upload-artifact.
- **Rationale:** The hosted workflows correctly caught lint defects, but those
  defects reached CI because no local hook mirrored the repository-wide Ruff
  gate. Floating CI tools also allow the quality gate to change without a
  repository commit. GitHub reported a non-blocking warning that the prior
  Actions versions targeted Node.js 20 and were being forced onto Node.js 24.
- **Consequence:** Direct CI quality-tool versions remain fixed until the
  constraints are intentionally updated; runtime and transitive dependencies
  remain resolver-controlled rather than being represented as fully locked.
  Contributors have an opt-in local Ruff check, and the Actions workflows no
  longer rely on the deprecated Node.js 20 runtime. This is CI maintenance
  only; it does not change the estimator, simulation matrix, or methodological
  claims.
- **Status:** Implemented in the CI constraints, pre-commit configuration, and
  workflow files.

## ADR-021 — Make the local Ruff hook match the CI scope

- **Date:** 2026-09-13
- **Decision:** Configure the optional pre-commit Ruff hook to run with
  `pass_filenames: false`, `always_run: true`, and the same `src`, `tests`,
  `simulations`, `benchmarks`, and `tools` paths used by the CI workflow.
- **Rationale:** A default pre-commit hook checks only staged Python files and
  therefore cannot catch an existing lint regression elsewhere in the
  repository. The hook is intended as a local mirror of the CI Ruff gate, not
  merely as a changed-file convenience.
- **Consequence:** Every commit performs the repository-wide Ruff check. The
  direct-tool constraints remain intentionally narrower than a complete
  dependency lockfile, and that limitation is documented rather than hidden.
- **Status:** Implemented in `.pre-commit-config.yaml` and the CI scope
  documentation.

## ADR-022 — Pre-specify a paired full-workflow search-cap expansion study

- **Date:** 2026-09-14
- **Decision:** Specify a three-arm, full-workflow comparison of
  `search_cap=2`, `search_cap=3`, and `search_cap=4` using the frozen v0.1
  matrix, identical generated data and row seeds across arms, and 25
  calibration simulations, 100 bootstrap resamples, and certification budget
  1000 per row. The study contains 540 rows per arm (1,620 total) and runs
  only through a manual workflow. Cap 2 remains the production baseline, and
  no arm is promoted automatically.
- **Rationale:** The hosted reach-boundary diagnostic found paired availability
  gains for caps 3 and 4 but intentionally made no full-workflow claims. A
  complete paired study is needed to determine whether those gains persist
  through calibration, certification, bootstrap, comparator behavior, and
  practical runtime while preserving the frozen v0.1 estimand. The design
  therefore fixes the data and randomization contract, separates pooled from
  jointly-valid pair metrics, preserves explicit censoring/failure states, and
  sets a 15-minute hosted operational ceiling without treating it as a
  scientific threshold.
- **Consequences:** The next implementation must add a validated paired
  artifact and evidence report under the approved specification. A result can
  support a later cap decision but cannot alter v0.1, add undeclared arms, or
  introduce optimization. Any production-cap change requires a subsequent
  decision entry.
- **Status:** Design specified and committed; user approval received; detailed
  implementation plan is committed separately; implementation and hosted
  execution remain pending.
- **Decision introduced in commit:** `bb7a851`
- **Design/specification:**
  [`docs/superpowers/specs/2026-09-14-task24-cap-expansion-design.md`](../superpowers/specs/2026-09-14-task24-cap-expansion-design.md)
- **Implementation plan:**
  [`docs/superpowers/plans/2026-09-14-task24-cap-expansion.md`](../superpowers/plans/2026-09-14-task24-cap-expansion.md)
- **Canonical methodology page:**
  [`docs/methodology/cap_expansion_study_v1.md`](../methodology/cap_expansion_study_v1.md)
- **Independent-review files:**
  `simulations/configs/cap_expansion_v1.json`,
  `tools/cap_expansion_manifest.py`, `simulations/full_workflow.py`,
  `tools/run_cap_expansion.py`, `tools/summarize_cap_expansion.py`,
  `.github/workflows/cap-expansion.yml`, and
  `docs/methodology/cap_expansion_study_v1.md`.
- **Review rationale:** The hosted reach-only diagnostic found paired cap
  sensitivity but did not establish calibration, certification, bootstrap, or
  practical-runtime behavior. The planned full-workflow comparison preserves
  the frozen v0.1 estimand while testing whether the availability gains persist
  under the complete workflow. After implementation and hosted execution, a
  follow-up decision record must add the exact implementation commit, Actions
  run ID, artifact checksum, findings, and cap decision.

## ADR-023 — Complete the paired cap-expansion implementation and retain cap 2 pending hosted execution

- **Date:** 2026-09-14
- **Decision:** Complete the Task 24 paired full-workflow implementation at
  commit `de02a257ff2acd958b354397711ba6e4fd6270e9`. Retain
  `search_cap=2` as the v0.1 production baseline. Treat cap 3 and cap 4 as
  diagnostic sensitivity arms; do not promote either arm automatically or
  change the v0.1 estimand from this run.
- **Why this happened:** The prior reach-boundary diagnostic showed that
  larger search caps can recover otherwise unreached rows, but it did not test
  downstream calibration, certification, comparator, bootstrap, or runtime
  behavior. Task 24 therefore froze a paired, same-data three-arm study before
  any optimization or production-cap change. A final seed-contract correction
  was included in the implementation commit because the loader previously
  accepted any nonnegative seed even though the study seed was frozen.
- **Local evidence provenance:** The complete 1,620-row study was run from
  commit `de02a257ff2acd958b354397711ba6e4fd6270e9` with Python 3.12.1 and
  NumPy 2.5.2. The results CSV SHA-256 was
  `64a4362440f52e34a5da2275c30a1f017d5e8c4b80cc52aa62ae867bb5e83810` and
  the frozen manifest checksum was
  `415576f1fec5ccd2a47e0ad411d29e4d48c6e8e370609ae495ccc877fe74e974`.
  The run produced 540 rows per arm in 564.23 seconds, below the 900-second
  operational budget. All 1,620 Wald and bootstrap stages completed without
  error; the 656 unreached rows are represented as partial workflow states,
  not as numerical failures.
- **Findings:** The cap-3 comparison had 284 reached-to-reached pairs, 44
  unreached-to-reached pairs, and 212 unreached-to-unreached pairs, with no
  reached-to-unreached pairs. Its paired reach-rate difference was 0.0815
  (95% normal interval 0.0584 to 0.1046; denominator 540). Cap 4 had 284
  reached-to-reached pairs, 68 unreached-to-reached pairs, and 188
  unreached-to-unreached pairs, again with no reached-to-unreached pairs. Its
  paired reach-rate difference was 0.1259 (95% normal interval 0.0979 to
  0.1539; denominator 540). Baseline cap 2 certified 284 rows; cap 3 and cap
  4 also certified 284 rows, while their newly reached rows were
  `not_certified` (44 and 68 respectively). The cap expansion therefore
  improved availability in this artifact without demonstrating additional
  certified evidence sufficient to justify a production change.
- **Hosted status:** The manual workflow is committed in
  `.github/workflows/cap-expansion.yml` and the branch is pushed as
  `codex/task-24-cap-expansion`. No GitHub Actions run ID or hosted artifact
  checksum exists yet: dispatch was attempted against this branch and GitHub
  returned HTTP 404 because the workflow is not present on the repository's
  default branch. After a reviewed merge makes the workflow available on the
  default branch, dispatch the workflow and append its exact run ID, commit,
  artifact name, checksum, and any local/hosted reproducibility comparison to
  this ADR.
- **Files for independent review:**
  `docs/superpowers/specs/2026-09-14-task24-cap-expansion-design.md`,
  `docs/superpowers/plans/2026-09-14-task24-cap-expansion.md`,
  `simulations/configs/cap_expansion_v1.json`,
  `tools/cap_expansion_manifest.py`, `simulations/full_workflow.py`,
  `tools/run_cap_expansion.py`, `tools/summarize_cap_expansion.py`,
  `tests/test_cap_expansion_manifest.py`,
  `tests/test_full_workflow.py`, `tests/test_cap_expansion_runner.py`,
  `tests/test_cap_expansion_summary.py`,
  `.github/workflows/cap-expansion.yml`, and
  `docs/methodology/cap_expansion_study_v1.md`.
- **Consequences:** The cap-expansion artifact is technically validated and
  supports a clear availability finding, but the methodology page remains
  pre-specified rather than upgraded to accepted hosted evidence. The next
  repository-level action is a reviewed PR merge followed by manual hosted
  execution; only a later, separately approved validation task may change the
  production cap or introduce optimization.
- **Review-correction provenance:** The first PR #13 matrix run,
  `34868854989`, failed only its Python 3.11/3.12/3.13 Ruff lint jobs on
  commit `875f03c`; the fixed-seed smoke test passed. The root cause was eight
  import-order/unused-import violations in
  `simulations/full_workflow.py`, `simulations/run_simulation.py`,
  `tools/run_cap_expansion.py`, and the three new cap-expansion test modules.
  The independent review also identified semantic-status, summary-integrity,
  deterministic-seed, checksum, right-censoring-label, runtime-reporting,
  and influence-error-state gaps. These were corrected in commit
  `c0aef22325fc500124898ddd7349a688df54ab9d`, with regression coverage in
  `tests/test_cap_expansion_summary.py` and
  `tests/test_full_workflow.py`. The reviewer-confirmed limitation that the
  CSV cannot independently prove digest content without retaining generated
  matrices is explicit: validation checks lowercase SHA-256 format and paired
  equality, while `tools/run_cap_expansion.py` computes the digest from the
  generated dataset.

### ADR-023 follow-up — Hosted cap-expansion confirmation and cross-runtime validator correction

- **Date:** 2026-09-14
- **Hosted execution:** The reviewed Task 24 merge landed as commit
  `338b0d95cdb312b2805affb0de458e06508d80f0`. Manual GitHub Actions run
  [`34871220664`](https://github.com/imh-ds/sdna/actions/runs/34871220664)
  completed successfully on that commit using Python 3.11.16. The uploaded
  artifact is `sdna-cap-expansion-34871220664`.
- **Hosted artifact checksums:** `results.csv` is
  `110d0b4f266b253251ac1a64bb4195b61722008d426b74c75802d3de57b43d87`,
  `summary.json` is
  `6695edf0cabcf02dc9f74b541302b4134266ad8f6eeaa80f8a2e4c2c63c3a717`, and
  `summary.md` is
  `faefe202925f2ad2594c963d8517cb0cf446c47fd223f75f4e0d17f03b5bcee1`.
- **Hosted evidence:** The run produced 1,620 rows (540 per arm), completed
  in 370.44 seconds under the 900-second ceiling, and reported no budget
  exceedance. Fragility statuses were 964 reached and 656 unreached;
  certification statuses were 852 certified, 112 not certified, and 656
  skipped as unreached; calibration statuses were 462 finite, 502
  right-censored, and 656 observed-unreached; Wald and bootstrap completed for
  all 1,620 rows. Relative to cap 2, cap 3 had 284 reached-to-reached, 44
  unreached-to-reached, 212 unreached-to-unreached, and 0 reached-to-unreached
  pairs; cap 4 had 284, 68, 188, and 0 respectively. The 44 and 68 newly
  reached rows were not certified, so cap 2 remains the v0.1 production
  baseline and caps 3/4 remain diagnostic sensitivity arms.
- **Cross-runtime correction:** Revalidating the downloaded hosted artifact
  under Python 3.12 initially exposed exact-JSON comparison failures at about
  `1e-16` in floating-point summary values, despite identical rows, seeds,
  checksums, statuses, and scientific calculations. Commit
  `785761a` (`fix: tolerate cross-runtime summary rounding`) changed
  `tools/summarize_cap_expansion.py` to require identical summary structure and
  keys while comparing numeric leaves with a tight `1e-12` tolerance. The
  regression test in `tests/test_cap_expansion_summary.py` proves that this
  narrow runtime-rounding tolerance is accepted; checksum, semantic-status,
  deterministic-seed, and substantive summary-tampering checks remain strict.
  The hosted artifact then passed local revalidation under Python 3.12.1.
- **Interpretation:** The correction changes validator portability only; it does
  not alter the hosted results or cap decision. Investigators should inspect
  `tools/summarize_cap_expansion.py`,
  `tests/test_cap_expansion_summary.py`, the hosted workflow, and the artifact
  checksums above when reproducing this record.

## ADR-024 — Pre-specify a certification-usability audit before considering cap promotion

- **Date:** 2026-09-14
- **Decision:** Approve Task 25 as a diagnostic certification-usability study.
  Begin with a read-only audit of the accepted Task 24 artifact, defining the
  exact matched populations that were unreached at cap 2 and reached at cap 3
  or cap 4. Run a separate instrumented paired rerun only when the existing
  artifact cannot identify the certification bottleneck. Retain cap 2 as the
  v0.1 production baseline throughout.
- **Why this happened:** Task 24 demonstrated additional reach at caps 3 and
  4, but its 44 cap-3 and 68 cap-4 newly reached rows were not certified. The
  existing CSV records `not_certified` but does not record certification
  combinations checked, budget exhaustion, or a dedicated failure reason.
  More reached rows therefore cannot yet be treated as more usable evidence.
- **Primary endpoint:** For each candidate cap `c` in `{3, 4}`, report
  certification yield among the complete matched population
  `U_to_R(c) = {baseline_cap2 unreached, cap-c reached}`. The denominator
  includes downstream failures and is reported with exact row identities; no
  missing or invalid result is converted to zero.
- **Protocol constraints:** The conditional rerun must preserve the Task 24
  matrix, data and child seeds, estimator, target `0.5`, certification budget
  `1000`, calibration/tail treatment, Wald comparator, bootstrap procedure,
  and 900-second ceiling. It may add only certification diagnostics. No cap
  promotion, optimization, workload increase, unregistered threshold, or
  independent pooling of audit and rerun results is authorized by this ADR.
- **Design provenance:** The approved design was introduced in
  `9c9d467748bfdc6636a59dc04af1f30e491c9565` and clarified for prior-stage
  errors in `e2e8223f8fd9d076865ebfab26875fde933b9aa0`. The implementation plan
  was introduced in
  `7d0c1888486b86b6b89d79053d503d621d1957d5`.
- **Files for independent review:**
  `docs/superpowers/specs/2026-09-14-task25-certification-usability-audit-design.md`,
  `docs/superpowers/plans/2026-09-14-task25-certification-usability-audit.md`,
  `docs/methodology/cap_expansion_study_v1.md`,
  `tools/run_cap_expansion.py`, `simulations/full_workflow.py`,
  `tools/summarize_cap_expansion.py`, and
  `docs/development/decisions.md`.
- **Status:** Design and implementation plan committed; implementation,
  hosted execution, and any resulting mechanism decision remain pending.

### ADR-024 implementation contract — Task 6

- **Date:** 2026-09-14
- **Decision:** Implement the approved certification-usability audit as a
  manual-only workflow. The workflow first validates and audits the accepted
  Task 24 artifact, then runs the frozen 1,620-row matrix with certification
  diagnostics, validates reproduction against the reference, and uploads the
  complete evidence bundle with 90-day retention.
- **Why this happened:** Phase A needs a stable, reviewable source artifact,
  while Phase B needs a reproducible execution path for the certification
  diagnostics that Task 24 did not record. A manual trigger keeps this
  diagnostic study out of routine pull-request gates and avoids implying that
  a recurring weekly run is a scientific requirement.
- **Files for independent review:**
  `docs/methodology/certification_usability_study_v1.md`,
  `.github/workflows/certification-usability.yml`,
  `tools/audit_certification_usability.py`,
  `tools/run_certification_usability.py`,
  `tools/summarize_certification_usability.py`, and
  `simulations/configs/certification_usability_v1.json`.
- **Implementation commit:** `c6a4f53` (`ci: specify certification usability
  validation workflow`).
- **Status:** The Task 6 workflow and methodology contract are implemented;
  hosted execution and the resulting mechanism decision remain pending. The
  Task 6 contract is ready for the hosted execution gate.

### ADR-024 pre-hosted validation — Task 7

- **Date:** 2026-09-14
- **Implementation tip:** `0d1e46e` (`test: align audit regression with
  validator imports`). The Task 6 workflow contract and provenance are in
  `c6a4f53` and `3a320e8`; the pre-hosted integration corrections are
  `0d06534` (Phase A source-manifest path), `e7730c1` (Phase B source-manifest
  path), and `e83cd93` (serialized certification-budget flag parsing).
- **Local verification:** The complete local suite passed with 168 tests;
  Ruff and Python compilation passed. The accepted Task 24 source artifact
  passed its production validator, and the synthetic Phase A/Phase B helper
  rehearsal passed the deliberate tamper-rejection checks.
- **Local instrumented replay:** A full 1,620-row replay completed in
  584.885 seconds under the 900-second ceiling, with 540 rows per arm,
  `U_to_R(3)=44`, `U_to_R(4)=68`, zero certified rows in both populations,
  and all 44/68 rows classified as `combination_budget_exhausted`. Its
  outputs are retained outside Git under `.task25-artifacts/` with results
  SHA-256 `e225483b71fe2101f358329142bd3ab83560245073d083e2fb8842ae10fce9c1`,
  summary SHA-256
  `fa709b92f1bcdfacaadedeb396ac36b7dc9dfe2d4f3a6bef57450af1e7ea2dcc`, and
  Markdown SHA-256
  `c4ebc50720be4f8c91b789f257c6747fe178cb7c047729ddf5b4be6ed2618da4`.
- **Local replay limitation:** The local replay used Python 3.12.1 and
  NumPy 2.5.2, while the accepted Task 24 artifact used Python 3.11.16 and
  NumPy 2.4.6. The strict reproduction check therefore rejected the local
  replay: 270 dataset digests and two `reference_reached_fraction` values
  differed, although row counts, arm balance, pairing keys, seeds, statuses,
  and the `U_to_R` populations matched. This is not accepted as Phase B
  evidence; the manual workflow’s Python 3.11 environment must complete the
  strict reference comparison before hosted evidence is accepted.
- **Interpretation:** The validator correctly refuses to convert a
  cross-runtime numerical difference into a passing reproduction. No cap
  promotion or protocol change follows from the local replay. Hosted run ID,
  artifact checksums, and the resulting mechanism decision remain pending.

### ADR-024 hosted evidence — Task 7

- **Date:** 2026-09-14
- **Hosted execution:** After PR #16 merged as `fcf7251`, the workflow-context
  correction in PR #18 merged as `7b22b3fca39888e1a452cb5a7ad8ec244ccd752e`.
  The manual-only workflow then completed successfully as Actions run
  [`34895397606`](https://github.com/imh-ds/sdna/actions/runs/34895397606),
  using Python 3.11.16 and NumPy 2.4.6. The artifact is
  `sdna-certification-usability-34895397606`.
- **Hosted validation:** Phase A downloaded and validated the accepted Task
  24 artifact, and Phase B produced 1,620 rows (540 per arm). Strict
  reference reproduction, diagnostic semantics, metadata, summary, and
  artifact checks all passed. Runtime was 311.334860969 seconds under the
  900-second ceiling; `budget_exceeded` was false.
- **Hosted checksums:** `results.csv` is
  `4ec0068d8fe2b2b62df45fccbbf71f884c50589e319e48c3a2400111ae051918`,
  `summary.json` is
  `139a803c804e5382515a64b62f4fc764b90b6e0e568f7f579e2b651b0f3af1f6`,
  `summary.md` is
  `e61a141a7775482c5e43f79126f3a1be4aebf8eb52db264a7c9f673f91dc2975`,
  `phase-a-audit.json` is
  `6c8a35ee9d625214b2b3acc69f343d311d4ce508f4f25345c7e60c77d5fedd17`, and
  `phase-a-audit.md` is
  `81a4307c136b07730e77448a7d6270bc0b5c56a719dd0ad0c3f46d29daa3d8f8`.
- **Hosted finding:** The exact primary populations were `U_to_R(3)=44` and
  `U_to_R(4)=68`; certification yield was `0/44` and `0/68`. Every population
  record was `not_certified` with reason `combination_budget_exhausted` and
  the exhaustion flag true. The certification routine checked 3,900
  combinations across the cap-3 population and 6,300 across the cap-4
  population before the next complete subset size exceeded the
  1,000-combination budget. No population record had a certification error or
  prior-stage error. All records had right-censored calibration, `ok` Wald,
  `ok` bootstrap, and `ok` overall workflow status.
- **Mechanism interpretation:** The diagnostic identifies certification
  search-budget exhaustion as the limiting mechanism for the newly reached
  rows; it does not establish that increasing the budget would certify them.
  The evidence is not pooled with Phase A as independent evidence, and no cap
  promotion, budget change, optimization, or threshold change is authorized.
  Cap 2 remains the v0.1 production baseline; caps 3 and 4 remain diagnostic
  sensitivity arms.
- **Files for independent review:**
  `docs/methodology/certification_usability_study_v1.md`,
  `.github/workflows/certification-usability.yml`,
  `simulations/configs/certification_usability_v1.json`,
  `tools/audit_certification_usability.py`,
  `tools/run_certification_usability.py`,
  `tools/summarize_certification_usability.py`, and the downloaded artifact
  named above.
- **Status:** Task 25’s diagnostic audit is technically complete. The
  mechanism finding is recorded without promoting a cap or changing the
  production protocol. Any follow-up budget study requires a new
  pre-specified methodological decision.

## ADR-025 — Pre-specify certification-budget sensitivity without changing production

- **Date:** 2026-09-15
- **Decision:** Run a manual-only fixed-budget study for Task 25 populations
  `U_to_R(3)=44` and `U_to_R(4)=68`, using `[1000, 5000, 10000, 20000]`.
  Cap 2 remains the unchanged production baseline. This is not a
  cap-promotion, production-budget, or optimization decision.
- **Rationale:** Task 25 observed zero certification yield in both selected
  populations, with every row classified as `combination_budget_exhausted`.
  That is diagnostically compatible with stopping at the 1,000-combination
  budget before the next complete subset size; it does not establish that
  certification is impossible at a larger budget. The exact 44/68 populations
  retain the motivating rows and their cap-specific overlap. The fixed grid
  probes pre-specified subset boundaries without choosing later budgets from
  interim results. A `timeout`, `failed`, or `incomplete` arm has no yield
  endpoint: missing rows cannot be scored as zero.
- **Protocol and interpretation limits:** Only budget changes; all Task 25/24
  data, pairing keys, datasets, seeds, estimator, target, calibration
  (`calibration_require_reached=False`), ordinary-partial Wald comparator,
  downstream procedures, and workflow behavior remain fixed. Each arm has an
  1,800-second computation ceiling. Timed-out arms retain start time, elapsed
  time, timeout ceiling, expected/completed rows, last key when available, and
  whether certification exhausted its configured budget. Row-level
  `combination_budget_exhausted` is distinct from an arm timeout. Any increase
  supports only budget sensitivity for the selected population and does not
  justify cap promotion, a production budget change, post-hoc selection, or a
  universal sufficiency claim. Cap 2 remains unchanged regardless of outcome.
- **Corrected source identities:** Task 25 is run `34895397606`, commit
  `7b22b3fca39888e1a452cb5a7ad8ec244ccd752e`, artifact
  `sdna-certification-usability-34895397606`, `results.csv` SHA-256
  `4ec0068d8fe2b2b62df45fccbbf71f884c50589e319e48c3a2400111ae051918`, and
  manifest SHA-256
  `b47842e33092b9431220204f46c77723f2465f86a1685e1cd1c90e601bedd4ff`.
  Nested Task 24 is run `34871220664`, commit
  `338b0d95cdb312b2805affb0de458e06508d80f0`, artifact
  `sdna-cap-expansion-34871220664`, `results.csv` SHA-256
  `110d0b4f266b253251ac1a64bb4195b61722008d426b74c75802d3de57b43d87`, and
  manifest SHA-256
  `415576f1fec5ccd2a47e0ad411d29e4d48c6e8e370609ae495ccc877fe74e974`.
  The latter is Task 24's checksum, not a mislabeled Task 25 checksum.
- **Design and implementation provenance:** Specification commit
  `810e57cd353426d6ebdb82f1c642088a9c75e2f6` (`docs: specify certification
  budget sensitivity study`); plan commit
  `80fbf44469656f8fa33663f2b47384d080fff238` (`docs: add certification budget
  sensitivity implementation plan`). Every implementation commit through this
  task's base is `9fb6f20f1e573025a92ebc04d869a66aa4205507` (manifest),
  `164076bea1d7e5941dc6f6c02768513aae7bdee3` (runner),
  `7e011d2a0ca1d1f38b092c10991e0b74778ef912` (runner fix),
  `7b69682f0180a72eacaf49f81e68638276b20597` (summary),
  `f5c83c2f6e478d2a61f55929ffa772976e4c5b9f` (validation fix),
  `3eff95de9bb7ce5ea2ec54b643d5bde130e47251` (minimum bound),
  `a06d34622b15978ffe54e0235e42ad87c9dbd871` (manual workflow), and
  `5d818524d6c561644a4b48bf5becaa28f925f560` (cancellation handling).
- **Hosted execution fields:** Hosted Actions run ID, dispatched commit,
  artifact names and SHA-256 checksums, runtime, per-arm statuses, yields,
  reason counts, and acceptance finding are **pending**. The workflow has not
  been dispatched; record them only after manual execution and validation.
- **Files for independent review:**
  `docs/superpowers/specs/2026-09-14-task26-certification-budget-sensitivity-design.md`,
  `docs/superpowers/plans/2026-09-14-task26-certification-budget-sensitivity.md`,
  `simulations/configs/certification_budget_sensitivity_v1.json`,
  `tools/certification_budget_sensitivity_manifest.py`,
  `tools/prepare_certification_budget_sensitivity.py`,
  `tools/run_certification_budget_sensitivity.py`,
  `tools/summarize_certification_budget_sensitivity.py`,
  `tests/test_certification_budget_sensitivity_manifest.py`,
  `tests/test_prepare_certification_budget_sensitivity.py`,
  `tests/test_certification_budget_sensitivity_runner.py`,
  `tests/test_certification_budget_sensitivity_summary.py`,
  `tests/test_certification_budget_sensitivity_workflow.py`,
  `.github/workflows/certification-budget-sensitivity.yml`,
  `docs/methodology/certification_budget_sensitivity_study_v1.md`, and
  `docs/development/decisions.md`.
- **Status:** Protocol and traceability are committed before hosted execution;
  Task 26 empirical evidence remains pending.
