# Task 13 Falsification Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate all six truth-aware simulation scenarios, row-level falsification measurements, benchmark-derived budgets, and scenario-level summaries without changing the statistical estimators.

**Architecture:** Extend the existing configuration-driven runner with a small scenario registry and explicit workload settings. Preserve the current row-oriented CSV format while adding auditable fields. Keep calculations that require multiple rows in `summarize.py`, where censored and undefined values can be filtered explicitly.

**Tech Stack:** Python 3.11+, NumPy, pytest, JSON/CSV, existing SDNA estimation/fragility/calibration APIs.

**Spec:** `docs/superpowers/specs/2026-09-11-task13-falsification-design.md`

## Global Constraints

- The v0.1 data boundary remains complete continuous independent observations.
- Exact LOO remains authoritative; analytic influence is an approximation used for ranking.
- Greedy fragility remains an upper bound unless certification succeeds.
- Censored fragility and undefined summary metrics remain explicit `None`/`null` values.
- Task 19 benchmark results define the pilot limits; do not optimize production numerical routines in this task.
- Bootstrap outputs remain labeled shrinkage-bootstrap outputs, not `bootnet` results.

---

## Shared test fixtures

The tests introduced by this plan use these concrete helpers in the relevant test modules:

```python
def minimal_config_with_single_case() -> dict[str, object]:
    return {
        "seed": 123,
        "replications": 1,
        "n_values": [8],
        "p_values": [3],
        "scenarios": ["single_influential_case"],
        "contamination_cases": [1],
        "fragility_targets": [0.5],
        "certification_combination_budget": 20,
        "calibration_simulations": 1,
        "bootstrap_samples": 2,
        "bootstrap_confidence": 0.95,
    }


def hand_computable_falsification_rows() -> list[dict[str, object]]:
    common = {
        "N": 50, "p": 5, "greedy_fragility_50": 2, "exact_fragility_50": 2,
        "certified": True, "reached": True, "reference_tail_probability": 0.02,
        "wald_z": 1.0, "influence_top_k_precision": 0.5,
        "influence_top_k_recall": 0.5, "first_planted_reciprocal_rank": 1.0,
        "planted_absolute_influence_share": 0.4,
        "bootstrap_ci_excludes_zero": False, "reference_reached_fraction": 1.0,
        "bootstrap_rejected_resamples": 0,
    }
    return [
        {**common, "scenario": "coalition_contamination", "replication": 0,
         "observed_rho": 0.10, "contamination_status": 0},
        {**common, "scenario": "coalition_contamination", "replication": 1,
         "observed_rho": 0.20, "contamination_status": 1},
        {**common, "scenario": "coalition_contamination", "replication": 2,
         "observed_rho": 0.30, "contamination_status": 1},
        {**common, "scenario": "coalition_contamination", "replication": 3,
         "observed_rho": 0.40, "contamination_status": 0},
    ]


def censored_clean_rows() -> list[dict[str, object]]:
    return [
        {
            "scenario": "clean_planted_edge", "N": 50, "p": 5,
            "observed_rho": 0.2, "wald_z": 1.0,
            "greedy_fragility_50": None, "exact_fragility_50": None,
            "certified": False, "reached": False,
            "reference_tail_probability": None, "contamination_status": 0,
        }
    ]
```

### Task 1: Add the scenario registry and bounded workload settings

**Files:**
- Modify: `simulations/run_simulation.py`
- Add: `simulations/configs/falsification_pilot.json`
- Test: `tests/test_simulation_runner.py`

**Interfaces:**
- Add `SCENARIO_NAMES: tuple[str, ...]` containing the six supported scenario names.
- Add `generate_scenario(name, n, p, rng, config) -> SimulatedDataset`.
- Add `workload_settings(config, smoke, calibration_override=None, bootstrap_override=None) -> tuple[int, int, int]` returning replications, calibration simulations, and bootstrap samples.

- [ ] **Step 1: Write the failing scenario-dispatch test**

```python
def test_runner_dispatches_all_falsification_scenarios():
    config = {
        "seed": 123,
        "replications": 1,
        "n_values": [8],
        "p_values": [3],
        "scenarios": [
            "clean_planted_edge", "single_influential_case",
            "coalition_contamination", "mixture_subgroup",
            "heavy_tails", "collinearity_stress",
        ],
        "contamination_cases": [1],
        "fragility_targets": [0.5],
        "certification_combination_budget": 20,
        "calibration_simulations": 1,
        "bootstrap_samples": 2,
    }
    rows = simulation_runner._run(config, smoke=False)
    assert {row["scenario"] for row in rows} == set(config["scenarios"])
```

- [ ] **Step 2: Run the focused test and confirm the missing scenario registry failure**

Run: `python -m pytest tests/test_simulation_runner.py::test_runner_dispatches_all_falsification_scenarios -q`

Expected: FAIL because the runner only dispatches clean and coalition scenarios.

- [ ] **Step 3: Implement the registry, workload settings, and CLI overrides**

Map each scenario name to the existing DGP function. Use configuration values for clean-edge partial correlation and coalition size; use the DGP defaults for the remaining families. Reject unknown scenario names and nonpositive workload counts with `ValueError`. For smoke runs cap the configured values at five replications, ten calibration simulations, and twenty-five bootstrap draws, matching the benchmark-derived CI budget.

Add `--calibration-simulations` and `--bootstrap-samples` command-line overrides so local execution can validate the pilot workflow with a reduced budget without editing the committed configuration.

- [ ] **Step 4: Add the pilot configuration**

Create `falsification_pilot.json` with seed `20260910`, ten replications, `n_values` `[50, 100, 150]`, `p_values` `[5, 10, 20]`, all six scenarios, calibration simulations `25`, bootstrap samples `100`, confidence `0.95`, and certification budget `100000`.

- [ ] **Step 5: Run the focused runner tests**

Run: `python -m pytest tests/test_simulation_runner.py -q`

Expected: all runner tests pass, including deterministic seed and metadata tests.

- [ ] **Step 6: Commit the scenario and workload slice**

```bash
git add simulations/run_simulation.py simulations/configs/falsification_pilot.json tests/test_simulation_runner.py
git commit -m "feat: add bounded falsification scenario workflow"
```

---

### Task 2: Add auditable influence and reach fields to result rows

**Files:**
- Modify: `simulations/run_simulation.py`
- Modify: `tests/test_simulation_runner.py`

**Interfaces:**
- Extend `FIELDNAMES` with `contamination_status`, `influence_top_k_precision`, `influence_top_k_recall`, `first_planted_reciprocal_rank`, `planted_absolute_influence_share`, `reference_reached_fraction`, and `bootstrap_rejected_resamples`.

- [ ] **Step 1: Write the failing row-schema test**

```python
def test_runner_records_full_influence_and_reach_measurements(tmp_path):
    rows = simulation_runner._run(minimal_config_with_single_case(), smoke=True)
    row = rows[0]
    assert row["contamination_status"] == 1
    assert row["influence_top_k_precision"] is not None
    assert row["first_planted_reciprocal_rank"] is not None
    assert row["reference_reached_fraction"] is not None
    assert row["bootstrap_rejected_resamples"] >= 0
```

- [ ] **Step 2: Run the focused test and confirm the missing-field failure**

Run: `python -m pytest tests/test_simulation_runner.py::test_runner_records_full_influence_and_reach_measurements -q`

Expected: FAIL because the current row only records influence recall and not the complete metric set.

- [ ] **Step 3: Implement the row measurements**

Use `influence_metrics` on exact LOO changes for scenarios with planted cases. Set influence metrics to `None` for clean and heavy-tail rows without known planted cases. Compute the proportion of reached reference calibrations from `CalibrationResult.reference_reached`. Read `rejected_resamples` from the bootstrap result. Preserve `None` for censored observed/reference counts.

- [ ] **Step 4: Run runner tests and the complete suite**

Run: `python -m pytest tests/test_simulation_runner.py tests/test_simulation_metrics.py -q`.

Expected: all focused tests pass without changing existing estimator outputs.

- [ ] **Step 5: Commit the row-schema slice**

```bash
git add simulations/run_simulation.py tests/test_simulation_runner.py
git commit -m "feat: record complete falsification row measurements"
```

---

### Task 3: Implement scenario-level falsification summaries

**Files:**
- Modify: `simulations/summarize.py`
- Test: `tests/test_simulation_metrics.py`

**Interfaces:**
- Add `summarize_scenario_rows(rows) -> dict[str, object]` for one scenario group.
- Extend `summarize_rows(rows)` with a `falsification` mapping keyed by scenario.

- [ ] **Step 1: Write hand-computable summary tests**

```python
def test_summary_reports_incremental_auc_and_rank_associations():
    rows = hand_computable_falsification_rows()
    summary = summarize_rows(rows)
    result = summary["falsification"]["coalition_contamination"]
    assert result["incremental_auc"]["augmented_auc"] >= result["incremental_auc"]["baseline_auc"]
    assert result["fragility_vs_abs_observed_rho_spearman"] is not None
    assert result["fragility_contamination_partial_rank"] is not None


def test_summary_preserves_null_for_single_class_or_censored_metrics():
    rows = censored_clean_rows()
    result = summarize_rows(rows)["falsification"]["clean_planted_edge"]
    assert result["incremental_auc"] is None
    assert result["mean_exact_fragility"] is None
```

- [ ] **Step 2: Run the new tests and confirm the summary fields are absent**

Run: `python -m pytest tests/test_simulation_metrics.py -q`

Expected: FAIL because the current summary only reports row count, mean observed rho, and clean false-flag rate.

- [ ] **Step 3: Implement finite/censor-aware summary helpers**

Group rows by scenario. Convert only finite, reached fragility rows to numeric fragility vectors. Use `spearman_correlation`, `partial_rank_association`, and `incremental_auc` on matched finite rows. Controls for partial rank association are absolute observed rho, `N`, and `p`; contamination status is binary. Compute means/rates for influence recovery, certification, overestimation, and reference reach. Return `None` when a metric has no valid rows or lacks both AUC classes.

- [ ] **Step 4: Add Markdown reporting for the principal metrics**

Extend the Markdown table with scenario, row count, clean false-flag rate, fragility/magnitude Spearman association, augmented AUC, influence recall, and certification rate. Keep the JSON summary as the complete representation.

- [ ] **Step 5: Run summary and complete tests**

Run: `python -m pytest tests/test_simulation_metrics.py tests/test_simulation_runner.py -q`.

Expected: focused and existing tests pass.

- [ ] **Step 6: Commit the summary slice**

```bash
git add simulations/summarize.py tests/test_simulation_metrics.py
git commit -m "feat: summarize falsification metrics by scenario"
```

---

### Task 4: Update smoke validation and validate the pilot workflow

**Files:**
- Modify: `tools/validate_smoke.py`
- Modify: `simulations/configs/smoke.json`
- Modify: `tests/test_simulation_runner.py`
- Modify: `tests/test_simulation_metrics.py`

**Interfaces:**
- Smoke validation must check the expanded CSV field list, finite/range constraints for new numeric fields, and the reference reach fraction bounds.

- [ ] **Step 1: Write the failing smoke-schema test**

```python
def test_smoke_validator_requires_falsification_fields(tmp_path):
    fields = [field for field in FIELDNAMES if field != "influence_top_k_precision"]
    results = tmp_path / "results.csv"
    results.write_text(",".join(fields) + "\n", encoding="utf-8")
    metadata = tmp_path / "results.metadata.json"
    metadata.write_text("{}", encoding="utf-8")
    summary = tmp_path / "summary.json"
    summary.write_text('{"rows": 0, "scenarios": {}}', encoding="utf-8")
    config = tmp_path / "config.json"
    config.write_text('{"seed": 123}', encoding="utf-8")
    with pytest.raises(ValueError, match="influence_top_k_precision"):
        validate_smoke(results, metadata, summary, config)
```

- [ ] **Step 2: Run the validator test and confirm the expected failure**

Run: `python -m pytest tests/test_simulation_runner.py::test_smoke_validator_requires_falsification_fields -q`

Expected: FAIL because the validator does not yet require the new fields.

- [ ] **Step 3: Update the validator and smoke configuration**

Require every expanded field, allow nullable influence fields where no planted cases exist, require all finite probabilities and rates to lie in `[0, 1]`, and retain the existing metadata/config checksum checks. Keep smoke at five replications, ten calibration simulations, and twenty-five bootstrap draws.

- [ ] **Step 4: Run a fixed-seed smoke workflow locally**

Run:

```bash
python -m simulations.run_simulation simulations/configs/smoke.json smoke-results.csv --smoke
python -c "from simulations.summarize import summarize_results; summarize_results('smoke-results.csv', 'smoke-summary.json', 'smoke-summary.md')"
python tools/validate_smoke.py smoke-results.csv smoke-results.metadata.json smoke-summary.json simulations/configs/smoke.json
```

Expected: validation passes and the summary contains all configured scenarios.

- [ ] **Step 5: Run the pilot configuration with a reduced calibration override for execution validation**

Run the pilot configuration with `--calibration-simulations 2 --bootstrap-samples 5` for execution validation, retain generated artifacts outside Git, and verify all six scenarios appear in the summary. Do not commit machine-specific simulation output files.

- [ ] **Step 6: Run full verification and lint**

Run: `python -m pytest -q` and `ruff check src tests simulations benchmarks`.

Expected: all tests pass and Ruff reports no violations.

- [ ] **Step 7: Commit the completed workflow**

```bash
git add tools/validate_smoke.py simulations/configs/smoke.json tests/test_simulation_runner.py tests/test_simulation_metrics.py
git commit -m "feat: validate bounded falsification workflow"
```

---

## Self-review checklist

- The scenario registry covers all six DGPs named in the specification.
- Workload settings match Task 19 measurements and do not make 500-simulation calibration the default.
- Row-level fields preserve censoring and missingness explicitly.
- Summary metrics use existing dependency-light primitives and return null when mathematically undefined.
- CI smoke remains small and deterministic.
- No production estimator or optimization code is changed.
