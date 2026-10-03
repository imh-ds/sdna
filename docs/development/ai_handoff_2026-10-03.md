# SDNA Project Handoff — 2026-10-03

## Purpose of this handoff

This document gives an incoming AI reviewer/implementer a concise but
comprehensive map of SDNA's current methodology, implementation, evidence,
known limits, and next work. It is intended to support a focused assessment of
whether SDNA's low-sample localized diagnostics are useful for psychological
survey data—especially skewed Likert composites—without confusing a runnable
package, a technically accepted simulation, and established methodological
validity.

Treat this as a snapshot, not as a replacement for the frozen protocols or the
append-only historical record. Recheck the active branch, current Actions runs,
and any newer decision-log addenda before making changes.

## Current repository snapshot

- Repository: `imh-ds/sdna`; local checkout: `C:\Users\imhoh\GitHub\sdna`.
- Snapshot reviewed: `main` at `f48f18a52005f8a6b0ec82399f79bb231af869b8`
  (`fix: update both Task 27 artifact download steps (#25)`), tracking
  `origin/main`. That checkout was clean immediately before this handoff file
  was added; this new file is currently uncommitted.
- Package: `sdna` version `0.1.0a0`; Python `>=3.11`; NumPy-based. This is an
  experimental alpha, not a mature general-purpose network package.
- Task 27 implementation and manual GitHub Actions workflow are merged. Its
  first complete hosted run and matched rerun have both been examined, but the
  matched-rerun acceptance gate failed. The run findings below have **not yet
  been incorporated into a committed Task 27 evidence report or decision-log
  addendum** as of this snapshot.
- Do not infer current Actions status from an old run page. The local GitHub CLI
  was inaccessible in the review environment; use GitHub directly when
  resuming.

## What SDNA is intended to do

SDNA (Structured Deletion Network Analysis) is an experimental diagnostic for
asking whether a prespecified edge in an estimated partial-correlation network
is unusually sensitive to removing particular observations or small sets of
observations. Its intended interpretation is localized: investigate selected
edges/cases and use the result as a clue for follow-up. It is **not** an
automatic whole-network discovery, community-detection, causal-discovery, or
complete graph-recovery method.

The current v0.1 data boundary is complete, continuous, independent and
exchangeable observations. The code may coerce numeric 1–5 inputs to floats,
but that does not validate an ordinal/Likert analysis. Ordinal/polychoric,
missing-data, longitudinal/dependent, and causal uses are explicitly outside
the v0.1 claim boundary.

For raw Likert items, a separate ordinal-aware design and validation are needed.
Summed/averaged item composites may be approximately continuous, but can remain
bounded, skewed, or ceiling-compressed. No checked-in validation study directly
tests realistic skewed Likert composites. A ceiling pile-up is not equivalent
to the existing continuous heavy-tail scenario.

## Method and implementation map

The main analysis flow is:

1. Fit a shrinkage-regularized empirical partial-correlation network.
2. Compute exact leave-one-out (LOO) influence as the authoritative
   individual-case deletion effect; the analytic influence routine is only an
   approximation/accelerator.
3. Search greedily for deletions that attain a declared fragility target (the
   primary simulation target is 50% attenuation) within a configured cap.
   A greedy result is only a candidate/upper bound unless bounded exhaustive
   certification verifies the minimum.
4. Calibrate against a model-based simulated reference using fixed full-sample
   shrinkage. With `require_reached=False`, unreached reference searches are
   retained as right-censored contributions. The resulting reference-tail
   probability is descriptive, not a formally calibrated p-value.
5. Produce a fixed-shrinkage bootstrap comparison and an ordinary-partial Wald
   comparison. These are contextual comparators, not interchangeable estimands.
6. Report reach, censoring, certification, numerical failures, and denominators
   separately. Missing/unavailable outcomes must never be silently recoded as
   zero.

Useful implementation entry points:

- `src/sdna/estimation.py` — shrinkage network estimator and diagnostics.
- `src/sdna/influence.py` — exact LOO and analytic influence methods.
- `src/sdna/fragility.py` — greedy search and bounded exact certification.
- `src/sdna/calibration.py` — reference simulation and right-censored tails.
- `simulations/full_workflow.py` — staged end-to-end run, named RNG streams,
  and stage statuses.
- `simulations/dgp.py` — v0.1 continuous simulation families.
- `simulations/run_simulation.py`, `tools/validate_smoke.py`, and study-specific
  `tools/run_*` / `tools/summarize_*` files — simulation execution and artifact
  validation.

## Development and evidence history

The project has advanced through named Task 27. The historical decisions and
exact implementation/run provenance belong in the decision log; this section
is only a navigation summary.

| Phase | What was established | Current interpretation |
|---|---|---|
| Tasks 1–12 | Core estimator, influence/fragility/calibration contracts, scope boundaries, comparators, tests and methodology documentation. | Experimental implementation with explicit estimands and failure/censoring semantics. |
| Task 13 and follow-on work | Full falsification simulation runner and the pre-specified v0.1 validation matrix; later corrections addressed shrinkage use, complete workflow execution, regression fixtures, LOO sample validation, metadata, metrics, degenerate bootstrap, comparator reproducibility, and documentation decisions. | The matrix is bounded evidence, not universal validation or an applied-data guarantee. |
| Task 18 | CI workflows for tests and quality checks, with coverage boundaries documented. | Engineering guardrails; passing CI does not establish methodological validity. |
| Task 19 | Runtime benchmarking used to set practical simulation limits before optimization. | Workload evidence for tested settings only; no broad performance guarantee. |
| Tasks 20–23 | Reduced validation rehearsal and reach-boundary studies, followed by correction/review work. | Kept reach distinct from certification; frozen cap 2 remained the production baseline. |
| Task 24 | Paired full-workflow cap expansion (2, 3, 4) on shared data and seeds. | More search reach did not itself provide certification; caps 3/4 remain diagnostic. |
| Task 25 | Audit of cases newly reached by larger caps. | At the original 1,000-combination budget, none of the selected new cap-3 or cap-4 reaches certified. |
| Task 26 | Prespecified certification-budget sensitivity on the Task 25-selected records. | Certification yield rose with larger budgets, but this was a selected population, not fresh-sample performance or authority to change production defaults. |
| Task 27 | Frozen localized-network operating-envelope DGP, paired cap-2/cap-4 workflow, strict artifact validator, and manual three-shard Actions workflow for `p=20,40,60`. | Implementation is merged; hosted execution has a reproducibility mismatch and is not finally accepted. |

Do not use unchecked boxes in the old master plan as a task-completion count.
The named milestone history and status sources are the decision log, study
plans, merged PRs, and validated artifacts.

## What has worked, and what the checked-in evidence says

### Engineering and workflow

- The v0.1 primary matrix completed as a 540-row hosted run and passed its
  profile-aware schema, provenance, range, and summary checks. It reported no
  workflow errors and no rejected bootstrap resamples. This is technical
  acceptance for the frozen run—not a guarantee of scientific adequacy.
- CI, fixed-seed smoke tests, study-specific validators, paired-run contracts,
  and manual hosted workflows are present. The test suite has extensive unit,
  regression, artifact-tampering, and workflow-contract coverage.
- A previously recorded full local run at commit `ad19a22` reported 359 tests
  passed; later commits added numerical-range and Actions-workflow regressions.
  This handoff did not rerun the suite on `f48f18a`.
- Task 24's hosted run completed 1,620 rows. Reach rose from 280/540 (51.9%)
  at cap 2 to 316/540 (58.5%) at cap 3 and 343/540 (63.5%) at cap 4. Newly
  reached rows were not certified under the original budget; cap 2 therefore
  remains the production baseline.
- Task 26 showed higher certification counts at larger combination budgets
  for the prespecified Task 25-selected records: cap 3 rose from 0/44 at 1,000
  combinations to 44/44 at 20,000; cap 4 rose from 0/68 to 44/68. These
  conditional results are budget-sensitivity evidence only.

### v0.1 primary falsification matrix

The frozen run covered `N={50,100,150}`, `p={5,10,20}`, six continuous DGPs,
and 10 replications per scenario/cell (540 total rows). The key outcomes were:

- Reach: clean planted edge 44/90; single influential case 80/90; coalition
  contamination 71/90; mixture subgroup 66/90; heavy tails 19/90; collinearity
  stress 0/90.
- Truth-known influence recall averaged 0.567 for single influential cases,
  0.689 for coalitions, and 0.151 for mixture-subgroup contaminated cases.
- The clean reference-tail flag was 1/44 among rows with finite values. This
  is a small descriptive result, **not** a validated type-I error rate.
- Many reached-only contrasts have outcome-dependent selection and small
  denominators. AUC values were learned in-sample benchmarks, not out-of-sample
  prediction results.
- Heavy-tail and collinearity results reveal important availability limits;
  collinearity stress supplied no finite fragility results in that matrix.

The matrix used only 10 replications per cell and 25 calibration simulations
per row. Treat cell rates as diagnostic pilot estimates, not precise operating
characteristics. The primary report itself warns that low reach is not a
reason to drop cells, and that complete-case comparisons are selected.

## Task 27 hosted execution: exact current issue

### Protocol and implementation

Task 27 freezes `N={50,100,150}`, `p={20,40,60}`, five-node sparse modules,
three prespecified focal contexts (`within_community`, `hub_adjacent`,
`bridge`), three conditions (`clean`, `single_case`, `coalition`), 10
replications, and paired caps 2 and 4. It expects 810 pairing keys and 1,620
arm rows. The study is localized and prespecified; it is not whole-network
discovery. Its protocol and code live in:

- `docs/superpowers/specs/2026-10-02-task27-localized-network-operating-envelope-design.md`
- `docs/superpowers/plans/2026-10-02-task27-localized-network-operating-envelope.md`
- `simulations/configs/localized_network_v1.json`
- `simulations/localized_network_dgp.py`
- `tools/localized_network_manifest.py`
- `tools/run_localized_network.py`
- `tools/summarize_localized_network.py`
- `.github/workflows/localized-network.yml`
- Task 27 manifest, DGP, runner, summary, and workflow tests under `tests/`.

### Hosted runs reviewed

- `37070756141` and `37072478469` are failed setup/aggregate attempts caused
  by invalid GitHub artifact downloader references. Do not use their outputs
  as empirical evidence. PRs #24 and #25 corrected both references.
- Baseline run `37074098652` on `main` commit `f48f18a` completed all three
  compute shards and the aggregate. It produced 1,620 rows, all 810 pairing
  keys, no missing/duplicate arm pairs, and no structural/provenance problems.
  It was marked `awaiting_matched_rerun`, which is explicitly intermediate,
  not final acceptance.
- Matched run `37075156838` used the same commit and completed the shards,
  artifact download, comparison, and summary. Its final gate failed:
  `acceptance_status=incomplete`, `matched_rerun.status=mismatch`, and
  `mismatch_count=2865` across 1,620 compared rows. No structural or
  provenance defects were reported.
- The deterministic mismatches were isolated to the `p=20` shard: all 540
  output rows (representing 90 generated datasets reused across contexts and
  arms) differed in at least one deterministic field. The `p=40` and `p=60`
  output rows matched.
- For mismatching rows, data/calibration/bootstrap seed fields matched, but
  `dataset_digest` differed. Small numerical differences were seen in fitted
  quantities; calibration `reference_reached_fraction` and tail values
  sometimes differed materially. Both runs recorded Python 3.11.16, NumPy
  2.4.6, the same package/config/commit identity.
- The first run's aggregate descriptively reported cap 2 reaching/certifying
  601/810 and cap 4 reaching 727/810 but certifying 601/810. These figures are
  preliminary only. Do not cite them as accepted Task 27 results while the
  matched-rerun gate is failed.

### What is known versus hypothesized

Known: seed fields and high-level provenance matched, but exact generated
dataset digests did not for the p=20 shard. Because the digest is computed on
the generated dataset before the full workflow runs, bootstrap or calibration
cannot explain the first point of divergence. The pipeline visibly supplies
separate data, calibration, and bootstrap RNG seeds; there is no k-fold CV
stage in this workflow.

Unknown: the root cause of the p=20 difference. Floating-point/linear-algebra
environment effects during multivariate data generation are plausible, but
not demonstrated.

Leading hypothesis (untested, added by a later reviewer): 
`simulations/localized_network_dgp.py` calls
`data_rng.multivariate_normal(..., population.covariance)`, whose default
`method='svd'` factorizes a covariance built from identical five-node modules.
That spectrum has repeated/near-degenerate singular values, so the singular
basis within each degenerate eigenspace is arbitrary and can depend on the
LAPACK/BLAS kernel and CPU dispatch. Different bases rotate the same seeded
normals into materially different datasets (not ULP noise). The all-or-nothing
pattern (all 540 p=20 rows differ, none of the p=40/60 rows) is more consistent
with a per-shard environment difference, such as a different runner CPU or
kernel, than with random nondeterminism inside a run. First test: compute the
SVD of the p=20 covariance under varied thread counts and `OPENBLAS_CORETYPE`
and compare singular vectors and `dataset_digest`. If confirmed, switching to
`method='cholesky'` or an explicit factorization changes the generated data,
so it is a protocol change requiring a new versioned decision plus a fresh
baseline and matched rerun; do not apply it to the frozen v1 manifest. No raw dataset arrays were retained in the hosted artifacts,
so digests alone cannot show whether values differed by a few ULPs or by a
larger amount. Do not weaken or replace the frozen comparator merely to make
the study pass. First isolate the divergence; then record any justified
protocol change as a new, traceable decision.

## Psychological survey/composite-score fit

Keep these cases distinct:

1. **Raw ordinal items:** one item has ordered categories, e.g. 1–5. A high
   frequency of 5s is a ceiling/top-end concentration, not a continuous
   heavy tail. Current v0.1 does not validate these inputs or a
   polychoric/ordinal network.
2. **Composite scores:** summing/averaging multiple items creates more
   possible score values and may be treated approximately continuously in
   some analyses. It remains bounded; if items are all skewed toward 5, the
   composite can still have ceiling compression and restricted variance.
   Whether it is appropriate for SDNA depends on scale construction and the
   intended estimand. This package has not simulated or validated that use.
3. **Current heavy-tail DGP:** continuous t-like data with `df=5`; it tests
   frequent/extreme continuous values. It does not recreate bounded Likert
   composites, top-heavy item thresholds, or response styles.
4. **Current influential-case DGP:** one case is shifted on the focal pair;
   it does not represent many respondents choosing the top response because
   of item wording, nor an acquiescence style affecting many items.
5. **Current collinearity DGP:** adjacent variables have population
   correlation 0.95; this probes highly redundant variables, not ceiling
   skew.

The nearest useful methodology question is whether SDNA works as a *localized
case-influence diagnostic on composite-score variables*, under low N and
bounded/top-heavy score distributions. That is narrower than claiming it
handles raw ordinal items or latent psychological networks.

## Recommended work pipeline

### Priority 1 — Diagnose Task 27 reproducibility without changing its gate

1. Recheck GitHub run/artifact availability and confirm the two reviewed run
   identities and checksums.
2. Build a minimal p=20 replay for one mismatching `(N,p,condition,replication)`
   seed. In a diagnostic-only artifact, retain the generated array or a
   compact exact representation; record max absolute difference, differing
   indices/count, dtype/shape, and exact per-stage digests.
3. Capture numerical runtime details beyond Python/NumPy: OS/runner image,
   CPU architecture, BLAS/LAPACK configuration, threadpool implementation and
   thread counts. Compare raw seeded random draws separately from covariance
   transformation, then compare fit, calibration, and bootstrap on the same
   saved dataset and child seeds.
4. Identify whether the discrepancy is data-generation arithmetic, software
   nondeterminism, or an implementation/seed-contract bug. Add a focused
   regression test for the demonstrated cause.
5. Preserve ADR-027 exact-match acceptance unless evidence justifies a
   specifically reviewed change. If the implementation/protocol changes,
   produce a fresh baseline and matched rerun at the same final commit; do not
   repurpose failed or mismatching artifacts as accepted evidence.
6. Only after the gate passes, write a new Task 27 evidence report and append
   a decision-log addendum with exact commits, run IDs, checksums, results,
   limits, and files for independent review. Preserve the v1 frozen protocol.

### Priority 2 — Pre-specify a realistic composite-score validation study

Before changing production code or claiming survey applicability, design a
study that is small enough to answer one clear question:

> For low-sample psychological studies where each network variable is a
> multi-item composite score, can the existing continuous SDNA workflow provide
> useful localized case-influence/edge-fragility information when item
> responses have realistic 1–5 ceiling skew?

The design should decide and freeze:

- the latent construct/network truth and whether the target is the
  **composite-score network** or the latent network (do not conflate them);
- number of items per composite, item loadings/reliability, correlated errors
  or local dependence, and scoring (sum vs mean);
- threshold patterns that yield symmetric, moderate ceiling, and severe
  ceiling response distributions, including heterogeneous item thresholds;
- whether to include reverse-worded items, acquiescence/response-style factors,
  and a small number of careless or influential respondents; these should be
  separate DGP factors, not lumped into “heavy tails”;
- `N`, number of composite variables `p`, replications, random streams, and
  matched continuous controls;
- target metrics and denominators: reach/censoring, certification, influence
  recall, focal-edge error, instability, and calibration behavior. Keep
  unavailable results/errors in scheduled denominators and avoid post-hoc
  success thresholds.

Prefer a staged design: (a) generate ordinal items from latent variables and
thresholds, (b) aggregate as users would, (c) run unchanged v0.1 SDNA on those
composites, and (d) compare against known truth at the explicitly chosen
composite level. Include a continuous matched control to isolate the extra
effect of thresholding/aggregation. Do not begin by adding ordinal support to
the estimator: first determine whether the composite-score path is a viable
and useful target.

Possible outcomes:

- If results are useful and stable in a clearly stated region, decide whether
  to document composites as a qualified extension and validate on fresh
  scenarios/samples.
- If reach or recovery collapses under plausible ceiling conditions, retain
  the current narrower scope and identify design/measurement conditions where
  the diagnostic is not informative.
- If the intended use is raw ordinal items or latent ordinal networks, draft a
  separate estimator/methodology design. That is a larger extension requiring
  ordinal network estimation and new influence, fragility, and calibration
  definitions—not merely accepting integers in input validation.

### Priority 3 — Only then decide product/method scope

Do not expand claims based only on successful software execution or an
attractive subgroup of simulation rows. Have an independent reviewer inspect
the accepted evidence and the exact estimand. Decide explicitly whether SDNA
remains a continuous-composite localized diagnostic, adds a validated
composite-score use case, or undertakes an ordinal-method extension. Keep
whole-network claims out of scope unless separately designed and tested.

## Decision log and evidence navigation

The authoritative historical decisions/provenance log is
[`docs/development/decisions.md`](decisions.md). It is append-only in spirit:
do not rewrite old rationale to fit new results. Add dated, commit-specific
entries for new decisions and fixes, naming the rationale, status, exact
commit(s), hosted run IDs, artifact/checksum identity, denominators, affected
files, and unresolved limits so another reviewer can trace each claim.

Other controlling/evidence files:

- `plan/sdna_repo_development_plan.md` — original package development plan;
  older checkbox counts are known stale, so use named task history and
  decision-log status instead of counting boxes.
- `docs/methodology/validation_matrix_v1.md` — frozen v0.1 matrix and scope.
- `docs/development/falsification_pilot_evidence_v2.md` — accepted 540-row
  v0.1 primary-run evidence and denominators.
- `docs/development/reach_boundary_evidence_v1.md` — hosted reach-only
  sensitivity results.
- `docs/methodology/cap_expansion_study_v1.md` — Task 24 paired cap results.
- `docs/methodology/certification_budget_sensitivity_study_v1.md` and
  `docs/methodology/certification_budget_sensitivity_study_v2.md` — frozen
  Task 26 design and hosted results.
- `docs/methodology/localized_network_operating_envelope_v1.md` — frozen Task
  27 protocol; do not edit its prespecified estimands/results into history.
- `docs/methodology/localized_network_operating_envelope_v2.md` — Task 27
  matched-rerun acceptance contract; it still says empirical results are
  pending and must be followed by an appropriately versioned evidence report
  after final acceptance.
- `docs/superpowers/specs/` and `docs/superpowers/plans/` — task designs and
  implementation sequencing.
- `.github/workflows/` — CI and manual validation/study workflows.

## Guardrails for the incoming agent

- Work inline; the user has explicitly asked not to use subagents.
- Use a separate worktree for substantive changes if appropriate, preserving
  the clean `main` checkout and existing worktree state.
- Do not modify frozen manifests or historical evidence to make results pass.
- Do not silently loosen exact matched-rerun acceptance or replace scientific
  thresholds after inspecting the outcome.
- Do not treat simulated continuous heavy tails as a proxy for ordinal
  ceiling-skewed survey scores.
- Keep implementation correctness, technical artifact acceptance, empirical
  operating performance, and real-data validity as four distinct claims.
- Commit meaningful, independently reviewable units and run focused tests plus
  the relevant full test/CI suite before claiming completion.

## Suggested opening instruction for the next agent

> Read `docs/development/ai_handoff_2026-10-03.md` and
> `docs/development/decisions.md` first. Verify the current branch, commit,
> worktree state, Task 27 run artifacts and any newer evidence before acting.
> Work inline without subagents. First isolate the Task 27 p=20 reproducibility
> mismatch without changing its acceptance rule. Keep that engineering issue
> separate from the unvalidated skewed Likert-composite use case. Then propose
> a narrow, pre-specified composite-score simulation design that targets the
> user's intended low-sample localized diagnostic; do not change production
> behavior or broaden claims before the design and evidence are reviewed.

## Addendum (later 2026-10-03): viability checks completed on `codex/viability-checks`

Edge-recovery and Likert-composite studies were pre-specified, run locally, and
documented (ADR-028). Read `docs/methodology/scope_and_evidence_summary.md`
first. Priority 2 of this handoff is therefore done for one design (p = 6,
five-item composites, one contamination type); a v2 with other contamination
types and weaker edges is the suggested follow-up. Priority 1 (Task 27 `p = 20`
mismatch) is still open and untouched.

## Addendum 2: Task 27 p=20 diagnosis result

The degenerate-spectrum hypothesis above was **refuted** (singular-value gaps
are distinct). The cause is CPU-dependent OpenBLAS kernel dispatch on
heterogeneous hosted runners; pinning `OPENBLAS_CORETYPE=Haswell` made seeded
data bit-identical across all observed CPU models. See
`docs/development/task27_p20_reproducibility_diagnosis.md` and ADR-029. Next:
merge the pin, then dispatch a fresh baseline and matched rerun of
`localized-network.yml` at the merged commit.
