# Task 13 Falsification Workflow Design

**Status:** Approved design; implementation follows after specification review.

**Goal:** Integrate the truth-aware simulation generators, SDNA analysis, comparator outputs, and falsification metrics into a reproducible workflow that quantifies whether fragility adds information beyond edge magnitude and ordinary uncertainty.

## Scope

The implementation extends the existing configuration-driven runner and summary layer. It does not redesign the CSV into a method-long schema, add plotting, optimize numerical routines, or make publication claims. Existing smoke-run behavior remains available and is validated against the expanded result schema.

## Architecture

The runner will use a scenario registry that maps configuration names to the existing DGP functions. Each replication produces one row containing common truth/simulation fields plus the SDNA, Wald, bootstrap, calibration, and influence-recovery measurements needed by the summary layer. Missing or censored quantities remain explicit `None` values.

The summary layer will operate on row-oriented results and calculate scenario-level falsification statistics. It will never coerce censored fragility results into observed counts, and it will return `None` for metrics that lack finite values or both binary classes rather than silently manufacturing a score.

## Scenario coverage

The runner will support these scenario names:

1. `clean_planted_edge` — a known nonzero population focal edge;
2. `single_influential_case` — a null/weak population edge with one shifted case;
3. `coalition_contamination` — a null/weak population edge with a known shifted coalition;
4. `mixture_subgroup` — a subgroup generated from a distinct covariance structure;
5. `heavy_tails` — continuous multivariate t-like observations;
6. `collinearity_stress` — a valid near-collinear covariance structure.

The default falsification-pilot configuration will use `N=[50,100,150]`, `p=[5,10,20]`, ten replications per cell, and all six scenarios. Existing `contamination_cases` remains the coalition-size control; DGP-specific defaults are used for the other scenario families unless overridden by future configuration work.

## Row-level measurements

Every result row will retain the existing core columns and add the following auditable fields:

- scenario truth status and planted-case count;
- influence top-k precision, top-k recall, first-planted reciprocal rank, and planted absolute-influence share;
- greedy/exact fragility counts, certification, reach status, and reference reach status;
- bootstrap rejection count and confidence-exclusion status;
- Wald statistic and reference-tail probability.

The row format remains compatible with the current smoke validator after its expected schema is updated. The runner will continue to use independent `SeedSequence` children for the dataset, calibration, and bootstrap streams.

## Summary metrics

For each scenario, the JSON summary will report:

- row count and mean observed focal-edge estimate;
- clean false-flag rate at reference-tail probability `<= 0.05`;
- Spearman association of fragility with `abs(observed_rho)` and `abs(wald_z)`;
- partial rank association of contamination status with fragility, controlling for magnitude, `N`, and `p`;
- baseline and augmented incremental AUC using learned predictor weights;
- mean influence-recovery measures for planted-case scenarios;
- greedy overestimation and certification rates where both counts are observed;
- fragility and reference-search reach rates.

Metrics with insufficient finite rows, censored counts, or only one binary class will be represented as `null`. Markdown output will present the principal scenario-level rates and AUC values while the JSON output remains the complete machine-readable record.

## Computational budget

Task 19 measured one 500-simulation calibration cell at up to approximately 37.8 seconds at the tested scale. The workflow therefore defines explicit profiles:

| Profile | Replications | Calibration simulations | Bootstrap draws | Purpose |
|---|---:|---:|---:|---|
| CI smoke | 5 | 10 | 25 | Fast schema and invariant validation |
| falsification pilot | 10 | 25 | 100 | Local end-to-end evidence across all scenarios |
| full research run | user-selected | 50 | 200 | Explicit, non-CI evidence generation |

The existing 500-simulation benchmark remains a performance measurement, not a default per-row calibration setting. No optimization is introduced until the pilot and full-run profiles have produced measurements showing a bottleneck.

## Files

- Modify `simulations/run_simulation.py` for scenario dispatch, expanded row fields, and budget validation.
- Modify `simulations/metrics.py` only where safe finite/missing-value helpers are needed by the summary calculations.
- Modify `simulations/summarize.py` for scenario-level falsification summaries and Markdown reporting.
- Add `simulations/configs/falsification_pilot.json` with the benchmark-derived pilot limits.
- Modify `tools/validate_smoke.py` and the smoke tests for the expanded schema and invariants.
- Extend `tests/test_simulation_runner.py` and `tests/test_simulation_metrics.py` with scenario coverage, budget behavior, and hand-computable summary cases.

## Acceptance criteria

1. A fixed-seed pilot configuration runs all six scenario families and writes deterministic row fields plus metadata.
2. The smoke workflow remains within the CI budget and validates the complete expanded schema.
3. Summary JSON and Markdown contain the listed falsification metrics and preserve explicit nulls for censored/undefined values.
4. Tiny hand-computable tests cover AUC, rank association, influence recovery, false-flag handling, and insufficient-class handling.
5. Existing package tests and Ruff checks remain green.
6. The implementation does not change estimator, influence, fragility, calibration, or comparator numerical behavior.

## Non-goals

- No production optimization based on the Task 19 timings.
- No default fragile/not-fragile label.
- No inference from bootstrap results that were not produced by `bootnet`.
- No real-data reanalysis or publication-level conclusion in this task.
