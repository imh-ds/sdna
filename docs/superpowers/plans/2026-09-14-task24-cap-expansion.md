# Task 24 Paired Search-Cap Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and validate a deterministic, full-workflow comparison of search caps 2, 3, and 4 on the frozen v0.1 simulation matrix without changing the v0.1 production baseline.

**Architecture:** Keep the existing v0.1 runner and reach-only diagnostic intact, then add a separate cap-expansion manifest, runner, schema validator, and summarizer. Extract the row-level full workflow into a reusable helper so the new paired runner can generate each dataset once and run all three cap arms against the same data with shared downstream child seeds.

**Tech Stack:** Python 3.11+, NumPy, pytest, Ruff, JSON/CSV, Markdown, and manual GitHub Actions with the repository's pinned CI constraints.

**Spec:** `docs/superpowers/specs/2026-09-14-task24-cap-expansion-design.md`

## Global Constraints

- The production and v0.1 baseline remains `search_cap=2`; this study cannot promote another cap automatically.
- The only primary arms are `baseline_cap2`, `cap3`, and `cap4`, with search caps 2, 3, and 4 respectively.
- The study contains 540 rows per arm and 1,620 rows total: six scenarios × three `N` values × three `p` values × ten replications × three arms.
- The frozen seed is `20260910`; the frozen `N`, `p`, scenario, parameter, target, confidence, calibration, bootstrap, and certification settings are copied exactly from the approved specification.
- Each paired key generates one dataset; all three arms record the same data seed, calibration seed, bootstrap seed, and stable dataset digest.
- Calibration runs with `require_reached=False` and reports right-censored reference tails separately from observed-unreached and error states.
- Greedy search, exact certification, calibration, Wald comparison, shrinkage bootstrap, truth-aware influence metrics, and runtime are reported separately; no stage failure is coerced to zero.
- Pooled arm metrics and jointly-valid pair metrics use separate named populations and denominators.
- The hosted workflow is `workflow_dispatch` only, records its commit and run provenance, uploads artifacts, and does not become a pull-request gate or scheduled job.
- The 15-minute runtime value is an operational budget indicator. A budget exceedance is retained and reported; it does not trigger algorithmic optimization or invalidate the artifact by itself.
- Existing v0.1 runner output, reach-boundary output, estimator behavior, and committed validation matrix are not silently changed.

## File map

| File | Responsibility |
| --- | --- |
| `simulations/configs/cap_expansion_v1.json` | Frozen three-arm study configuration and declared 1,620-row count. |
| `tools/cap_expansion_manifest.py` | Load, validate, checksum, and expand the frozen configuration into paired jobs. |
| `simulations/full_workflow.py` | Reusable full-workflow execution and deterministic child-seed/data-digest helpers. |
| `tools/run_cap_expansion.py` | Generate each paired dataset once, execute all arms, and write the enriched row artifact plus metadata. |
| `tools/summarize_cap_expansion.py` | Validate the artifact and produce pooled, paired, jointly-valid, timing, JSON, and Markdown summaries. |
| `tests/test_cap_expansion_manifest.py` | Manifest shape, arm, row-count, and pairing-contract tests. |
| `tests/test_full_workflow.py` | Full-workflow stage, stream, censoring, and failure-state tests. |
| `tests/test_cap_expansion_runner.py` | Same-data/same-seed arm pairing and row/metadata tests. |
| `tests/test_cap_expansion_summary.py` | Endpoint, denominator, transition, validation, and tamper-detection tests. |
| `docs/methodology/cap_expansion_study_v1.md` | User-facing pre-specified study description and links to the exact design/config. |
| `.github/workflows/cap-expansion.yml` | Manual hosted execution, validation, budget reporting, and artifact upload. |
| `docs/development/decisions.md` | ADR-022 provenance and implementation traceability. |

---

## Shared test fixtures

The focused summary tests use this concrete row builder. It supplies the
existing summary fields and the cap-expansion status/provenance fields, so a
test can vary only the state relevant to the assertion:

```python
def cap_row(
    arm: str,
    replication: int,
    *,
    reached: bool | None,
    status: str = "ok",
    digest: str = "dataset-a",
    observed_rho: float = 0.2,
    exact_fragility: float | None = 2.0,
) -> dict[str, object]:
    cap = {"baseline_cap2": 2, "cap3": 3, "cap4": 4}[arm]
    is_error = status == "error"
    fragility_status = "error" if is_error else ("reached" if reached else "unreached")
    return {
        "arm": arm, "scenario": "coalition_contamination", "parameter_id": 0,
        "parameter": 3, "replication": replication, "N": 50, "p": 5,
        "data_seed": 11, "calibration_seed": 12, "bootstrap_seed": 13,
        "dataset_digest": digest, "fragility_target": 0.5, "search_cap": cap,
        "true_rho": 0.0, "observed_rho": observed_rho, "lambda": 0.1,
        "contamination_count": 3, "contamination_status": 1,
        "greedy_fragility_50": exact_fragility if reached else None,
        "exact_fragility_50": exact_fragility if reached else None,
        "certified": bool(reached) if not is_error else None, "reached": reached,
        "reference_tail_probability": 0.01 if reached else None,
        "reference_reached_fraction": 1.0 if reached else 0.0,
        "wald_z": 1.0, "bootstrap_ci_excludes_zero": False,
        "bootstrap_rejected_resamples": 0,
        "influence_top_k_precision": 0.5, "influence_top_k_recall": 0.5,
        "first_planted_reciprocal_rank": 1.0,
        "planted_absolute_influence_share": 0.4,
        "fragility_status": fragility_status,
        "certification_status": "certified" if reached else "skipped_unreached",
        "calibration_status": "finite" if reached else "observed_unreached",
        "wald_status": "error" if is_error else "ok",
        "bootstrap_status": "error" if is_error else "ok",
        "workflow_status": "error" if is_error else ("ok" if reached else "partial"),
        "error_stage": "bootstrap" if is_error else None,
        "error_type": "RuntimeError" if is_error else None,
        "error_message": "synthetic failure" if is_error else None,
        "elapsed_seconds": 0.1,
    }
```

For validator tests, define `write_valid_artifact_fixture(tmp_path)` in the
test module by expanding the committed manifest into all 1,620 jobs, creating
one valid `cap_row`-shaped record per job with the job's arm/key/cap fields,
writing matching metadata and summary JSON, and returning the four artifact
paths. The test then changes one `dataset_digest` cell and verifies the exact
pairing error without relying on a full numerical simulation.

### Task 1: Freeze and validate the cap-expansion manifest

**Files:**
- Create: `simulations/configs/cap_expansion_v1.json`
- Create: `tools/cap_expansion_manifest.py`
- Test: `tests/test_cap_expansion_manifest.py`

**Interfaces:**
- `CAP_ARM_NAMES: tuple[str, ...] = ("baseline_cap2", "cap3", "cap4")`.
- `PAIRING_FIELDS: tuple[str, ...] = ("scenario", "N", "p", "parameter_id", "replication")`.
- `load_cap_expansion_manifest(path: str | Path) -> dict[str, Any]` validates and returns the parsed manifest.
- `expand_cap_expansion_jobs(manifest: Mapping[str, Any]) -> list[dict[str, Any]]` returns one job mapping per arm and paired key.
- `cap_expansion_pairing_keys(manifest: Mapping[str, Any]) -> list[tuple[Any, ...]]` returns the sorted unique paired keys used to derive row seeds.
- `manifest_checksum(manifest: Mapping[str, Any]) -> str` returns the canonical SHA-256 checksum used in metadata.

The JSON must contain `version=1`, seed `20260910`, `replications=10`,
`n_values=[50,100,150]`, `p_values=[5,10,20]`, all six scenario names,
`focal_edge=[0,1]`, `population_partial_r=[0.2]`,
`contamination_cases=[3]`, `fragility_targets=[0.9,0.7,0.5,0.3]`,
`primary_target=0.5`, `calibration_simulations=25`, `bootstrap_samples=100`,
`bootstrap_confidence=0.95`, `certification_combination_budget=1000`,
`calibration_require_reached=false`, `operational_runtime_ceiling_seconds=900`,
`expected_rows=1620`, and the exact three arm definitions.

- [ ] **Step 1: Write manifest tests that define the frozen contract**

```python
def test_cap_expansion_manifest_has_three_balanced_arms() -> None:
    manifest = load_cap_expansion_manifest(
        Path("simulations/configs/cap_expansion_v1.json")
    )
    jobs = expand_cap_expansion_jobs(manifest)
    assert len(jobs) == 1620
    assert Counter(job["arm"] for job in jobs) == {
        "baseline_cap2": 540,
        "cap3": 540,
        "cap4": 540,
    }
    assert {job["search_cap"] for job in jobs} == {2, 3, 4}
    assert len(cap_expansion_pairing_keys(manifest)) == 540
```

- [ ] **Step 2: Run the focused tests and confirm the missing contract**

Run: `python -m pytest tests/test_cap_expansion_manifest.py -q`

Expected: FAIL because the cap-expansion manifest module and configuration do not yet exist.

- [ ] **Step 3: Implement strict manifest loading and expansion**

Reject missing or duplicate arms, unknown scenarios, wrong caps, wrong row
count, modified matrix values, duplicate paired keys, and any arm outside the
three exact definitions. Compute the expected row count from the matrix rather
than trusting the declared count, then require the declared count to equal
1,620. Preserve the job ordering used for deterministic seed assignment:
`N`, `p`, scenario, parameter ID, replication, with arm order applied only
after the paired keys are established.

- [ ] **Step 4: Run manifest tests and verify the exact expanded grid**

Run: `python -m pytest tests/test_cap_expansion_manifest.py -q`

Expected: all tests pass, including rejection tests for changed caps, extra
arms, wrong `expected_rows`, and a duplicated pairing key.

- [ ] **Step 5: Commit the frozen manifest slice**

```bash
git add simulations/configs/cap_expansion_v1.json tools/cap_expansion_manifest.py tests/test_cap_expansion_manifest.py
git commit -m "feat: freeze paired cap expansion manifest"
```

---

### Task 2: Extract the reusable full-workflow execution contract

**Files:**
- Create: `simulations/full_workflow.py`
- Test: `tests/test_full_workflow.py`
- Modify: `simulations/run_simulation.py`
- Test: `tests/test_simulation_runner.py`

**Interfaces:**
- `WorkflowSeeds` is a frozen dataclass with integer fields `calibration` and `bootstrap`.
- `derive_workflow_seeds(row_seed: int) -> WorkflowSeeds` deterministically derives the two named child-stream seeds from one row/data seed.
- `dataset_digest(dataset: SimulatedDataset) -> str` hashes the canonical contiguous `X` shape, dtype, and bytes.
- `run_full_workflow(dataset: SimulatedDataset, *, target: FragilityTarget, search_cap: int, calibration_simulations: int, bootstrap_samples: int, bootstrap_confidence: float, certification_combination_budget: int, seeds: WorkflowSeeds, calibration_require_reached: bool = False) -> dict[str, Any]` executes the complete estimator workflow and returns stage values plus explicit stage statuses.

The returned mapping must include the existing estimator fields needed by
`simulations.summarize.summarize_rows`, plus these exact status fields:

```python
{
    "fragility_status": "reached" | "unreached" | "error",
    "certification_status": "certified" | "not_certified" | "skipped_unreached" | "error",
    "calibration_status": "finite" | "right_censored" | "observed_unreached" | "error",
    "wald_status": "ok" | "error",
    "bootstrap_status": "ok" | "error",
    "workflow_status": "ok" | "partial" | "error",
    "error_stage": str | None,
    "error_type": str | None,
    "error_message": str | None,
}
```

`workflow_status="partial"` is reserved for declared non-error states such
as an unreached fragility target or skipped certification. Any caught numerical
exception or stage exception sets the relevant stage to `error`, records the
first failing stage in the error fields, and leaves successful independent
stage outputs intact.

Calibration status is derived from the current contract: `finite` means the
observed target and every reference target reached; `right_censored` means the
observed target reached but at least one reference target did not; and
`observed_unreached` means the observed tail probability is unavailable because
the observed search did not reach. The helper must pass the configuration's
`calibration_require_reached` value explicitly.

- [ ] **Step 1: Write failing helper tests for deterministic streams and statuses**

```python
def test_workflow_seeds_and_dataset_digest_are_deterministic(gaussian_data) -> None:
    first = derive_workflow_seeds(20260910)
    second = derive_workflow_seeds(20260910)
    assert first == second
    assert first.calibration != first.bootstrap
    assert dataset_digest(gaussian_data) == dataset_digest(gaussian_data.copy())


def test_full_workflow_reports_all_stage_statuses(gaussian_data) -> None:
    result = run_full_workflow(
        gaussian_data,
        target=FragilityTarget("relative", 0.5),
        search_cap=2,
        calibration_simulations=1,
        bootstrap_samples=2,
        bootstrap_confidence=0.95,
        certification_combination_budget=20,
        seeds=derive_workflow_seeds(7),
    )
    assert {"fragility_status", "certification_status", "calibration_status",
            "wald_status", "bootstrap_status", "workflow_status"} <= set(result)
    assert result["bootstrap_status"] in {"ok", "error"}
```

- [ ] **Step 2: Run the focused tests and confirm the helper is absent**

Run: `python -m pytest tests/test_full_workflow.py -q`

Expected: FAIL because the reusable workflow module and status contract do not yet exist.

- [ ] **Step 3: Implement named child streams, digesting, and stage execution**

Move the current row-level calls for fit, greedy fragility, certification,
calibration, Wald, bootstrap, and influence metrics into the helper without
changing their estimator arguments. Use the shared calibration and bootstrap
seeds for all cap arms. Catch the existing numerical/domain exception classes
at stage boundaries, preserve `None` for unavailable values, and never encode
an unreached or censored result as zero.

- [ ] **Step 4: Refactor the existing v0.1 runner to use the helper**

Keep `simulations.run_simulation.FIELDNAMES`, CSV output, metadata shape, and
existing CLI behavior stable. Adapt the helper result into the current v0.1
row schema and retain the current baseline's `require_reached=False` behavior.
Do not add cap-arm fields to the frozen v0.1 CSV.

- [ ] **Step 5: Run focused regression tests**

Run: `python -m pytest tests/test_full_workflow.py tests/test_simulation_runner.py -q`

Expected: all new helper tests and all existing v0.1 runner tests pass.

- [ ] **Step 6: Commit the shared workflow slice**

```bash
git add simulations/full_workflow.py simulations/run_simulation.py tests/test_full_workflow.py tests/test_simulation_runner.py
git commit -m "refactor: share full simulation workflow execution"
```

---

### Task 3: Implement the paired cap-expansion runner and artifact schema

**Files:**
- Create: `tools/run_cap_expansion.py`
- Create: `tests/test_cap_expansion_runner.py`

**Interfaces:**
- `CAP_EXPANSION_FIELDNAMES: list[str]` defines the exact CSV order.
- `run_cap_expansion(config_path: str | Path, output_path: str | Path) -> None` writes the CSV and adjacent `.metadata.json`.
- `generate_cap_expansion_dataset(job: Mapping[str, Any], seed: int, manifest: Mapping[str, Any]) -> SimulatedDataset` generates one declared DGP from the existing scenario registry.
- `pairing_key(job: Mapping[str, Any]) -> tuple[Any, ...]` returns the five-field key from `PAIRING_FIELDS`.

Define `CAP_EXPANSION_FIELDNAMES` in this order:

```python
[
    "arm", "scenario", "parameter_id", "parameter", "replication", "N", "p",
    "data_seed", "calibration_seed", "bootstrap_seed", "dataset_digest",
    "fragility_target", "search_cap", "calibration_require_reached",
    "true_rho", "observed_rho", "lambda", "contamination_count",
    "contamination_status", "greedy_fragility_50", "exact_fragility_50",
    "certified", "reached", "reference_tail_probability",
    "reference_reached_fraction", "wald_z", "bootstrap_ci_excludes_zero",
    "bootstrap_rejected_resamples", "influence_top_k_precision",
    "influence_top_k_recall", "first_planted_reciprocal_rank",
    "planted_absolute_influence_share", "fragility_status",
    "certification_status", "calibration_status", "wald_status",
    "bootstrap_status", "workflow_status", "error_stage", "error_type",
    "error_message", "elapsed_seconds",
]
```

The CSV must include the pairing/provenance fields `arm`, `scenario`,
`parameter_id`, `parameter`, `replication`, `N`, `p`, `data_seed`,
`calibration_seed`, `bootstrap_seed`, `dataset_digest`, `fragility_target`,
and `search_cap`; the complete estimator/metric fields; all six stage status
fields; `contamination_count`; `bootstrap_rejected_resamples`; and
`elapsed_seconds`.

The runner must derive one data seed per sorted pairing key, cache the
generated `SimulatedDataset` by pairing key, and execute each arm using that
cached dataset. It must derive the same `WorkflowSeeds` from the data seed for
each arm and write the digest from the same dataset object. Metadata must
include `git_commit`, Python/NumPy/package versions, manifest checksum, row
and arm counts, status counts by workflow/stage, total and per-arm runtime,
`runtime_ceiling_seconds`, and `budget_exceeded`.

- [ ] **Step 1: Write failing pairing and provenance tests**

```python
def test_cap_expansion_runner_reuses_data_and_child_seeds(tmp_path) -> None:
    config = Path("simulations/configs/cap_expansion_v1.json")
    output = tmp_path / "cap-expansion.csv"
    run_cap_expansion(config, output)
    rows = list(csv.DictReader(output.open(newline="", encoding="utf-8")))
    assert len(rows) == 1620
    grouped = defaultdict(list)
    for row in rows:
        grouped[tuple(row[field] for field in PAIRING_FIELDS)].append(row)
    assert all(len(group) == 3 for group in grouped.values())
    assert all(len({row["data_seed"] for row in group}) == 1 for group in grouped.values())
    assert all(len({row["dataset_digest"] for row in group}) == 1 for group in grouped.values())
    assert all(len({row["calibration_seed"] for row in group}) == 1 for group in grouped.values())
    assert all(len({row["bootstrap_seed"] for row in group}) == 1 for group in grouped.values())
```

Use a one-cell test manifest or monkeypatch the manifest expansion for the
focused test so it completes quickly; reserve the full 1,620-row execution for
the manual workflow and final verification.

- [ ] **Step 2: Run the focused test and confirm the runner is absent**

Run: `python -m pytest tests/test_cap_expansion_runner.py -q`

Expected: FAIL because the cap-expansion runner and artifact schema do not yet exist.

- [ ] **Step 3: Implement paired dataset generation and row assembly**

Reuse `generate_scenario` for all six DGP names, apply the row's clean-edge
partial or contamination parameter exactly as the existing runner does, call
`run_full_workflow`, and merge its result with the arm/provenance fields. Keep
the configured primary target at `0.5` even though the configuration retains
the complete target list for provenance.

- [ ] **Step 4: Implement metadata and explicit per-row failure preservation**

Ensure a row is written for every declared job even when one stage fails. A
stage error must retain its `error_stage`, `error_type`, and message while
keeping the same pairing fields, seeds, digest, and runtime. Do not drop the
row or convert a failed value into a numeric sentinel.

- [ ] **Step 5: Run the small runner test and schema inspection**

Run: `python -m pytest tests/test_cap_expansion_runner.py -q`

Expected: all paired rows have three arms, identical data/child seeds and
digests, unique arm/pairing keys, and complete metadata.

- [ ] **Step 6: Commit the runner slice**

```bash
git add tools/run_cap_expansion.py tests/test_cap_expansion_runner.py
git commit -m "feat: run paired full-workflow cap study"
```

---

### Task 4: Add cap-specific summaries, joint metrics, and artifact validation

**Files:**
- Create: `tools/summarize_cap_expansion.py`
- Create: `tests/test_cap_expansion_summary.py`

**Interfaces:**
- `summarize_cap_expansion_rows(rows: Sequence[Mapping[str, Any]], manifest: Mapping[str, Any]) -> dict[str, Any]` returns the complete machine-readable summary.
- `summarize_cap_expansion(results_csv: str | Path, summary_json: str | Path, summary_markdown: str | Path, manifest_path: str | Path) -> None` writes JSON and Markdown summaries.
- `validate_cap_expansion(results_csv: str | Path, metadata_json: str | Path, summary_json: str | Path, manifest_path: str | Path) -> None` raises `ValueError` for any schema, pairing, provenance, or invariant violation.

The summary must contain:

- pooled per-arm summaries using the existing finite/censor-aware metrics;
- stage-status and denominator counts for every arm;
- baseline-to-cap3 and baseline-to-cap4 transition counts at target `0.5`;
- paired reach-rate differences with explicit non-error and all-row denominators;
- errors separated from unreached/censored rows;
- pooled and jointly-valid-pair metrics under distinct names;
- calibration tail mode/status counts, certification status counts, bootstrap
  rejection counts, false-flag metrics, and comparator summaries;
- arm-level and total timing plus budget-exceedance status; and
- the manifest checksum and row/arm counts.

For a candidate comparison, match rows only by
`(scenario, N, p, parameter_id, replication)`. Count `reached`/`unreached`
transitions only among pairs without a stage error, and report error counts
separately. Define a jointly-valid pair for a metric as both arm rows meeting
that metric's finite/status contract. Never use an invalid row as a zero or
silently pool it into a paired denominator.

- [ ] **Step 1: Write hand-computable summary tests**

```python
def test_cap_summary_reports_transitions_and_joint_denominators() -> None:
    rows = [
        cap_row("baseline_cap2", 0, reached=False),
        cap_row("cap3", 0, reached=True),
        cap_row("cap4", 0, reached=True),
        cap_row("baseline_cap2", 1, reached=True),
        cap_row("cap3", 1, reached=True),
        cap_row("cap4", 1, reached=True),
        cap_row("baseline_cap2", 2, reached=True),
        cap_row("cap3", 2, reached=None, status="error"),
        cap_row("cap4", 2, reached=True),
    ]
    manifest = load_cap_expansion_manifest(Path("simulations/configs/cap_expansion_v1.json"))
    summary = summarize_cap_expansion_rows(rows, manifest)
    comparison = summary["comparisons"]["cap3"]
    assert comparison["transition_counts"]["unreached_to_reached"] == 1
    assert comparison["candidate_error_rows"] == 1
    assert comparison["jointly_valid_pair_count"] == 2
    assert comparison["pooled_metrics"] != comparison["jointly_valid_pair_metrics"]


def test_cap_validator_rejects_mismatched_pair_digest(tmp_path) -> None:
    results, metadata, summary, manifest = write_valid_artifact_fixture(tmp_path)
    rows = list(csv.DictReader(results.open(newline="", encoding="utf-8")))
    rows[1]["dataset_digest"] = "tampered"
    with results.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CAP_EXPANSION_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="dataset_digest"):
        validate_cap_expansion(results, metadata, summary, manifest)
```

- [ ] **Step 2: Run focused tests and confirm cap summaries are absent**

Run: `python -m pytest tests/test_cap_expansion_summary.py -q`

Expected: FAIL because the cap-specific summary and validation functions do not yet exist.

- [ ] **Step 3: Implement parsing, status populations, transitions, and joint metrics**

Reuse `summarize_rows` for each arm's scenario-level pooled metrics, then add
cap-specific comparisons. Keep `pooled_metrics` and
`jointly_valid_pair_metrics` as separate JSON objects with their own counts.
Include each denominator beside the rate or contrast it supports.

- [ ] **Step 4: Implement strict artifact validation**

Require the exact field order, 1,620 unique rows, exact arm counts, exact
pairing-key set, allowed cap values, same pair seeds/digests, valid status
enums, finite/range-checked numeric values, metadata checksum/count/timing
agreement, and summary row/arm/comparison agreement. Validate that
`budget_exceeded` is reported from timing but do not reject an otherwise valid
artifact solely because the 900-second operational budget was exceeded.

- [ ] **Step 5: Implement Markdown evidence output**

Report the frozen configuration, cap-arm counts, primary transitions and
reach-rate denominators, status/censoring counts, paired-vs-pooled metric
labels, runtime, budget status, provenance commit, and the limitations/no-
promotion rule. The Markdown output must state that it is generated evidence
and must not imply a new production cap.

- [ ] **Step 6: Run summary/validator tests and lint**

Run: `python -m pytest tests/test_cap_expansion_summary.py tests/test_simulation_metrics.py -q` and `ruff check tools simulations tests`.

Expected: all tests pass and Ruff reports no violations.

- [ ] **Step 7: Commit the summary and validator slice**

```bash
git add tools/summarize_cap_expansion.py tests/test_cap_expansion_summary.py
git commit -m "feat: validate and summarize cap expansion evidence"
```

---

### Task 5: Publish the user-facing methodology description

**Files:**
- Create: `docs/methodology/cap_expansion_study_v1.md`
- Modify: `docs/development/decisions.md`
- Test: `tests/test_cap_expansion_summary.py`

**Interfaces:**
- The methodology page links to the approved design, frozen JSON configuration, runner, validator, and manual workflow using repository-relative links.
- ADR-022 gains a traceability block naming the originating decision commit `bb7a851`, the exact design/config/implementation files, and the review questions for an independent agent.

The methodology page must state the three arms, 1,620-row count, paired data
and seed semantics, full-workflow stages, right-censored versus strict tail
behavior, pooled/joint denominator distinction, runtime budget, manual-only
workflow, and no-promotion interpretation. It must distinguish the prior
reach-only evidence from this planned full-workflow study and must not report
unexecuted results.

The ADR traceability block must contain:

```markdown
**Decision introduced in commit:** `bb7a851`

**Design/specification:** `docs/superpowers/specs/2026-09-14-task24-cap-expansion-design.md`

**Implementation plan:** `docs/superpowers/plans/2026-09-14-task24-cap-expansion.md`

**Files for independent review:**
- `simulations/configs/cap_expansion_v1.json`
- `tools/cap_expansion_manifest.py`
- `simulations/full_workflow.py`
- `tools/run_cap_expansion.py`
- `tools/summarize_cap_expansion.py`
- `.github/workflows/cap-expansion.yml`
- `docs/methodology/cap_expansion_study_v1.md`

**Reason for the decision:** The hosted reach-only diagnostic found paired cap
sensitivity but did not establish calibration, certification, bootstrap, or
practical-runtime behavior. The full-workflow comparison preserves the frozen
v0.1 estimand while testing whether the availability gains persist under the
complete workflow.
```

After the implementation commit and hosted run, add the exact implementation
and workflow-run commit IDs to the same traceability block in a separate
decision-log commit.

- [ ] **Step 1: Write documentation assertions**

```python
def test_methodology_page_points_to_frozen_implementation_contract() -> None:
    text = Path("docs/methodology/cap_expansion_study_v1.md").read_text(encoding="utf-8")
    for required in ("bb7a851", "1,620", "right-censored", "jointly-valid", "cap-expansion.yml"):
        assert required in text
```

- [ ] **Step 2: Run the documentation test and confirm the page is absent**

Run: `python -m pytest tests/test_cap_expansion_summary.py::test_methodology_page_points_to_frozen_implementation_contract -q`

Expected: FAIL because the canonical methodology page does not yet exist.

- [ ] **Step 3: Add the methodology page and ADR traceability block**

Use the exact values from the approved specification and link to the files in
the file map. Do not add empirical claims before the manual workflow is run.

- [ ] **Step 4: Run documentation checks**

Run: `python -m pytest tests/test_cap_expansion_summary.py::test_methodology_page_points_to_frozen_implementation_contract -q` and `git diff --check`.

Expected: both pass with no placeholders or uncommitted generated artifacts.

- [ ] **Step 5: Commit the methodology/provenance slice**

```bash
git add docs/methodology/cap_expansion_study_v1.md docs/development/decisions.md tests/test_cap_expansion_summary.py
git commit -m "docs: trace cap expansion design and review files"
```

---

### Task 6: Add the manual hosted validation workflow

**Files:**
- Create: `.github/workflows/cap-expansion.yml`
- Modify: `tests/test_cap_expansion_summary.py`

**Interfaces:**
- The workflow is named `SDNA paired cap-expansion validation` and declares only `workflow_dispatch`.
- It runs on `ubuntu-latest` with Python `3.11`, installs `.[dev]` under `constraints-ci.txt`, executes the committed configuration, summarizes and validates the artifact, and uploads all files with 90-day retention.

The workflow must:

1. check out the reviewed commit;
2. create an artifact directory and copy the config;
3. record `GITHUB_WORKFLOW`, `GITHUB_RUN_ID`, `GITHUB_EVENT_NAME`,
   `GITHUB_REF`, and `GITHUB_SHA`;
4. run `python -m tools.run_cap_expansion`;
5. run `python -m tools.summarize_cap_expansion ... --validate`;
6. emit a visible warning or summary line when `budget_exceeded=true` without
   deleting the artifact or changing the job's technical validation result;
7. upload the CSV, metadata, config, manifest/checksum, JSON summary, Markdown
   report, command record, and GitHub provenance with `if: always()`; and
8. remain manual-only, with no `schedule`, `push`, or `pull_request` trigger.

Use a 20-minute job watchdog so a run that passes the 15-minute operational
budget can still finish summary/validation and upload its retained artifact.

- [ ] **Step 1: Add a static workflow-contract test**

```python
def test_cap_expansion_workflow_is_manual_only() -> None:
    text = Path(".github/workflows/cap-expansion.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "pull_request:" not in text
    assert "tools.run_cap_expansion" in text
    assert "--validate" in text
```

- [ ] **Step 2: Run the test and confirm the workflow is absent**

Run: `python -m pytest tests/test_cap_expansion_summary.py::test_cap_expansion_workflow_is_manual_only -q`

Expected: FAIL because the manual cap-expansion workflow does not yet exist.

- [ ] **Step 3: Implement the workflow and artifact upload**

Mirror the repository's established primary/reach-boundary artifact pattern,
using the cap-expansion commands and 90-day retention. Keep the command
recorded in the artifact so an independent reviewer can reproduce the run.

- [ ] **Step 4: Run static checks**

Run: `python -m pytest tests/test_cap_expansion_summary.py -q` and
`ruff check src tests simulations tools`.

Expected: all focused tests pass and the workflow text contains no recurring or
PR trigger.

- [ ] **Step 5: Commit the hosted-workflow slice**

```bash
git add .github/workflows/cap-expansion.yml tests/test_cap_expansion_summary.py
git commit -m "ci: add manual paired cap expansion validation"
```

---

### Task 7: Execute, verify, and record the implementation decision

**Files:**
- Modify: `docs/development/decisions.md`
- Create outside Git: hosted cap-expansion artifact directory and downloaded evidence bundle

**Interfaces:**
- The hosted run is dispatched manually from the implementation commit.
- The final decision-log entry records the exact implementation commit, exact GitHub Actions run ID/commit, artifact name/checksum, technical validation result, runtime/budget result, and whether cap 2 remains the baseline.

- [ ] **Step 1: Run the full local test/lint suite before dispatch**

Run: `python -m pytest -q` and `ruff check src tests simulations tools`.

Expected: all tests pass and Ruff reports no violations.

- [ ] **Step 2: Run a reduced local cap-expansion rehearsal**

Use a temporary one-cell manifest with one replication, calibration `1`, and
bootstrap `2`. Run the runner, summarizer, and validator end to end. Verify
that all three arms share the same data digest and child seeds, stage statuses
are explicit, and the validator rejects a deliberately modified digest.
Delete only the temporary artifact directory after inspection; do not delete
tracked files or the committed configuration.

- [ ] **Step 3: Commit any final test-only or documentation corrections**

Run `git diff --check`, inspect `git status --short`, and commit only source,
tests, workflow, and documentation changes. Record the resulting commit hash
before dispatching Actions.

- [ ] **Step 4: Dispatch the manual GitHub Actions workflow**

Run the workflow on the recorded implementation commit. Confirm that the
artifact contains 1,620 rows, three balanced arms, the expected checksum,
paired data digests/seeds, summaries, and provenance.

- [ ] **Step 5: Add the post-run decision-log entry**

Record the exact implementation commit and exact hosted run ID in ADR-022 or
a new sequential ADR. Include the artifact name/checksum, technical status,
runtime and budget status, transition counts, denominator/censoring findings,
and the explicit cap decision. If the run is technically valid but exceeds
the 15-minute operational budget, retain the artifact and state that no
optimization or cap promotion follows from that result.

- [ ] **Step 6: Commit the post-run traceability record**

```bash
git add docs/development/decisions.md
git commit -m "docs: record cap expansion validation evidence"
```

---

## Self-review checklist

- The manifest task covers exact arms, matrix values, row count, pairing keys, and checksum.
- The workflow task covers every full-workflow stage and keeps error, unreached, censored, and rejected-resample states separate.
- The runner task creates each dataset once and records data/child seeds and digest equality across caps.
- The summary task covers primary transitions, pooled metrics, jointly-valid pair metrics, denominators, errors, censoring, truth-aware false flags, comparator behavior, and runtime.
- The documentation task prevents unexecuted empirical claims and gives an independent reviewer the originating decision commit and exact files to inspect.
- The Actions task is manual-only, uploads artifacts even on validation failure, and preserves budget exceedances.
- The final task records the implementation commit and hosted run ID in the decision log after they exist.
- No task changes the v0.1 production default or adds a cap-selection heuristic.
