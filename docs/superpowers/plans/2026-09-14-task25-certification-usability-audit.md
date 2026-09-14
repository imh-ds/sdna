# Task 25: Certification usability audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit and, when necessary, instrument the paired cap-expansion workflow to determine whether rows newly reached by caps 3 and 4 are certifiable usable evidence.

**Architecture:** Phase A is a read-only audit of the accepted Task 24 artifact and identifies the exact cap-2-unreached/candidate-reached pairs. Phase B is a separate, manual-only runner that reuses the frozen Task 24 matrix and deterministic paired data while adding certification diagnostics; it is accepted only when its original Task 24 fields reproduce and its diagnostic schema validates. The production cap-2 workflow and Task 24 artifact remain unchanged.

**Tech Stack:** Python 3.11+, NumPy, pytest, Ruff, JSON/CSV artifacts, and manual GitHub Actions workflows.

**Spec:** `docs/superpowers/specs/2026-09-14-task25-certification-usability-audit-design.md`

## Global Constraints

- The v0.1 production baseline remains `search_cap=2`.
- Task 24’s three arms remain `baseline_cap2`, `cap3`, and `cap4`.
- The Task 24 matrix remains six scenarios, `N=[50,100,150]`, `p=[5,10,20]`, ten replications, and 1,620 rows.
- The global seed remains `20260910`, with the existing deterministic data/calibration/bootstrap seed derivation.
- The fragility target remains relative target `0.5`.
- The certification combination budget remains `1000`.
- Calibration, Wald, bootstrap, shrinkage, and right-censored tail behavior remain unchanged.
- The hosted operational ceiling remains `900` seconds.
- Phase A reads the Task 24 artifact and never rewrites it.
- Phase B is manual-only, has no recurring schedule, and is not a pull-request gate.
- No cap-selection score, post-hoc threshold, algorithmic optimization, or workload increase is introduced.

---

## Files and responsibilities

- Create `simulations/configs/certification_usability_v1.json`: immutable reference to the Task 24 source run, source manifest checksum, candidate caps, primary endpoint, and diagnostic reason vocabulary.
- Create `tools/certification_usability_manifest.py`: load and validate the Task 25 audit manifest and its pinned Task 24 source identity.
- Create `tools/audit_certification_usability.py`: validate the Task 24 input artifact, identify exact `U_to_R(3)` and `U_to_R(4)` pairs, and write the Phase A JSON/Markdown audit.
- Modify `simulations/full_workflow.py`: expose certification diagnostics without changing stage behavior or existing callers.
- Modify `tools/run_cap_expansion.py`: support an explicit instrumentation mode while preserving the existing default Task 24 field list and CLI output.
- Create `tools/run_certification_usability.py`: invoke the shared paired runner with certification instrumentation enabled.
- Create `tools/summarize_certification_usability.py`: summarize `U_to_R` certification yield, reason counts, downstream status populations, stratified denominators, and provenance; validate the instrumented artifact against the Task 24 reference.
- Create `tests/test_certification_usability_manifest.py`: manifest and source-identity tests.
- Create `tests/test_certification_usability_audit.py`: pair extraction, denominator, unavailable-field, and audit-report tests.
- Modify `tests/test_full_workflow.py`: certification diagnostic status tests.
- Modify `tests/test_cap_expansion_runner.py`: default-schema compatibility and instrumented-schema tests.
- Create `tests/test_certification_usability_summary.py`: primary endpoint, reason, reproduction, tampering, and denominator tests.
- Create `tests/test_certification_usability_workflow.py`: manual-only workflow and methodology contract tests.
- Create `.github/workflows/certification-usability.yml`: manual-only Phase A/Phase B workflow with reference-artifact download and 90-day artifact retention.
- Create `docs/methodology/certification_usability_study_v1.md`: user-facing scope, endpoint, limits, and interpretation contract.
- Modify `docs/development/decisions.md`: record the Task 25 design/implementation provenance and, after hosted execution, the exact run and resulting mechanism.
- Modify `.gitignore`: ignore `.task25-artifacts/` while leaving all committed source, tests, plans, specifications, and decision records tracked.

## Reference identities

The new manifest must pin these already accepted Task 24 values:

```json
{
  "source_run_id": "34871220664",
  "source_commit": "338b0d95cdb312b2805affb0de458e06508d80f0",
  "source_artifact": "sdna-cap-expansion-34871220664",
  "source_manifest_checksum": "415576f1fec5ccd2a47e0ad411d29e4d48c6e8e370609ae495ccc877fe74e974",
  "source_results_sha256": "110d0b4f266b253251ac1a64bb4195b61722008d426b74c75802d3de57b43d87"
}
```

The audit manifest must also declare `candidate_caps: [3, 4]`,
`primary_population: "baseline_unreached_candidate_reached"`,
`primary_endpoint: "candidate_certification_yield"`,
`instrumented_schema_version: 1`, and the exact reason values
`not_applicable_unreached`, `not_applicable_prior_error`, `certified`,
`combination_budget_exhausted`, `not_certified_other`, and `error`.

### Task 1: Freeze the audit manifest and source contract

**Files:**
- Create: `simulations/configs/certification_usability_v1.json`
- Create: `tools/certification_usability_manifest.py`
- Create: `tests/test_certification_usability_manifest.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces `load_certification_usability_manifest(path: str | Path) -> dict[str, Any]`.
- Produces `certification_usability_manifest_checksum(manifest: Mapping[str, Any]) -> str`.
- Consumes `tools.cap_expansion_manifest.manifest_checksum` and the pinned Task 24 identity above.

- [ ] **Step 1: Write failing manifest tests**

Add tests that load the committed JSON, assert the exact source run/commit/artifact/checksum values, assert candidate caps `[3, 4]`, assert the primary population and endpoint names, assert the six reason values, and assert that mutations to the source checksum, source run ID, candidate caps, or reason list raise `ValueError`.

- [ ] **Step 2: Run the manifest tests to verify they fail**

Run:

```powershell
& 'C:\tmp\redana-python312\python.exe' -c "import sys; sys.path[0:0]=[r'.',r'src']; import pytest; raise SystemExit(pytest.main(['-q','tests/test_certification_usability_manifest.py']))"
```

Expected: FAIL because the manifest loader and configuration do not exist.

- [ ] **Step 3: Add the immutable JSON manifest and loader**

The loader must require the exact reference identities and values above, reject unknown reason values, canonicalize the JSON with sorted keys and compact separators for its checksum, and return a fresh dictionary. It must not inspect or modify the external artifact.

- [ ] **Step 4: Run the manifest tests to verify they pass**

Run the same pytest command. Expected: all manifest tests pass.

- [ ] **Step 5: Add the generated-artifact ignore rule and commit**

Add only `.task25-artifacts/` to `.gitignore`, then run:

```powershell
git add simulations/configs/certification_usability_v1.json tools/certification_usability_manifest.py tests/test_certification_usability_manifest.py .gitignore
git commit -m "feat: freeze certification usability audit manifest"
```

### Task 2: Implement the Phase A row-level audit

**Files:**
- Create: `tools/audit_certification_usability.py`
- Create: `tests/test_certification_usability_audit.py`

**Interfaces:**
- Produces `identify_newly_reached_pairs(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]` with keys `cap3` and `cap4`.
- Produces `audit_certification_usability(results_csv: str | Path, metadata_json: str | Path, summary_json: str | Path, source_manifest: str | Path, audit_manifest: str | Path, output_json: str | Path, output_markdown: str | Path) -> None`.
- Consumes `validate_cap_expansion` before extracting any pairs.

- [ ] **Step 1: Write failing pair-identification tests**

Use a three-key synthetic fixture with one cap-2-unreached/cap-3-reached pair, one cap-2-unreached/cap-4-reached pair, and one reached-to-reached pair. Add one newly reached row with a downstream error and assert it remains in the primary denominator. Assert duplicate keys, missing arms, and non-`reached` candidate rows are rejected. Test `identify_newly_reached_pairs` directly with the reduced fixture; the production `validate_cap_expansion` call remains reserved for a complete 1,620-row source artifact.

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:

```powershell
& 'C:\tmp\redana-python312\python.exe' -c "import sys; sys.path[0:0]=[r'.',r'src']; import pytest; raise SystemExit(pytest.main(['-q','tests/test_certification_usability_audit.py']))"
```

Expected: FAIL because the audit extractor does not exist.

- [ ] **Step 3: Implement exact `U_to_R` extraction**

Load and validate all four Task 24 source files with `validate_cap_expansion`. Group rows by the frozen pairing key, require one row for each of the three arms, select cap-2 `fragility_status=unreached` and candidate `fragility_status=reached`, and return one record per candidate cap containing both rows’ keys, seeds, digest, statuses, certification fields, downstream fields, and error fields. Do not filter on certification or workflow success.

- [ ] **Step 4: Implement the Phase A report**

Write JSON containing the input artifact identity, audit commit, exact `U_to_R` counts, per-row records, and an `unavailable_fields` list containing `certification_combinations_checked`, `certification_combination_budget`, and `certification_failure_reason`. Write Markdown with the same denominators and a clear statement that the Task 24 CSV cannot distinguish certification-budget exhaustion from another completed non-certification without instrumentation.

- [ ] **Step 5: Run the focused tests to verify they pass**

Run the same pytest command. Expected: all audit tests pass, including the denominator and unavailable-field assertions.

- [ ] **Step 6: Commit the Phase A audit**

```powershell
git add tools/audit_certification_usability.py tests/test_certification_usability_audit.py
git commit -m "feat: add certification usability artifact audit"
```

### Task 3: Add non-invasive certification diagnostics to the workflow

**Files:**
- Modify: `simulations/full_workflow.py`
- Modify: `tests/test_full_workflow.py`

**Interfaces:**
- Extends the workflow result with `certification_combinations_checked: int | None`, `certification_combination_budget: int`, `certification_budget_exhausted: bool`, and `certification_failure_reason: str`.
- Existing callers continue to receive their current behavior; `simulations.run_simulation` continues to select its existing v0.1 CSV fields.

- [ ] **Step 1: Write failing workflow diagnostic tests**

Add tests for four states: unreached search produces `not_applicable_unreached`; successful certification produces `certified` and a checked-count value; current `not_certified` behavior produces `combination_budget_exhausted` and `True`; and a prior fit/fragility failure produces `not_applicable_prior_error` without pretending certification was attempted. Add a certification-exception test that produces `error`.

- [ ] **Step 2: Run the focused workflow tests to verify they fail**

Run:

```powershell
& 'C:\tmp\redana-python312\python.exe' -c "import sys; sys.path[0:0]=[r'.',r'src']; import pytest; raise SystemExit(pytest.main(['-q','tests/test_full_workflow.py']))"
```

Expected: FAIL because the diagnostic keys are absent.

- [ ] **Step 3: Add diagnostics without changing stage execution**

Set the configured budget at workflow start. Record `combinations_checked` from the certification result. Map the existing certification contract’s false result to `combination_budget_exhausted`; map successful certification to `certified`; map an exception to `error`; map unreached search to `not_applicable_unreached`; and map a prior stage error to `not_applicable_prior_error`. Keep the existing stage statuses and endpoint values unchanged.

- [ ] **Step 4: Run focused and existing workflow tests**

Run the full `tests/test_full_workflow.py` command above. Expected: all tests pass, including the pre-existing failure-state tests.

- [ ] **Step 5: Commit the workflow diagnostics**

```powershell
git add simulations/full_workflow.py tests/test_full_workflow.py
git commit -m "feat: expose certification usability diagnostics"
```

### Task 4: Preserve the Task 24 runner and add the instrumented runner

**Files:**
- Modify: `tools/run_cap_expansion.py`
- Create: `tools/run_certification_usability.py`
- Modify: `tests/test_cap_expansion_runner.py`

**Interfaces:**
- Preserves `run_cap_expansion(config_path, output_path)` with the original `CAP_EXPANSION_FIELDNAMES` when instrumentation is disabled.
- Adds `run_cap_expansion(config_path, output_path, *, include_certification_diagnostics: bool = False) -> None`.
- Produces `run_certification_usability(config_path: str | Path, output_path: str | Path) -> None`, which calls the shared runner with instrumentation enabled.

- [ ] **Step 1: Write failing schema-compatibility tests**

Assert the default runner field list is byte-for-byte unchanged. Assert the instrumented field list appends the four diagnostic fields. Assert data-error rows contain valid diagnostic values and that every normal row carries the declared budget and one reason value.

- [ ] **Step 2: Run runner tests to verify they fail**

Run:

```powershell
& 'C:\tmp\redana-python312\python.exe' -c "import sys; sys.path[0:0]=[r'.',r'src']; import pytest; raise SystemExit(pytest.main(['-q','tests/test_cap_expansion_runner.py']))"
```

Expected: FAIL because the optional instrumented schema does not exist.

- [ ] **Step 3: Add the explicit instrumentation mode**

Keep the existing default field list, metadata format, seed map, dataset generation, and CLI unchanged. Select `CAP_EXPANSION_FIELDNAMES +` the four diagnostics only when the new keyword is true. Ensure error rows use the same diagnostic reason contract as normal rows.

- [ ] **Step 4: Add the instrumented CLI**

Implement `python -m tools.run_certification_usability <config> <output>` as a thin wrapper around the shared runner. It must use `simulations/configs/cap_expansion_v1.json` and write the instrumented CSV plus adjacent metadata; it must not alter the frozen source configuration.

- [ ] **Step 5: Run runner tests to verify they pass**

Run the same pytest command. Expected: all runner tests pass and existing Task 24 schema tests remain green.

- [ ] **Step 6: Commit the instrumented runner**

```powershell
git add tools/run_cap_expansion.py tools/run_certification_usability.py tests/test_cap_expansion_runner.py
git commit -m "feat: add instrumented certification usability runner"
```

### Task 5: Summarize and validate the certification-usability evidence

**Files:**
- Create: `tools/summarize_certification_usability.py`
- Create: `tests/test_certification_usability_summary.py`

**Interfaces:**
- Produces `summarize_certification_usability(rows: Sequence[Mapping[str, Any]], manifest: Mapping[str, Any], audit_manifest: Mapping[str, Any]) -> dict[str, Any]`.
- Produces `validate_certification_usability(instrumented_results_csv: str | Path, instrumented_metadata_json: str | Path, summary_json: str | Path, source_results_csv: str | Path, source_metadata_json: str | Path, source_summary_json: str | Path, source_manifest: str | Path, audit_manifest: str | Path) -> None`.
- Produces a CLI accepting the eight paths above plus `--validate` and writing adjacent Markdown and artifact checksums.

- [ ] **Step 1: Write failing summary tests**

Build a paired synthetic fixture with known `U_to_R(3)` and `U_to_R(4)` rows. Assert the primary numerator and denominator, reason counts, downstream status counts, and scenario/`N`/`p` denominators. Add tests that reject a changed pairing key, seed, digest, original stage status, diagnostic reason, summary value, or artifact checksum. Add a test that accepts only numeric summary differences within the established `1e-12` cross-runtime tolerance.

- [ ] **Step 2: Run summary tests to verify they fail**

Run:

```powershell
& 'C:\tmp\redana-python312\python.exe' -c "import sys; sys.path[0:0]=[r'.',r'src']; import pytest; raise SystemExit(pytest.main(['-q','tests/test_certification_usability_summary.py']))"
```

Expected: FAIL because the summarizer and validator do not exist.

- [ ] **Step 3: Implement the primary and secondary summaries**

Use the Phase A `U_to_R` rule on the instrumented rows. For each candidate cap report `certified / U_to_R denominator`, all diagnostic reason counts, combination counts, downstream status populations, error stages, and stratified denominators. Include exact pair keys and source/ instrumented provenance. Keep cap-2 unreached values out of finite-valued metric calculations.

- [ ] **Step 4: Implement reference reproduction validation**

Validate the instrumented artifact’s 1,620 rows, 540-row arms, key uniqueness, deterministic seeds, paired digests, source manifest checksum, diagnostic schema, artifact checksums, and summary. Compare every original Task 24 field except `elapsed_seconds` row-by-row against the downloaded reference artifact: statuses and categorical values must match exactly; finite numeric endpoint values must match within `1e-12`; nullability must match exactly. Validate runtime fields separately as nonnegative reported values. Reject any mismatch rather than repairing it.

- [ ] **Step 5: Implement JSON and Markdown output**

Write the machine-readable summary, human-readable report, and metadata checksums. State that Phase B is a reproduction with diagnostics, not independent evidence, and state the decision rule that no cap is promoted by this report.

- [ ] **Step 6: Run summary tests to verify they pass**

Run the same pytest command. Expected: all summary and validator tests pass.

- [ ] **Step 7: Commit the summary and validator**

```powershell
git add tools/summarize_certification_usability.py tests/test_certification_usability_summary.py
git commit -m "feat: validate certification usability evidence"
```

### Task 6: Add methodology documentation and the manual workflow

**Files:**
- Create: `docs/methodology/certification_usability_study_v1.md`
- Create: `.github/workflows/certification-usability.yml`
- Modify: `docs/development/decisions.md`

**Interfaces:**
- The workflow is manually dispatched with `workflow_dispatch` only.
- The workflow downloads Task 24 artifact `sdna-cap-expansion-34871220664` using the pinned run ID and `GH_TOKEN`, runs Phase A, runs the instrumented Phase B runner, validates against the downloaded reference, and uploads all outputs with 90-day retention even on failure.

- [ ] **Step 1: Write documentation/workflow contract tests**

Assert the methodology page names the `U_to_R` population, certification yield, fixed Task 24 settings, reason vocabulary, cap-2 decision, and Phase A/Phase B distinction. Assert the workflow contains `workflow_dispatch`, the pinned run ID, `tools.audit_certification_usability`, `tools.run_certification_usability`, `--validate`, and artifact upload with `if: always()`. Assert it contains neither `schedule:` nor `push:` nor `pull_request:`.

- [ ] **Step 2: Run the contract tests to verify they fail**

Run:

```powershell
& 'C:\tmp\redana-python312\python.exe' -c "import sys; sys.path[0:0]=[r'.',r'src']; import pytest; raise SystemExit(pytest.main(['-q','tests/test_certification_usability_workflow.py']))"
```

Expected: FAIL because the documentation and workflow do not exist.

- [ ] **Step 3: Write the methodology page**

Document the study question, exact primary denominator, diagnostic reason meanings, unavailable Phase A fields, unchanged Task 24 settings, 900-second ceiling, artifact contract, and non-promotion interpretation. Do not include empirical Phase B findings before a hosted run exists.

- [ ] **Step 4: Write the manual-only workflow**

Use Python 3.11, install the pinned CI/development dependencies, download the reference artifact, run Phase A, run the instrumented runner, summarize/validate, write a command record, and upload CSV, metadata, manifest, summaries, audit output, command record, and report. Set artifact retention to 90 days and preserve outputs on failure.

- [ ] **Step 5: Add the Task 25 decision entry**

Record the approved specification commit, implementation plan commit, files, the fact that Phase A precedes conditional Phase B, the exact primary endpoint, and the prohibition on cap promotion. Leave the hosted run/result fields explicitly pending until execution exists.

- [ ] **Step 6: Run documentation/workflow tests to verify they pass**

Run the same pytest command. Expected: all contract tests pass.

- [ ] **Step 7: Commit the documentation and workflow**

```powershell
git add docs/methodology/certification_usability_study_v1.md .github/workflows/certification-usability.yml docs/development/decisions.md tests/test_certification_usability_workflow.py
git commit -m "ci: specify certification usability validation workflow"
```

### Task 7: Run the complete local validation and prepare the hosted study

**Files:**
- Modify: `docs/development/decisions.md`
- Create outside Git: `.task25-artifacts/`

- [ ] **Step 1: Run the complete local checks**

Run:

```powershell
& 'C:\tmp\redana-python312\python.exe' -c "import sys; sys.path[0:0]=[r'.',r'src']; import pytest; raise SystemExit(pytest.main(['-q','--basetemp',r'.pytest-tmp']))"
& 'C:\tmp\redana-batch-ruff\bin\ruff.exe' check src tests examples benchmarks simulations tools
& 'C:\tmp\redana-python312\python.exe' -m compileall -q src simulations tools tests
```

Expected: all tests pass, Ruff reports no violations, and compilation exits successfully. Remove `.pytest-tmp` after verification.

- [ ] **Step 2: Run a reduced helper-level rehearsal**

Use a synthetic three-key reference/instrumented fixture with one newly reached pair for each candidate cap, one reached-to-reached pair, and one downstream-error row. Run the pair extractor and summarizer against that fixture and exercise their deliberate tamper rejection checks. Run the complete production validator only against the downloaded 1,620-row Task 24 artifact; do not pass a reduced manifest to the production runner or production validator. The frozen manifest loader must continue to reject any matrix other than the declared 1,620-row study. Keep temporary files under `.task25-artifacts/` and do not change the committed frozen manifests.

- [ ] **Step 3: Record the final implementation commit**

Run `git status --short`, `git diff --check`, and `git rev-parse HEAD`. Record the implementation commit in ADR-024 before dispatching the hosted workflow.

- [ ] **Step 4: Dispatch the manual workflow**

Dispatch `.github/workflows/certification-usability.yml` from the implementation commit. Confirm the run downloads the pinned Task 24 artifact, identifies the published `U_to_R` rows, generates 1,620 instrumented rows, validates source reproduction, and uploads the complete evidence bundle.

- [ ] **Step 5: Add hosted findings without changing the protocol**

Record the exact Actions run ID, merge/implementation commit, artifact name, checksums, runtime, budget status, `U_to_R` counts, certification yields, reason counts, and downstream outcomes. State whether the evidence identifies a certification-budget, certification-error, or downstream bottleneck. Do not add a new threshold or rerun with changed settings in response to the result.

- [ ] **Step 6: Commit the hosted traceability record**

```powershell
git add docs/development/decisions.md docs/methodology/certification_usability_study_v1.md
git commit -m "docs: record certification usability evidence"
```

## Self-review checklist

- The plan implements every Phase A and Phase B requirement in the approved specification.
- The exact `U_to_R` denominator is defined once and reused by the audit, summary, validator, documentation, and workflow.
- The existing Task 24 runner remains byte-for-byte compatible by default.
- The four new diagnostics distinguish unreached, prior-error, certified, budget-exhausted, other non-certification, and certification-error states.
- The reference reproduction compares original fields and refuses post-hoc repair.
- Numeric cross-runtime tolerance is limited to `1e-12`; keys, statuses, nullability, seeds, digests, checksums, and denominators remain strict.
- Phase A and Phase B are not pooled as independent evidence.
- The workflow is manual-only and uploads artifacts on failure.
- No task changes the v0.1 production cap, estimator, target, workload budgets, or tail treatment.
