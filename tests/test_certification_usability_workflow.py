"""Tests for the Task 25 methodology page and manual workflow contract."""

from pathlib import Path

METHODOLOGY_PATH = Path("docs/methodology/certification_usability_study_v1.md")
WORKFLOW_PATH = Path(".github/workflows/certification-usability.yml")


def test_certification_usability_methodology_page_declares_study_contract() -> None:
    text = METHODOLOGY_PATH.read_text(encoding="utf-8")

    for required in (
        "U_to_R",
        "certification yield",
        "not_applicable_prior_error",
        "combination_budget_exhausted",
        "20260910",
        "1000",
        "900",
        "Phase A",
        "Phase B",
        "cap 2 remains",
    ):
        assert required in text


def test_certification_usability_workflow_is_manual_only_and_uploads_failures() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    for required in (
        "workflow_dispatch:",
        "34871220664",
        "tools.audit_certification_usability",
        "tools.run_certification_usability",
        "--validate",
        "if: always()",
        "retention-days: 90",
    ):
        assert required in text
    for forbidden in ("schedule:", "push:", "pull_request:"):
        assert forbidden not in text
