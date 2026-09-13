# Task 23 Reach-Boundary Study Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the pre-specified reach-only diagnostic that separates search-cap censoring, target difficulty, and heavy-tail/collinearity stress before any estimator optimization.

**Architecture:** Keep the frozen primary runner and estimator unchanged. Add a separate manifest-driven diagnostic runner that expands the seven declared arms, reuses paired seeds for cap comparisons, records numerical diagnostics and explicit failures, and writes a dedicated artifact schema. Summaries will compare paired reach transitions rather than pooling rows across arms.

**Tech Stack:** Python 3.11+, NumPy, pytest, JSON/CSV, existing `sdna.fragility`, `sdna.estimation`, and simulation DGP APIs.

**Spec:** `docs/methodology/reach_boundary_study_v1.md`

## Global Constraints

- The v0.1 primary matrix and `simulations/configs/falsification_pilot.json` remain unchanged.
- The baseline arm uses root seed `20260910`, the six primary scenarios, `N=[50,100,150]`, `p=[5,10,20]`, ten replications, target `0.5`, and `search_cap=2`.
- Cap arms use the same generated data as `baseline_cap2` for each paired row.
- Reach-only outputs must not be presented as calibration, bootstrap, AUC, or exact-minimum evidence.
- Unreached searches, numerical failures, and certified results remain distinct states.
- No production optimization is permitted in this task.

---

### Task 1: Add the frozen reach-boundary arm manifest

**Files:**
- Create: `simulations/configs/reach_boundary_v1.json`
- Create: `tools/reach_boundary_manifest.py`
- Test: `tests/test_reach_boundary.py`

**Interfaces:**
- The manifest must declare the seven arm names, scenario scope, target, search cap, and DGP overrides exactly as listed in `docs/methodology/reach_boundary_study_v1.md`.
- The loader must reject duplicate arm names, undeclared scenario names, nonpositive caps, target values outside `(0, 1)`, and missing baseline arms.

- [ ] **Step 1: Write manifest validation tests**

Assert that the manifest expands to 2,430 expected rows and that the cap arms have identical scenario/cell/replication keys.

- [ ] **Step 2: Run the focused tests and confirm the missing manifest failure**

Run: `pytest tests/test_reach_boundary.py -q`

Expected: FAIL because the reach-boundary manifest and loader do not exist.

- [ ] **Step 3: Add the JSON manifest and loader**

Use explicit arm records, not implicit name parsing, and preserve the primary configuration values in the manifest.

- [ ] **Step 4: Run the focused tests**

Run: `pytest tests/test_reach_boundary.py -q`

Expected: PASS for manifest expansion and validation.

- [ ] **Step 5: Commit**

```bash
git add simulations/configs/reach_boundary_v1.json tests/test_reach_boundary.py
git commit -m "test: freeze reach-boundary study arms"
```

---

### Task 2: Implement the reach-only runner and explicit diagnostics

**Files:**
- Create: `tools/run_reach_boundary.py`
- Modify: `tests/test_reach_boundary.py`

**Interfaces:**
- Add `run_reach_boundary(config_path, output_path) -> None`.
- Add `expand_reach_boundary_jobs(manifest) -> list[dict[str, object]]`.
- Each output row must include arm identity, paired row key, seed, target, cap, reach status, greedy count, trajectory endpoint, fit diagnostics, elapsed seconds, error status, and error message.

- [ ] **Step 1: Write a failing paired-seed and failure-preservation test**

Use a small one-cell manifest fixture. Assert that cap arms receive the same generated data and that a forced numerical exception is written as an error row rather than `reached=False`.

- [ ] **Step 2: Run the focused test**

Run: `pytest tests/test_reach_boundary.py::test_runner_preserves_pairing_and_failures -q`

Expected: FAIL because the runner does not exist.

- [ ] **Step 3: Implement deterministic arm expansion and execution**

Generate each paired dataset once for cap arms, call `greedy_fragility` with the declared target/cap, read `NetworkDiagnostics`, and catch only row-level numerical/runtime exceptions needed to preserve the artifact. Do not catch validation errors that indicate an invalid manifest.

- [ ] **Step 4: Implement heavy-tail and collinearity overrides**

Pass degrees of freedom only for `heavy_df8` and adjacent correlation only for the two collinearity arms. Reject an override on an unrelated scenario.

- [ ] **Step 5: Run focused tests**

Run: `pytest tests/test_reach_boundary.py -q`

Expected: PASS with deterministic row keys, pairing, diagnostics, and explicit failures.

- [ ] **Step 6: Commit**

```bash
git add tools/run_reach_boundary.py tests/test_reach_boundary.py
git commit -m "feat: add reach-boundary diagnostic runner"
```

---

### Task 3: Add paired transition summaries and artifact validation

**Files:**
- Create: `tools/summarize_reach_boundary.py`
- Modify: `tests/test_reach_boundary.py`

**Interfaces:**
- Add `summarize_reach_boundary(input_csv, json_output, markdown_output) -> None`.
- Add `validate_reach_boundary(results_csv, metadata_json, summary_json, manifest_path) -> None`.
- Summaries must report `0 -> 0`, `0 -> 1`, `1 -> 0`, and `1 -> 1` transitions, reach differences, censoring, failures, numerical diagnostics, and runtime by arm/scenario/cell.

- [ ] **Step 1: Write hand-computable transition tests**

Use four baseline/candidate pairs with two newly reached rows and assert exact transition counts and denominators. Include one error row and assert it is not counted as censoring.

- [ ] **Step 2: Run the focused tests and confirm missing-summary failure**

Run: `pytest tests/test_reach_boundary.py -q`

Expected: FAIL because the summary and validator do not exist.

- [ ] **Step 3: Implement finite, paired summaries**

Match rows by the declared key, refuse duplicate or missing pair keys, and preserve descriptive nulls where a metric has no valid rows. Do not compute inferential p-values or pool across nonpaired DGP arms.

- [ ] **Step 4: Implement manifest/provenance/schema validation**

Require exactly 2,430 rows, the declared arm counts, finite successful diagnostics, explicit error fields, and metadata containing commit, Python, NumPy, package, manifest checksum, and runtime.

- [ ] **Step 5: Run summary tests and lint**

Run: `pytest tests/test_reach_boundary.py -q` and `ruff check tools tests simulations`.

Expected: all focused tests and Ruff checks pass.

- [ ] **Step 6: Commit**

```bash
git add tools/summarize_reach_boundary.py tests/test_reach_boundary.py
git commit -m "feat: summarize paired reach-boundary transitions"
```

---

### Task 4: Execute and review the pre-specified diagnostic artifact

**Files:**
- Modify: `.github/workflows/reach-boundary.yml`
- Modify: `docs/development/decisions.md`
- Create: `docs/development/reach_boundary_evidence_v1.md`

**Interfaces:**
- The workflow must be manual-only, use Python 3.11, run the declared manifest without smoke caps, validate the artifact, and upload results with 90-day retention.
- The evidence report must show the exact hosted run, arm counts, paired transition tables, numerical diagnostics, runtime, and limitations without selecting favorable cells.

- [ ] **Step 1: Add the manual workflow and run it locally first**

Run the full local artifact with the machine-readable manifest, then validate its row count and deterministic baseline status before dispatching Actions.

- [ ] **Step 2: Run the hosted workflow**

Retain the artifact and record the run ID, commit, environment, and manifest checksum.

- [ ] **Step 3: Write the evidence report and decision entry**

Choose among retaining cap 2, drafting a cap-expansion study, or narrowing the declared scope only after displaying all paired transitions and diagnostics. Do not modify the primary matrix in the same commit.

- [ ] **Step 4: Run full verification**

Run: `pytest -q`, `ruff check src tests simulations tools`, `mypy --python-version 3.12 src/sdna`, and `git diff --check`.

- [ ] **Step 5: Commit the artifact interpretation**

```bash
git add .github/workflows/reach-boundary.yml docs/development/reach_boundary_evidence_v1.md docs/development/decisions.md
git commit -m "docs: record reach-boundary study evidence"
```
