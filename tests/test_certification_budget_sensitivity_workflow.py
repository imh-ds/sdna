"""Contract tests for the manual Task 26 Actions workflow."""

from pathlib import Path

WORKFLOW_PATH = Path(".github/workflows/certification-budget-sensitivity.yml")


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
