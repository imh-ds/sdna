"""Contract tests for the manual Task 26 Actions workflow."""

from pathlib import Path

WORKFLOW_PATH = Path(".github/workflows/certification-budget-sensitivity.yml")
METHODOLOGY_PATH = Path("docs/methodology/certification_budget_sensitivity_study_v1.md")


def test_budget_sensitivity_workflow_is_manual_fixed_matrix() -> None:
    """Catch a workflow that can run outside the fixed Task 26 evidence contract."""
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    for required in (
        "workflow_dispatch:",
        "contents: read",
        "actions: read",
        "34895397606",
        "sdna-certification-usability-34895397606",
        "matrix:",
        "budget: [1000, 5000, 10000, 20000]",
        "fail-fast: false",
        "timeout-minutes: 40",
        "if: always()",
        "continue-on-error: true",
        "tools.prepare_certification_budget_sensitivity",
        "tools.run_certification_budget_sensitivity",
        "tools.summarize_certification_budget_sensitivity",
        "actions/checkout@v7.0.1",
        "actions/setup-python@v7.0.0",
        "actions/upload-artifact@v7.0.1",
        "GH_TOKEN: ${{ github.token }}",
        "gh run download",
        "retention-days: 90",
        "complete_sensitivity_result",
    ):
        assert required in text
    for forbidden in ("schedule:", "push:", "pull_request:"):
        assert forbidden not in text


def test_aggregate_downloads_do_not_mask_missing_artifacts() -> None:
    """Catch aggregate staging that skips arm downloads or manufactures arm directories."""
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert (
        '"sdna-certification-budget-selection-$GITHUB_RUN_ID" --dir "$PREPARATION_DIR" || true'
        in text
    )
    assert 'mkdir -p "$ARMS_DIR/$budget"' not in text
    assert '"sdna-certification-budget-arm-$budget-$GITHUB_RUN_ID"' in text


def test_budget_matrix_does_not_continue_after_workflow_cancellation() -> None:
    """Allow failed preparation but stop expensive matrix jobs on cancellation."""
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    run_budget = text.split("  run-budget:\n", maxsplit=1)[1].split("\n  aggregate:", maxsplit=1)[0]
    job_condition = next(
        line.strip()
        for line in run_budget.splitlines()
        if line.startswith("    if:") and not line.startswith("      ")
    )

    assert job_condition == "if: ${{ always() && !cancelled() }}"


def test_methodology_pre_specifies_the_budget_sensitivity_contract() -> None:
    """Catch removal of fixed protocol commitments from the study record."""
    assert METHODOLOGY_PATH.is_file()
    text = METHODOLOGY_PATH.read_text(encoding="utf-8")

    for required in (
        "U_to_R(3)=44",
        "U_to_R(4)=68",
        "[1000, 5000, 10000, 20000]",
        "1800",
        "timeout",
        "combination_budget_exhausted",
        "calibration_require_reached=False",
        "ordinary-partial",
        "not a cap-promotion",
        "overlap",
        "cap 2",
        "incomplete",
    ):
        assert required in text

    for relative_path in (
        "../superpowers/specs/2026-09-14-task26-certification-budget-sensitivity-design.md",
        "../superpowers/plans/2026-09-14-task26-certification-budget-sensitivity.md",
        "../../simulations/configs/certification_budget_sensitivity_v1.json",
        "../../tools/run_certification_budget_sensitivity.py",
        "../../tools/summarize_certification_budget_sensitivity.py",
        "../../.github/workflows/certification-budget-sensitivity.yml",
    ):
        assert f"]({relative_path})" in text
        assert (METHODOLOGY_PATH.parent / relative_path).resolve().is_file()
