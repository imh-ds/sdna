# Task 27 Localized Network Operating-Envelope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and execute the pre-specified 1,620-row Task 27 study measuring SDNA's localized case-influence and focal-edge fragility behavior across sparse network sizes, local motifs, sample sizes, and paired search caps.

**Architecture:** Add a Task 27-specific manifest and DGP without changing the existing v0.1 scenario registry or Tasks 24–26 contracts. Run paired cap-2/cap-4 records in deterministic `p` shards, checkpoint shard artifacts, then validate and summarize all shards with explicit denominators and study limitations. Keep the manual Actions workflow and hosted evidence append-only and traceable through the decision log.

**Tech Stack:** Python 3.11+, NumPy, pytest, Ruff, mypy, JSON/CSV/Markdown, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-02-task27-localized-network-operating-envelope-design.md`

## Global Constraints

- Keep `N=[50,100,150]`, `p=[20,40,60]`, five-node modules, three focal contexts, three data conditions, ten replications, caps `[2,4]`, relative target `0.5`, certification budget `1000`, calibration simulations `25`, bootstrap draws `100`, confidence `0.95`, and right-censored reference tails exactly as specified.
- The expected matrix has 810 pairing keys and 1,620 arm rows; each `p` shard has 270 pairing keys and 540 arm rows.
- Grow the graph by adding five-node modules; do not increase community size or local hub degree with `p`.
- The fixed focal partial correlation is `0.05`; the precision matrix has diagonal `1` and graph-edge entries `-0.05`.
- Pairing key is `(N, p, focal_context, condition, replication)`. Both caps share row seed, data digest, calibration seed, and bootstrap seed.
- Derive the data/case seed from `(root_seed, N, p, condition, replication)`, excluding focal context so all three contexts share the underlying clean draw and planted-case indices. Derive workflow streams from the shared row seed using `derive_workflow_seeds`.
- Use only cap 2 as the primary operating workflow; cap 4 is diagnostic sensitivity evidence. Neither results nor technical acceptance promote cap 4 or change any production setting.
- Preserve errors, unreached rows, uncertified rows, timeouts, and incomplete shards as distinct statuses. Never turn missing or failed metrics into zero.
- Shard manually by `p=[20,40,60]`; set a fixed 3,600-second per-shard computation ceiling and 70-minute Actions job timeout. Retain shard artifacts on every outcome.
- Do not alter existing v0.1 manifests, Task 24–26 result schemas/artifacts, or generic estimator behavior. Keep Task 27 additions study-specific unless compatibility tests justify and protect a shared change.
- Add an append-only decision entry before hosted empirical execution. Record implementation commit, merged commit, run ID, artifact names and checksums, denominators, deviations, and files for independent review in the hosted evidence addendum.

## Review Focus

- **Topology confounding:** verify module size, maximum degree, focal edges, and equal focal truth stay fixed across `p`; pin graph adjacency and truth in DGP tests.
- **Pairing drift:** verify cap arms and focal contexts share the intended seeds/data/case indices; pin keys, derived seeds, and digests in manifest/runner tests.
- **Truth metadata drift:** verify only the selected focal variables are shifted and that the recorded population partial correlation is the matrix-derived value; pin exact changed columns and planted indices in DGP tests.
- **Denominator ambiguity:** verify reach, certification, clean flags, and influence metrics report their intended valid counts and Wilson intervals; pin censored, failed, and missing examples in summary tests.
- **Partial-shard acceptance:** verify missing, duplicated, malformed, or timed-out `p` shards are visibly incomplete and cannot be accepted as a complete 1,620-row run; pin these cases in aggregate-validator and workflow tests.

---

## File Map

| File | Responsibility |
|---|---|
| `simulations/configs/localized_network_v1.json` | Frozen Task 27 matrix, graph and condition settings, paired arms, shard ceiling, and output contract. |
| `tools/localized_network_manifest.py` | Strict config loading, checksum, job expansion, pairing keys, and `p`-shard selection. |
| `simulations/localized_network_dgp.py` | Fixed sparse modular population, truth metadata, and deterministic dataset generation for each focal context/condition. |
| `tools/run_localized_network.py` | Paired workflow execution, row schema, per-`p` checkpointing, provenance, and shard status. |
| `tools/summarize_localized_network.py` | Shard validation, aggregate acceptance, denominators, Wilson intervals, and Markdown/JSON summaries. |
| `.github/workflows/localized-network.yml` | Manual-only three-shard Actions workflow and unconditional artifact retention. |
| `tests/test_localized_network_manifest.py` | Frozen values, expansion counts, pairing, checksum, and shard membership. |
| `tests/test_localized_network_dgp.py` | Graph structure, positive definiteness, equal focal truth, shared draws/cases, and focal-only shifts. |
| `tests/test_localized_network_runner.py` | Paired seeds/digests, row schema, checkpoint behavior, error rows, and timing/status metadata. |
| `tests/test_localized_network_summary.py` | Exact expected keys, duplicate/missing rows, denominators, Wilson intervals, and incomplete-shard behavior. |
| `tests/test_localized_network_workflow.py` | Manual-only trigger, three fixed shards, timeouts, aggregate gate, and failure artifact upload. |
| `docs/methodology/localized_network_operating_envelope_v1.md` | Frozen user-facing protocol and interpretation rules; empirical fields remain pending until run acceptance. |
| `docs/methodology/localized_network_operating_envelope_v2.md` | Hosted evidence, results, checksums, limits, and interpretation after the run. |
| `docs/development/decisions.md` | Append-only Task 27 decision and hosted-acceptance addendum. |

## Shared Interfaces and Data Contracts

### DGP

`simulations/localized_network_dgp.py` exposes:

```python
@dataclass(frozen=True)
class LocalizedNetworkPopulation:
    covariance: np.ndarray
    precision: np.ndarray
    partial_correlation: np.ndarray
    focal_edges: Mapping[str, tuple[int, int]]
    module_count: int

def build_localized_population(p: int) -> LocalizedNetworkPopulation: ...

def generate_localized_dataset(
    n: int,
    p: int,
    focal_context: str,
    condition: str,
    seed: int,
) -> SimulatedDataset: ...
```

`generate_localized_dataset` returns the existing `SimulatedDataset` type.
Given the same `(n, p, condition, replication)` seed, changing only
`focal_context` must retain the same base observations and planted-case indices,
then apply any condition shift only to that context's focal columns.

### Manifest and job key

`tools/localized_network_manifest.py` exposes:

```python
def load_localized_manifest(path: str | Path) -> dict[str, Any]: ...
def expand_localized_jobs(
    manifest: Mapping[str, Any], p_shard: int | None = None
) -> list[dict[str, Any]]: ...
def localized_pairing_keys(
    manifest: Mapping[str, Any], p_shard: int | None = None
) -> list[tuple[Any, ...]]: ...
def localized_manifest_checksum(manifest: Mapping[str, Any]) -> str: ...
```

Jobs contain `arm`, `N`, `p`, `focal_context`, `condition`, `replication`,
`target`, and `search_cap`. Arm names are exactly `baseline_cap2` and
`diagnostic_cap4`. A full expansion has 1,620 rows; each `p` shard has 540.

### Result CSV schema

Freeze these fields in this order before runner and summarizer implementation:

```text
arm,N,p,focal_context,condition,replication,data_seed,calibration_seed,
bootstrap_seed,dataset_digest,focal_i,focal_j,planted_case_indices,
module_count,true_rho,observed_rho,lambda,contamination_count,
contamination_status,fragility_target,search_cap,calibration_require_reached,
greedy_fragility_50,exact_fragility_50,certified,reached,
certification_combinations_checked,certification_combination_budget,
certification_budget_exhausted,certification_failure_reason,
reference_tail_probability,reference_reached_fraction,wald_z,
bootstrap_ci_excludes_zero,bootstrap_rejected_resamples,
influence_top_k_precision,influence_top_k_recall,
first_planted_reciprocal_rank,planted_absolute_influence_share,
fragility_status,certification_status,calibration_status,wald_status,
bootstrap_status,workflow_status,error_stage,error_type,error_message,
elapsed_seconds
```

`planted_case_indices` is canonical JSON (`[]` for clean data). The runner uses
the existing workflow status vocabulary and adds no meaning to existing fields.
Each shard directory contains `results.csv`, `shard_status.json`, and
`results.metadata.json`; the aggregate directory contains all three shard
records plus `summary.json` and `summary.md`.

### Summary denominators

- Reached rate: `reached / fragility-stage-completed`.
- Fragility-stage failure rate: `fragility-stage-errors / all-scheduled`.
- Certification rate conditional on reach: `certified / reached`.
- Certified yield: `certified / all-scheduled`.
- Budget-exhaustion rate: `budget-exhausted / reached`.
- Clean false-flag rate: valid clean rows flagged at `reference_tail_probability <= 0.05` divided by clean rows with a valid finite reference-tail probability; report invalid/missing clean rows separately.
- Influence top-`k` metrics: average over contaminated rows with valid influence output, with valid-row and scheduled-row counts both shown.

Every proportion reports numerator, denominator, and a 95% Wilson interval.
An undefined denominator yields JSON `null`, never zero.

---

## Task 1: Freeze the Manifest and Pairing Contract

**Parallel assignment:** Agent A; disjoint from Task 2.

**Files:**
- Create: `simulations/configs/localized_network_v1.json`
- Create: `tools/localized_network_manifest.py`
- Create: `tests/test_localized_network_manifest.py`

- [ ] Add tests for the exact frozen values, 1,620 rows, 810 pairing keys, 810 rows per cap, 270 pairing keys/540 rows per `p`, and strict rejection of changed caps, dimensions, scenario values, or counts.
- [ ] Add pairing tests proving each key has exactly both arms and that `p_shard` returns only the corresponding 540 rows and 270 keys.
- [ ] Implement canonical checksum and deterministic expansion with data-seed key dimensions explicitly excluding `focal_context` but including `(N,p,condition,replication)`.
- [ ] Run `py -3.11 -m pytest tests/test_localized_network_manifest.py -q`; expect all manifest contract tests to pass.
- [ ] Commit as `feat: freeze Task 27 localized network manifest`.

## Task 2: Implement the Sparse Modular DGP

**Parallel assignment:** Agent B; disjoint from Task 1.

**Files:**
- Create: `simulations/localized_network_dgp.py`
- Create: `tests/test_localized_network_dgp.py`

- [ ] Test module counts `4`, `8`, and `12`; fixed five-node module membership; exact ring, hub, and adjacent-module bridge edges; maximum degree at most five; symmetric precision; positive eigenvalues; and focal population partial correlations equal to `0.05` within `1e-12`.
- [ ] Test the three exact focal-edge indices and reject unsupported `p`, context, condition, invalid `n`, and malformed dimensions.
- [ ] Test that a matched seed across focal contexts yields identical clean data and planted indices, and that single/coalition conditions change only the two focal columns by exactly `4.0` for the known indices.
- [ ] Implement `LocalizedNetworkPopulation`, `build_localized_population(p)`, and `generate_localized_dataset(n,p,focal_context,condition,seed)` returning `SimulatedDataset`.
- [ ] Run `py -3.11 -m pytest tests/test_localized_network_dgp.py -q`; expect all DGP contract tests to pass.
- [ ] Commit as `feat: add localized modular network generator`.

## Task 3: Add the Paired, Checkpointed Runner

**Files:**
- Create: `tools/run_localized_network.py`
- Create: `tests/test_localized_network_runner.py`
- Consumes: Task 1 manifest API and Task 2 DGP API.

- [ ] Test exact CSV field order, one dataset digest per pairing key shared by both cap rows, shared calibration/bootstrap seeds across contexts and caps, exact `p` shard membership, and recorded truth/contamination metadata.
- [ ] Test one-row-at-a-time or fixed-batch checkpointing: after an injected interruption, completed rows and `shard_status.json` remain readable with status `incomplete`; completed rows are not rewritten as errors.
- [ ] Test generation and workflow exceptions become explicit error rows with the correct stage and do not abort the remainder of the shard.
- [ ] Implement `run_localized_network(config_path, output_dir, p_shard)`; write `results.csv`, `shard_status.json`, and provenance metadata atomically/checkpointed, recording expected/completed rows and runtime ceiling status.
- [ ] Keep one in-memory generated dataset per pairing key for cap 2/cap 4; derive workflow seeds with `derive_workflow_seeds(data_seed)` and pass all frozen values to `run_full_workflow`.
- [ ] Run `py -3.11 -m pytest tests/test_localized_network_runner.py -q`; expect all pairing, checkpoint, and failure-state tests to pass.
- [ ] Commit as `feat: run paired localized network shards`.

## Task 4: Validate and Summarize the Study Artifacts

**Files:**
- Create: `tools/summarize_localized_network.py`
- Create: `tests/test_localized_network_summary.py`
- Consumes: Task 1 job expansion and Task 3 exact CSV/status schemas.

- [ ] Test valid full synthetic shards, correct counts and Wilson intervals for each denominator, null metrics at zero denominator, and separate status counts for errors/unreached/certification exhaustion.
- [ ] Test rejection or explicit incomplete status for a missing shard, duplicate key, missing arm member, changed seed/digest, wrong truth metadata, malformed JSON case indices, and tampered checksum.
- [ ] Test that clean false flags use only finite valid clean reference-tail rows and that invalid/missing clean rows are separately counted.
- [ ] Test that a missing/timed-out/incomplete `p` shard yields an incomplete aggregate while still writing summary artifacts for available rows.
- [ ] Implement `summarize_localized_network(shard_dirs, config_path, output_dir, validate=True)`, per-cell summaries, overall provenance, and an aggregate acceptance status that is complete only for all 1,620 valid rows.
- [ ] Run `py -3.11 -m pytest tests/test_localized_network_summary.py -q`; expect denominator, tamper, and partial-aggregate tests to pass.
- [ ] Commit as `feat: validate localized network artifacts`.

## Task 5: Add the Manual Hosted Workflow and Freeze the User Protocol

**Files:**
- Create: `.github/workflows/localized-network.yml`
- Create: `tests/test_localized_network_workflow.py`
- Create: `docs/methodology/localized_network_operating_envelope_v1.md`
- Modify: `docs/development/decisions.md` (append Task 27 pre-run decision)

- [ ] Test that Actions has only `workflow_dispatch`, exactly three fixed `p` shards, a 70-minute job timeout, unconditional upload, and an aggregate job that preserves failed/incomplete shard outputs.
- [ ] Test documented protocol values and metrics against the manifest; explicitly label cap 2 primary, cap 4 diagnostic, per-edge descriptive clean flags, `p>N` stress cells, and no universal cutoff claim.
- [ ] Add a pre-run append-only decision record with the spec commit `2f0b49a`, this implementation-plan commit, exact manifest/checksum once frozen, reasons for the study, metric denominators, commit and files to inspect, and the pending hosted-run status.
- [ ] Add the v1 methodology page as the readable protocol; do not put empirical findings in v1 before the hosted run.
- [ ] Run `py -3.11 -m pytest tests/test_localized_network_workflow.py -q`; expect workflow contract and documentation/manifest consistency tests to pass.
- [ ] Commit as `feat: add manual localized network study workflow`.

## Task 6: Integrated Local Verification and Pull Request Review

**Files:** all Task 27 files above.

- [ ] Run the focused Task 27 tests and repository-wide tests, lint, type-check, and compile checks in the supported CI Python matrix; report any pre-existing failures separately.
- [ ] Verify all existing Tasks 24–26 fixture/artifact contracts remain unchanged and their focused tests pass.
- [ ] Review the complete diff against the spec, especially seed derivation, exact `p`-shard counts, null denominators, checkpoint durability, and no accidental production-default changes.
- [ ] Push the branch and open a reviewed pull request; merge only after required GitHub Actions checks pass and the review finds no unresolved methodology or artifact-contract issue.
- [ ] Commit any required fixes as separate meaningful commits before merge.

## Task 7: Run the Frozen Matrix on `main` and Record Hosted Evidence

**Files:**
- Create: `docs/methodology/localized_network_operating_envelope_v2.md`
- Modify: `docs/development/decisions.md` (append hosted-acceptance addendum)

- [ ] After the implementation PR is merged, manually dispatch the three-shard Task 27 workflow on `main`; preserve all shard/aggregate artifacts if a job fails or times out.
- [ ] Validate the merged `main` run's manifest checksum, 1,620 result rows, 810 paired keys, 540 rows per shard, software provenance, and artifact checksums.
- [ ] If complete and valid, report results by `N × p × focal context × condition × cap`, retaining every denominator, Wilson interval, error, censoring, and certification outcome. If incomplete, report the exact failure boundary without treating missing outputs as zero.
- [ ] Add v2 evidence and an ADR addendum with run ID, source/merge commits, artifact names and hashes, Python/NumPy/package versions, runtimes, deviations, interpretation limits, and exact files for independent review.
- [ ] Commit evidence as `docs: record Task 27 hosted operating-envelope evidence`, open and merge a reviewed evidence PR, then verify required checks and post-merge `main` Actions.

## Execution Order and Parallel Work

1. Run Tasks 1 and 2 concurrently using agents with disjoint file ownership.
2. Review and integrate both deliverables before starting Task 3.
3. Task 3 and Task 4 may then be implemented concurrently only against the CSV/status contract above; review their interface agreement before integration.
4. Implement Task 5 after runner and summary CLI arguments/artifact paths are fixed.
5. The lead agent owns integrated verification, independent diff review, PR creation/merge, manual dispatch, evidence validation, and evidence PR. No agent merges or dispatches Actions independently.
