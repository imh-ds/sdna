# Task 26 Certification-budget Sensitivity Study Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run and validate a focused, deterministic sensitivity study of certification budgets `[1000, 5000, 10000, 20000]` on the exact Task 25 `U_to_R(3)` and `U_to_R(4)` populations without changing the production cap-2 protocol.

**Architecture:** Add a new immutable Task 26 study manifest and a preparation command that validates the accepted Task 25 artifact before writing the exact 44/68 selected pairing keys. A budget-arm runner will regenerate the validated source datasets deterministically, execute only candidate caps 3 and 4 at one fixed budget, checkpoint results/statuses for timeout diagnosis, and preserve all non-certification fields. A separate validator/aggregator will compare each arm to the Task 25 source rows, summarize complete arms and incomplete arms distinctly, and produce a combined evidence artifact. A manual-only Actions matrix will execute the four budgets and aggregate their artifacts.

**Tech Stack:** Python 3.11+, NumPy, pytest, Ruff, mypy, JSON/CSV/Markdown, GitHub Actions, and the existing Task 24/25 manifest, workflow, and artifact validators.

**Spec:** `docs/superpowers/specs/2026-09-14-task26-certification-budget-sensitivity-design.md`

## Global Constraints

- The source identity is fixed to Task 25 Actions run `34895397606`, source commit `7b22b3fca39888e1a452cb5a7ad8ec244ccd752e`, artifact `sdna-certification-usability-34895397606`, and Task 25 `results.csv` SHA-256 `4ec0068d8fe2b2b62df45fccbbf71f884c50589e319e48c3a2400111ae051918`.
- The nested Task 24 source identity is fixed to run `34871220664`, commit `338b0d95cdb312b2805affb0de458e06508d80f0`, artifact `sdna-cap-expansion-34871220664`, source-results SHA-256 `110d0b4f266b253251ac1a64bb4195b61722008d426b74c75802d3de57b43d87`, and source-manifest SHA-256 `415576f1fec5ccd2a47e0ad411d29e4d48c6e8e370609ae495ccc877fe74e974`.
- The selected populations are exactly `U_to_R(3)=44` and `U_to_R(4)=68`; the populations may overlap by pairing key and must never be described as 112 unique keys.
- The fixed budget grid is `[1000, 5000, 10000, 20000]`; no budget is added adaptively after inspecting results.
- The source seed is `20260910`; the six scenarios, `N`/`p` grid, parameterization, target `0.5`, calibration `25`, bootstrap `100`, confidence `0.95`, right-censored reference-tail treatment, ordinary-partial Wald comparator, shrinkage, and all stage behavior remain unchanged.
- `calibration_require_reached=False` remains explicit in every completed row.
- Only `certification_combination_budget` changes across arms. It is recorded in each row and in every arm/aggregate manifest.
- Cap 2 remains the unchanged production baseline and is not rerun by the focused study.
- Each budget arm has a computation ceiling of `1800` seconds and an Actions job timeout of `40` minutes; timeout, failure, and incomplete arms are not converted to zero yield.
- Row-level `combination_budget_exhausted` is a valid completed certification outcome and is distinct from arm-level `timeout`, `failed`, and `incomplete` statuses.
- Completed arms contain 44 cap-3 rows and 68 cap-4 rows. A complete aggregate contains 448 cap-budget rows.
- Original Task 25 fields must match exactly except `elapsed_seconds`; finite numeric values use `rel_tol=1e-12` and `abs_tol=1e-12`, while keys, categorical values, booleans, nullability, seeds, digests, and row membership remain strict.
- Existing `cap_expansion_v1.json`, `certification_usability_v1.json`, cap-2 behavior, Task 24 artifacts, and Task 25 artifacts remain unchanged.
- The hosted workflow is `workflow_dispatch` only; it is not a push, pull-request, or scheduled workflow.

## File map

| File | Responsibility |
| --- | --- |
| `simulations/configs/certification_budget_sensitivity_v1.json` | Immutable Task 26 source identities, budget grid, population counts, protocol constants, timeout ceiling, and output contract. |
| `tools/certification_budget_sensitivity_manifest.py` | Strictly load, validate, and checksum the Task 26 manifest. |
| `tools/prepare_certification_budget_sensitivity.py` | Validate the Task 25 artifact, extract exact `U_to_R` rows, and write the selection manifest consumed by every budget arm. |
| `tests/test_certification_budget_sensitivity_manifest.py` | Manifest values, checksum, and mutation-rejection tests. |
| `tests/test_prepare_certification_budget_sensitivity.py` | Exact population selection, overlap, key ordering, and source-validation tests. |
| `tools/run_certification_budget_sensitivity.py` | Execute one fixed budget arm on the prepared selection, checkpoint outputs, enforce the computation ceiling, and record environment/provenance. |
| `tests/test_certification_budget_sensitivity_runner.py` | Budget propagation, shared deterministic datasets, source digest/seeds, row schema, checkpointing, timeout, and failure-state tests. |
| `tools/summarize_certification_budget_sensitivity.py` | Validate one arm against Task 25, summarize cap/budget endpoints, aggregate four arms, and render JSON/Markdown reports. |
| `tests/test_certification_budget_sensitivity_summary.py` | Per-arm validation, exact source-field comparison, incomplete-arm semantics, aggregation, and tamper rejection. |
| `.github/workflows/certification-budget-sensitivity.yml` | Manual preparation, four fixed-budget matrix jobs, artifact retention, and aggregate reporting. |
| `tests/test_certification_budget_sensitivity_workflow.py` | Manual-only workflow and failure-artifact contract tests. |
| `docs/methodology/certification_budget_sensitivity_study_v1.md` | User-facing pre-specified methodology and interpretation rules. |
| `docs/development/decisions.md` | ADR-025 implementation traceability, hosted run, checksums, findings, and limitations. |

## Shared interfaces and data contracts

The implementation must preserve the existing Task 25 CSV field order and
comparison semantics. The new arm CSV uses:

```python
SENSITIVITY_FIELDNAMES = CAP_EXPANSION_FIELDNAMES + [
    "certification_combinations_checked",
    "certification_combination_budget",
    "certification_budget_exhausted",
    "certification_failure_reason",
]
```

The selection manifest contains the validated source identity and the exact
Task 25 candidate rows, grouped by candidate cap:

```python
def build_selection_manifest(
    task25_rows: Sequence[Mapping[str, Any]],
    study_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the validated cap-specific selection mapping."""

def load_selection_manifest(
    path: str | Path,
    study_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Load and validate a previously written selection mapping."""
```

The fixed-budget runner has this public interface:

```python
def run_certification_budget_arm(
    selection_manifest_path: str | Path,
    source_manifest_path: str | Path,
    study_manifest_path: str | Path,
    budget: int,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Run one fixed budget arm and return its persisted status mapping."""
```

It writes `results.csv`, `results.metadata.json`, and `arm_status.json` in
`output_dir`. The returned mapping is the same machine-readable arm status
written to disk. Its `arm_status` is one of `complete`, `timeout`, `failed`, or
`incomplete`.

The arm validator writes `arm_validation.json` beside these files. On a
validation failure it must still write a report containing `valid=false`, the
exception type and message, observed row/status counts, source identities, and
the budget, so the Actions upload has a reviewable failure record.

The summary module has these public interfaces:

```python
def validate_certification_budget_arm(
    arm_dir: str | Path,
    selection_manifest_path: str | Path,
    study_manifest_path: str | Path,
) -> dict[str, Any]:
    """Validate and summarize one budget-arm directory."""

def aggregate_certification_budget_arms(
    arm_dirs: Mapping[int, str | Path],
    selection_manifest_path: str | Path,
    study_manifest_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Validate available arms and write the aggregate evidence bundle."""
```

The aggregate writes the concatenated `results.csv`, `summary.json`, and
`summary.md`, plus a copied `selection_manifest.json` and per-budget status
records. A complete sensitivity result is true only when every fixed budget
has status `complete` and exactly 112 rows.

## Test fixture conventions

The new test modules should define their own small fixtures rather than
downloading hosted artifacts. Use these exact helper names and contracts so
the examples below are executable within the test modules:

```python
MANIFEST_PATH = Path("simulations/configs/certification_budget_sensitivity_v1.json")
SOURCE_CONFIG_PATH = Path("simulations/configs/cap_expansion_v1.json")
STUDY_CONFIG_PATH = MANIFEST_PATH
STUDY_MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

def write_json(tmp_path: Path, name: str, value: Mapping[str, Any]) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(value), encoding="utf-8")
    return path

def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
```

Each runner and summary test module defines
`write_selection_fixture(tmp_path: Path, expected_counts: dict[str, int]) -> Path`
using one cap-3-only key, one cap-4-only key, and one key present in both
populations; it writes the same candidate source-row fields that the Task 25
CSV uses. Runner tests may
patch `generate_cap_expansion_dataset` with a tracker returning a small
`SimulatedDataset` and patch `run_full_workflow` with a tracker returning all
required workflow fields plus the requested certification diagnostics.
Manifest tests define `task25_rows() -> list[dict[str, Any]]` using the same
three-key relationship. The tracker names are local test helpers, not
production interfaces. The runner test module imports the runner as
`from tools import run_certification_budget_sensitivity as runner` and defines
`tracked_dataset(generated: list[SimulatedDataset]) -> Callable[..., SimulatedDataset]`
and `tracked_workflow(calls: list[dict[str, Any]]) -> Callable[..., dict[str, Any]]`;
the first records one generated object per call and the second records keyword
arguments while returning the complete synthetic workflow mapping.

---

### Task 1: Freeze the Task 26 manifest and exact selected population

**Files:**
- Create: `simulations/configs/certification_budget_sensitivity_v1.json`
- Create: `tools/certification_budget_sensitivity_manifest.py`
- Create: `tools/prepare_certification_budget_sensitivity.py`
- Test: `tests/test_certification_budget_sensitivity_manifest.py`
- Test: `tests/test_prepare_certification_budget_sensitivity.py`

**Interfaces:**
- `BUDGET_GRID: tuple[int, int, int, int] = (1000, 5000, 10000, 20000)`.
- `load_certification_budget_sensitivity_manifest(path: str | Path) -> dict[str, Any]`.
- `certification_budget_sensitivity_manifest_checksum(manifest: Mapping[str, Any]) -> str`.
- `build_selection_manifest(task25_rows: Sequence[Mapping[str, Any]], study_manifest: Mapping[str, Any]) -> dict[str, Any]`.
- `load_selection_manifest(path: str | Path, study_manifest: Mapping[str, Any]) -> dict[str, Any]`.
- `prepare_certification_budget_sensitivity(task25_results_csv: str | Path, task25_metadata_json: str | Path, task25_summary_json: str | Path, source_results_csv: str | Path, source_metadata_json: str | Path, source_summary_json: str | Path, source_manifest_path: str | Path, task25_manifest_path: str | Path, study_manifest_path: str | Path, output_path: str | Path) -> None`, which validates the Task 25 artifact before writing the selection manifest.

The JSON manifest must contain the complete Task 25 and Task 24 identities,
`candidate_caps=[3,4]`, `expected_population_rows={"cap3":44,"cap4":68}`,
`budget_grid=[1000,5000,10000,20000]`, `baseline_budget=1000`,
`runtime_ceiling_seconds=1800`, `actions_timeout_minutes=40`,
`expected_rows_per_budget=112`, `seed=20260910`,
`calibration_simulations=25`, `bootstrap_samples=100`,
`bootstrap_confidence=0.95`, `calibration_require_reached=false`,
`primary_target=0.5`, `source_manifest="simulations/configs/cap_expansion_v1.json"`,
`task25_manifest="simulations/configs/certification_usability_v1.json"`,
the six allowed diagnostic reasons, and an explicit output schema version.

- [ ] **Step 1: Write failing manifest tests**

```python
def test_budget_manifest_declares_the_fixed_contract() -> None:
    manifest = load_certification_budget_sensitivity_manifest(
        Path("simulations/configs/certification_budget_sensitivity_v1.json")
    )
    assert manifest["budget_grid"] == [1000, 5000, 10000, 20000]
    assert manifest["candidate_caps"] == [3, 4]
    assert manifest["expected_population_rows"] == {"cap3": 44, "cap4": 68}
    assert manifest["runtime_ceiling_seconds"] == 1800
    assert manifest["expected_rows_per_budget"] == 112


@pytest.mark.parametrize("field", ["budget_grid", "source_task25_run_id", "runtime_ceiling_seconds"])
def test_budget_manifest_rejects_protocol_mutation(tmp_path: Path, field: str) -> None:
    manifest = json.loads(Path(MANIFEST_PATH).read_text(encoding="utf-8"))
    manifest[field] = {"budget_grid": [1000], "source_task25_run_id": "other", "runtime_ceiling_seconds": 1}[field]
    path = write_json(tmp_path, "mutated.json", manifest)
    with pytest.raises(ValueError):
        load_certification_budget_sensitivity_manifest(path)
```

- [ ] **Step 2: Run manifest tests and verify the missing contract**

Run: `python -m pytest tests/test_certification_budget_sensitivity_manifest.py -q`

Expected: FAIL because the Task 26 manifest module and JSON configuration do
not exist.

- [ ] **Step 3: Implement the immutable manifest and checksum**

Create the JSON with the exact values above. The loader must reject missing or
extra fields, wrong source identities, a changed budget order, duplicate
budgets, changed population counts, changed timeout values, a changed reason
vocabulary, and protocol constants inconsistent with the source study. Return
a fresh dictionary. Canonicalize JSON with sorted keys and compact separators
for the manifest checksum.

- [ ] **Step 4: Write failing selection tests with an overlapping fixture**

Use a synthetic Task 25 row fixture with three pairing keys: one selected only
for cap 3, one selected only for cap 4, and one selected for both caps. Include
the cap-2 baseline row for every key. Assert that `build_selection_manifest`
returns the two cap populations separately, preserves the overlap, sorts keys
by `(N, p, scenario, parameter_id, replication)`, and records the candidate
source rows without filtering on downstream status. Pass a test study mapping
with expected counts `{"cap3": 2, "cap4": 2}` to this pure builder so the
three-key fixture can exercise overlap; the production preparation call uses
the loaded immutable manifest and enforces `{"cap3": 44, "cap4": 68}`.

```python
def test_selection_manifest_preserves_cap_overlap_and_exact_rows() -> None:
    test_manifest = dict(STUDY_MANIFEST)
    test_manifest["expected_population_rows"] = {"cap3": 2, "cap4": 2}
    selection = build_selection_manifest(task25_rows(), test_manifest)
    assert len(selection["populations"]["cap3"]) == 2
    assert len(selection["populations"]["cap4"]) == 2
    assert selection["overlap_rows"] == 1
    assert selection["unique_pair_keys"] == 3
    assert selection["populations"]["cap3"][0]["candidate"]["arm"] == "cap3"
```

- [ ] **Step 5: Implement validated Task 25 preparation**

Call the existing `validate_certification_usability` with the Task 25 CSV,
metadata, summary, nested Task 24 CSV/metadata/summary, cap-expansion
manifest, and Task 25 manifest before reading rows for selection. Then call
`identify_newly_reached_pairs`, require exactly 44 cap-3 and 68 cap-4 rows,
compute the overlap by canonical pairing key, and write a selection manifest
containing the complete source identities, manifest checksum, exact keys,
candidate rows, baseline rows, expected counts, overlap count, and a checksum
of the selection JSON.

`load_selection_manifest` must reject changed source checksums, changed Task 25
run/commit/artifact identifiers, changed cap populations, duplicate candidate
keys, missing baseline rows, and a changed selection checksum. It must not
collapse an overlapping key into one population.

- [ ] **Step 6: Run focused manifest and selection tests**

Run: `python -m pytest tests/test_certification_budget_sensitivity_manifest.py tests/test_prepare_certification_budget_sensitivity.py -q`

Expected: all manifest and selection tests pass, including overlap and source
identity rejection tests.

- [ ] **Step 7: Commit the frozen Task 26 source slice**

```powershell
git add simulations/configs/certification_budget_sensitivity_v1.json tools/certification_budget_sensitivity_manifest.py tools/prepare_certification_budget_sensitivity.py tests/test_certification_budget_sensitivity_manifest.py tests/test_prepare_certification_budget_sensitivity.py
git commit -m "feat: freeze certification budget sensitivity manifest"
```

---

### Task 2: Implement the deterministic fixed-budget arm runner

**Files:**
- Create: `tools/run_certification_budget_sensitivity.py`
- Test: `tests/test_certification_budget_sensitivity_runner.py`

**Interfaces:**
- `run_certification_budget_arm(selection_manifest_path: str | Path, source_manifest_path: str | Path, study_manifest_path: str | Path, budget: int, output_dir: str | Path) -> dict[str, Any]`.
- CLI: `python -m tools.run_certification_budget_sensitivity <selection> <source-config> <study-config> <budget> <output-dir>`.
- `SENSITIVITY_FIELDNAMES` is the existing Task 24 field list followed by the four Task 25 certification diagnostic fields.

The runner consumes only the validated selection manifest and the unchanged
Task 24 source configuration. It must use the candidate source row's data
seed, canonicalize its numeric job fields, call
`generate_cap_expansion_dataset`, and verify that the regenerated dataset
digest equals the Task 25 candidate digest before running the workflow.

For an overlapping pairing key, cache one generated dataset and execute the
cap-3 and cap-4 candidate rows against that same object. The workflow seeds
must be `derive_workflow_seeds(data_seed)` and must match the Task 25
calibration/bootstrap seeds. Budget order must not affect any digest, seed,
data, calibration, Wald, bootstrap, or source field.

- [ ] **Step 1: Write failing runner tests for selected rows and budget propagation**

Patch `generate_cap_expansion_dataset` and `run_full_workflow` with small
deterministic fixtures. Use a selection containing two cap-3 rows and two
cap-4 rows, including one overlapping pairing key. Assert that one dataset is
generated per unique key, that every output row contains the requested budget,
that the CSV has exactly the diagnostic schema, and that the workflow receives
the requested `max_combinations` through `certification_combination_budget`.

```python
def test_runner_uses_one_dataset_per_pair_and_records_requested_budget(tmp_path, monkeypatch) -> None:
    generated = []
    calls = []
    monkeypatch.setattr(runner, "generate_cap_expansion_dataset", tracked_dataset(generated))
    monkeypatch.setattr(runner, "run_full_workflow", tracked_workflow(calls))
    selection_path = write_selection_fixture(tmp_path, expected_counts={"cap3": 2, "cap4": 2})

    status = runner.run_certification_budget_arm(
        selection_path,
        SOURCE_CONFIG_PATH,
        STUDY_CONFIG_PATH,
        5000,
        tmp_path,
    )

    rows = read_csv(tmp_path / "results.csv")
    assert status["arm_status"] == "complete"
    assert len(generated) == 3
    assert len(rows) == 4
    assert {int(row["certification_combination_budget"]) for row in rows} == {5000}
    assert {call["certification_combination_budget"] for call in calls} == {5000}
```

- [ ] **Step 2: Run the focused runner test and verify the runner is absent**

Run: `python -m pytest tests/test_certification_budget_sensitivity_runner.py -q`

Expected: FAIL because the fixed-budget runner does not exist.

- [ ] **Step 3: Implement canonical job construction and workflow execution**

Construct each candidate job from the selection record with integer
`parameter_id`, `replication`, `N`, `p`, and `search_cap`, numeric `parameter`
and `fragility_target`, and the source `scenario`/`arm`. Use the existing
`generate_cap_expansion_dataset` and `run_full_workflow` interfaces. Build a
row with the existing Task 25 fields, overwrite workflow outputs with the new
run, set `certification_combination_budget=budget`, and preserve the source
row's pairing/provenance values. Reject a regenerated data digest or child
seed mismatch before producing a completed arm.

Catch the same stage exceptions already represented by
`run_full_workflow` as row-level statuses. For a dataset-generation error,
write a valid diagnostic row with `certification_failure_reason` set to
`not_applicable_prior_error` and `certification_budget_exhausted=False`.
Unexpected runner exceptions are arm-level failures and must not be converted
into synthetic non-certification rows.

- [ ] **Step 4: Implement row-by-row checkpointing and fixed timeout semantics**

Create `results.csv` with its header before processing. After every completed
row, append and flush the row, write `results.metadata.json`, and atomically
replace `arm_status.json`. Check elapsed time between rows. When the 1,800
second ceiling is reached, stop before the next key, preserve completed rows,
write `arm_status="timeout"`, and return a status mapping without assigning
unprocessed rows a certification result. Use status values `complete`,
`timeout`, `failed`, and `incomplete`; write `expected_rows=112`, observed
cap counts, completed keys, last completed key, elapsed seconds, runtime
ceiling, source checksums, budget, environment versions, and artifact
checksums.

The CLI exits with status 0 only for a complete arm and a nonzero status for a
timeout, failure, or incomplete arm. The output files remain available for
the Actions upload step in all cases.

- [ ] **Step 5: Add timeout, failure, and reproducibility regression tests**

Use a monotonic-clock fixture that reaches the ceiling after one row and assert
that the arm status is `timeout`, the CSV contains only the completed row, and
the status record names the last completed key. Add an unexpected-exception
fixture and assert `failed` rather than a zero-yield row. Run the same selected
keys twice with budgets in opposite order and assert matching source fields,
data seeds, child seeds, and dataset digests.

- [ ] **Step 6: Run focused runner tests**

Run: `python -m pytest tests/test_certification_budget_sensitivity_runner.py -q`

Expected: all selected-row, schema, caching, budget, checkpoint, timeout,
failure, and reproducibility tests pass.

- [ ] **Step 7: Commit the fixed-budget runner**

```powershell
git add tools/run_certification_budget_sensitivity.py tests/test_certification_budget_sensitivity_runner.py
git commit -m "feat: run certification budget sensitivity arms"
```

---

### Task 3: Validate, summarize, and aggregate the budget arms

**Files:**
- Create: `tools/summarize_certification_budget_sensitivity.py`
- Test: `tests/test_certification_budget_sensitivity_summary.py`

**Interfaces:**
- `validate_certification_budget_arm(arm_dir: str | Path, selection_manifest_path: str | Path, study_manifest_path: str | Path) -> dict[str, Any]`.
- `summarize_certification_budget_arm(rows: Sequence[Mapping[str, Any]], selection: Mapping[str, Any], study_manifest: Mapping[str, Any], arm_status: Mapping[str, Any]) -> dict[str, Any]`.
- `aggregate_certification_budget_arms(arm_dirs: Mapping[int, str | Path], selection_manifest_path: str | Path, study_manifest_path: str | Path, output_dir: str | Path) -> dict[str, Any]`.
- CLI aggregation command accepts the selection manifest, an arms directory, the study manifest, and an output directory.

Use `compare_instrumented_rows_to_reference` from
`tools.summarize_certification_usability` with the 112 selected Task 25
candidate rows as the reference sequence. This preserves the established
comparison contract while allowing the focused subset. Do not compare or
require the Task 25 `certification_*` diagnostics to remain unchanged; those
are the intended budget-dependent fields. Compare every other field except
`elapsed_seconds` exactly as Task 25 does.

- [ ] **Step 1: Write failing per-arm summary and validation tests**

Create a valid synthetic selection and a 112-row arm fixture. Assert cap-3 and
cap-4 denominators, certification yield, reason counts, budget exhaustion,
combination totals, downstream status counts, and exact pair-key lists. Add
tamper cases for a changed source digest, seed, status, nullability, pairing
key, budget, diagnostic reason, row count, and artifact checksum.

```python
def test_incomplete_arm_has_no_certification_yield() -> None:
    status = {"arm_status": "timeout", "expected_rows": 112, "rows": 7}
    summary = summarize_certification_budget_arm(
        arm_rows[:7], SELECTION, STUDY_MANIFEST, status
    )
    assert summary["arm_status"] == "timeout"
    assert summary["populations"]["cap3"]["certification_yield"] is None
    assert summary["populations"]["cap3"]["yield_status"] == "unavailable_incomplete_arm"
```

- [ ] **Step 2: Run summary tests and verify the validator is absent**

Run: `python -m pytest tests/test_certification_budget_sensitivity_summary.py -q`

Expected: FAIL because the Task 26 summary and validator do not exist.

- [ ] **Step 3: Implement strict arm validation**

Load and validate the Task 26 manifest and selection manifest. Require the
arm budget to be one declared budget, require the arm CSV fields to be
`SENSITIVITY_FIELDNAMES` in order, and require the arm status to agree with
the observed files. For a complete arm, require exactly 112 rows with 44
cap-3 and 68 cap-4 rows. For an incomplete arm, require the observed count to
equal the checkpointed status record and leave missing rows absent rather than
inventing outcomes.

Validate every diagnostic state with the existing Task 25 reason vocabulary:
unreached rows use `not_applicable_unreached`, prior errors use
`not_applicable_prior_error`, successful certification uses `certified`,
budget exhaustion uses `combination_budget_exhausted` and a true exhaustion
flag, other non-certification uses `not_certified_other`, and certification
exceptions use `error`.

Compare completed rows to their exact Task 25 candidate source rows. Require
matching `arm`, pairing fields, seeds, digest, target, cap, calibration mode,
stage values, downstream outputs, error fields, and nullability. Permit only
the established `1e-12` numeric tolerance and the intentionally different
certification diagnostics and elapsed time.

Expose a CLI validation mode that always writes `arm_validation.json` before
returning. A valid complete arm exits zero. A timeout, failed arm, incomplete
arm, schema mismatch, source mismatch, or tampered artifact exits nonzero but
retains its machine-readable validation report.

- [ ] **Step 4: Implement per-arm summaries**

For each cap in each completed arm, calculate:

```python
{
    "rows": 44 or 68,
    "certified_rows": int,
    "certification_yield": certified_rows / expected_rows,
    "yield_status": "available",
    "certification_status_counts": dict[str, int],
    "reason_counts": dict[str, int],
    "budget_exhausted_rows": int,
    "combination_counts": {
        "rows": int,
        "total": int,
        "minimum": int | None,
        "maximum": int | None,
    },
    "downstream_status_counts": dict[str, dict[str, int]],
    "error_stage_counts": dict[str, int],
    "pair_keys": list[dict[str, Any]],
}
```

For a timed-out, failed, or incomplete arm, retain observed counts and
diagnostic status counts but set `certification_yield=None` and
`yield_status="unavailable_incomplete_arm"` for every affected population.
The denominator is never reduced to the number of completed rows.

- [ ] **Step 5: Implement four-arm aggregation and Markdown rendering**

Load each available budget directory, validate it, concatenate rows in the
deterministic order `(budget, candidate cap, N, p, scenario, parameter_id,
replication)`, and write one combined `results.csv`. Produce `summary.json`
with complete source identities/checksums, fixed grid, overlap count, arm
statuses, per-cap/per-budget endpoints, runtime, reason counts, and boolean
`complete_sensitivity_result`. Produce `summary.md` that states:

- cap-3 and cap-4 denominators are separate and may overlap;
- incomplete arms are not zero-yield evidence;
- row-level budget exhaustion differs from arm timeout;
- cap 2 remains the production baseline; and
- any yield change is evidence only for the specified selected population and
  budget, not a cap-promotion or production-budget decision.

The aggregate must still write a diagnostic summary when one or more arm
directories are missing or incomplete, but the complete-result check must be
false and the CLI must exit nonzero.

- [ ] **Step 6: Run focused summary tests**

Run: `python -m pytest tests/test_certification_budget_sensitivity_summary.py -q`

Expected: all source comparison, diagnostic-state, denominator, overlap,
incomplete-arm, aggregation, tamper, and Markdown-contract tests pass.

- [ ] **Step 7: Commit validation and aggregation**

```powershell
git add tools/summarize_certification_budget_sensitivity.py tests/test_certification_budget_sensitivity_summary.py
git commit -m "feat: validate certification budget sensitivity evidence"
```

---

### Task 4: Add the manual fixed-budget Actions workflow

**Files:**
- Create: `.github/workflows/certification-budget-sensitivity.yml`
- Create: `tests/test_certification_budget_sensitivity_workflow.py`

**Interfaces:**
- The workflow has `workflow_dispatch` as its only trigger.
- The matrix is exactly `budget: [1000, 5000, 10000, 20000]` with `fail-fast: false`.
- The preparation job downloads and validates Task 25 artifact `sdna-certification-usability-34895397606`.
- Each matrix job has `timeout-minutes: 40`, runs one fixed budget, and uploads its arm artifact with `if: always()`.
- The aggregation job runs with `if: always()`, preserves partial artifacts, and reports a nonzero completion check for missing/incomplete arms.

- [ ] **Step 1: Write failing workflow contract tests**

```python
def test_budget_sensitivity_workflow_is_manual_fixed_matrix() -> None:
    text = Path(WORKFLOW_PATH).read_text(encoding="utf-8")
    for required in (
        "workflow_dispatch:",
        "34895397606",
        "sdna-certification-usability-34895397606",
        "matrix:",
        "1000",
        "5000",
        "10000",
        "20000",
        "fail-fast: false",
        "timeout-minutes: 40",
        "if: always()",
        "tools.prepare_certification_budget_sensitivity",
        "tools.run_certification_budget_sensitivity",
        "tools.summarize_certification_budget_sensitivity",
        "actions/upload-artifact",
    ):
        assert required in text
    for forbidden in ("schedule:", "push:", "pull_request:"):
        assert forbidden not in text
```

- [ ] **Step 2: Run the workflow contract test and verify it fails**

Run: `python -m pytest tests/test_certification_budget_sensitivity_workflow.py -q`

Expected: FAIL because the Task 26 workflow and contract test do not yet
exist.

- [ ] **Step 3: Implement the preparation job**

Use checkout `actions/checkout@v7.0.1`, setup Python `actions/setup-python@v7.0.0`
with Python `3.11`, and install `.[dev]` with `constraints-ci.txt`. Download
the pinned Task 25 artifact with `GH_TOKEN: ${{ github.token }}` and `gh run
download`. Pass the nested reference files to
`tools.prepare_certification_budget_sensitivity`; upload the resulting
selection manifest, command record, provenance, and any validation output with
90-day retention and `if: always()`.

- [ ] **Step 4: Implement the four budget matrix jobs**

Use a matrix over the exact fixed budget list with `fail-fast: false`. Download
the preparation artifact, run the fixed-budget CLI into a budget-specific
directory, and set `continue-on-error: true` on the runner step so timeout and
failure artifacts reach upload. Run the arm validator in an `if: always()`
step with `continue-on-error: true` so it writes `arm_validation.json` even
when the runner is incomplete. Upload `results.csv`, metadata, status,
validation report, selection manifest, environment, and any partial
checkpoints under an artifact name containing the budget and workflow run ID.
Do not rerun cap 2 or regenerate population membership in these jobs.

- [ ] **Step 5: Implement the always-run aggregation job**

Download all available budget artifacts without merging same-named files into
one directory. Run the aggregate CLI with the selection manifest and four
budget directories. Upload the combined evidence directory with `if:
always()` and 90-day retention. The aggregation step may fail the job when
`complete_sensitivity_result` is false, but it must retain the summary and
partial outputs first.

- [ ] **Step 6: Run the workflow contract tests**

Run: `python -m pytest tests/test_certification_budget_sensitivity_workflow.py -q`

Expected: all manual-only, fixed-grid, pinned-source, matrix, timeout, and
artifact-upload assertions pass.

- [ ] **Step 7: Commit the manual workflow**

```powershell
git add .github/workflows/certification-budget-sensitivity.yml tests/test_certification_budget_sensitivity_workflow.py
git commit -m "ci: add manual certification budget sensitivity matrix"
```

---

### Task 5: Document the pre-specified study and decision traceability

**Files:**
- Create: `docs/methodology/certification_budget_sensitivity_study_v1.md`
- Modify: `docs/development/decisions.md`

**Interfaces:**
- The methodology page links to the Task 26 specification, plan, manifest,
  runner, validator, and workflow by repository-relative paths.
- ADR-025 records the specification commit `810e57c`, the implementation-plan
  commit from this task, every implementation commit, the hosted Actions run,
  artifact name/checksums, findings, and limitations.

- [ ] **Step 1: Write documentation tests before the documentation**

Extend the workflow-contract test module or create a focused documentation
test that requires the methodology page to contain `U_to_R(3)=44`,
`U_to_R(4)=68`, `[1000, 5000, 10000, 20000]`, `1800`, `timeout`,
`combination_budget_exhausted`, `not a cap-promotion`, `overlap`, `cap 2`,
and `incomplete`.

- [ ] **Step 2: Write the methodology page**

State the study question, exact Task 25/24 source identities, population
selection rule, separate cap denominators, fixed budget grid, combinatorial
motivation, protocol invariants, one-dataset-per-key rule, timeout semantics,
row and aggregate artifact schemas, validation tolerance, manual-only Actions
execution, and interpretation limits. Keep empirical results out of this
initial page until a hosted run is accepted.

- [ ] **Step 3: Add ADR-025 with pending execution fields**

Record why Task 25's all-zero certification yield is diagnostically compatible
with budget exhaustion, why the selected 44/68 populations and fixed grid are
preferred, why incomplete arms cannot be scored as zero, and why cap 2 remains
unchanged. Identify the exact spec and plan commits and list every file in the
implementation scope. Mark hosted run ID, artifact checksums, runtime, and
empirical yields as pending until the manual workflow completes.

- [ ] **Step 4: Run documentation tests**

Run: `python -m pytest tests/test_certification_budget_sensitivity_workflow.py -q`

Expected: all workflow and methodology contract tests pass.

- [ ] **Step 5: Commit the documentation and decision entry**

```powershell
git add docs/methodology/certification_budget_sensitivity_study_v1.md docs/development/decisions.md tests/test_certification_budget_sensitivity_workflow.py
git commit -m "docs: specify certification budget sensitivity study"
```

---

### Task 6: Run complete local verification and hosted evidence generation

**Files:**
- Modify: `docs/development/decisions.md`
- Modify: `docs/methodology/certification_budget_sensitivity_study_v1.md`
- Create outside Git: `.task26-artifacts/`

- [ ] **Step 1: Run focused tests and static checks**

Run:

```powershell
python -m pytest tests/test_certification_budget_sensitivity_manifest.py tests/test_prepare_certification_budget_sensitivity.py tests/test_certification_budget_sensitivity_runner.py tests/test_certification_budget_sensitivity_summary.py tests/test_certification_budget_sensitivity_workflow.py -q
ruff check src tests examples benchmarks simulations tools
mypy src/sdna
python -m compileall -q src simulations tools tests
```

Expected: all focused tests pass, Ruff and mypy report no violations, and
compilation succeeds.

- [ ] **Step 2: Run the complete repository suite**

Run: `python -m pytest -q`

Expected: all existing tests and Task 26 tests pass. Keep generated files
under `.task26-artifacts/`; do not modify committed Task 24/25 manifests or
artifacts.

- [ ] **Step 3: Run a local synthetic end-to-end rehearsal**

Build a small selection fixture with one cap-3-only key, one cap-4-only key,
and one overlapping key. Run each budget-arm function with mocked workflow
stages, validate each output, aggregate the four arms, and assert that the
combined output has one row per `(pairing_key, candidate_cap, budget)`, that
the overlap contributes two cap-specific rows, and that changing the budget
changes only certification diagnostics.

- [ ] **Step 4: Record implementation traceability before dispatch**

Run `git status --short`, `git diff --check`, and `git rev-parse HEAD`. Add the
plan commit and all implementation commit hashes to ADR-025. Confirm the
working tree is clean and that the workflow references the committed fixed
manifest and pinned Task 25 artifact.

- [ ] **Step 5: Dispatch the manual Actions workflow**

Dispatch `.github/workflows/certification-budget-sensitivity.yml` from the
implementation commit. Confirm the preparation job validates Task 25 before
selection, all four fixed-budget jobs publish arm artifacts, and the
aggregation job writes a complete result or an explicit incomplete report.

- [ ] **Step 6: Verify hosted artifacts and post-run checks**

For a complete run, verify 44 cap-3 and 68 cap-4 rows per budget, 448
combined rows, exact selection keys, source checksums, environment versions,
arm statuses, per-budget yields, reason counts, budget exhaustion, and runtime
against the committed schema. For any incomplete arm, verify that its missing
rows are not counted as zero certification yield and that the aggregate
completion check is false.

- [ ] **Step 7: Record hosted evidence without changing the protocol**

Add the exact Actions run ID, source/implementation commit, artifact names,
all output checksums, Python/NumPy versions, runtime and timeout status,
overlap count, cap/budget yields, reason counts, and practical runtime limits
to ADR-025 and the methodology page. Interpret any yield increase only as a
budget sensitivity finding for the fixed Task 25 population. Do not change
the production budget, promote a cap, or add a new arm in response to the
result.

- [ ] **Step 8: Commit the hosted evidence record**

```powershell
git add docs/development/decisions.md docs/methodology/certification_budget_sensitivity_study_v1.md
git commit -m "docs: record certification budget sensitivity evidence"
```

## Self-review checklist

- Every section of the approved Task 26 specification maps to a concrete task,
  file, test, or hosted acceptance check.
- The source artifact is validated before `U_to_R` selection, and the exact
  selection is serialized for every budget job.
- Overlapping cap populations remain separate; no report claims 112 unique
  pairing keys.
- The four budgets are fixed before execution and cannot be extended based on
  interim results.
- The runner shares one dataset per pairing key within an arm, reproduces the
  Task 25 digest and child seeds, and remains order-independent across budgets.
- Row-level budget exhaustion and arm-level timeout/failure/incompleteness are
  separate machine-readable states.
- Incomplete arms retain diagnostic rows but have no certification yield and
  cannot produce a complete sensitivity conclusion.
- Source comparison reuses the established Task 25 comparator and permits only
  the approved `1e-12` numeric tolerance plus expected certification diagnostics
  and elapsed-time differences.
- The existing production cap-2 configuration and Task 25 artifacts are not
  modified.
- The Actions workflow is manual-only and uploads artifacts on success and
  failure paths.
- Documentation and ADR-025 identify the exact commits and files needed for an
  independent reviewer to reproduce and audit the evidence.
