"""Tests for the Task 25 Phase A artifact audit."""

from collections.abc import Iterable

import pytest

from tools.audit_certification_usability import (
    UNAVAILABLE_FIELDS,
    _render_markdown,
    identify_newly_reached_pairs,
)


def audit_row(
    arm: str,
    replication: int,
    fragility_status: str,
    *,
    certification_status: str = "skipped_unreached",
    workflow_status: str = "partial",
) -> dict[str, object]:
    return {
        "arm": arm,
        "scenario": "clean_planted_edge",
        "parameter_id": 0,
        "parameter": 0.2,
        "replication": replication,
        "N": 50,
        "p": 5,
        "data_seed": 100 + replication,
        "calibration_seed": 200 + replication,
        "bootstrap_seed": 300 + replication,
        "dataset_digest": "a" * 64,
        "fragility_status": fragility_status,
        "certification_status": certification_status,
        "calibration_status": "observed_unreached",
        "wald_status": "ok",
        "bootstrap_status": "ok",
        "workflow_status": workflow_status,
        "certified": None,
        "exact_fragility_50": None,
        "reference_tail_probability": None,
        "reference_reached_fraction": None,
        "bootstrap_rejected_resamples": 0,
        "error_stage": "certification" if workflow_status == "error" else None,
        "error_type": "RuntimeError" if workflow_status == "error" else None,
        "error_message": "synthetic certification failure" if workflow_status == "error" else None,
    }


def paired_rows(rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    return list(rows)


def test_identify_newly_reached_pairs_uses_exact_candidate_transitions() -> None:
    rows = paired_rows(
        [
            audit_row("baseline_cap2", 0, "unreached"),
            audit_row(
                "cap3",
                0,
                "reached",
                certification_status="error",
                workflow_status="error",
            ),
            audit_row("cap4", 0, "unreached"),
            audit_row("baseline_cap2", 1, "unreached"),
            audit_row("cap3", 1, "unreached"),
            audit_row("cap4", 1, "reached", certification_status="not_certified"),
            audit_row("baseline_cap2", 2, "reached", certification_status="certified"),
            audit_row("cap3", 2, "reached", certification_status="certified"),
            audit_row("cap4", 2, "reached", certification_status="certified"),
        ]
    )

    pairs = identify_newly_reached_pairs(rows)

    assert [pair["pair_key"] for pair in pairs["cap3"]] == [
        ("clean_planted_edge", 50, 5, 0, 0)
    ]
    assert [pair["pair_key"] for pair in pairs["cap4"]] == [
        ("clean_planted_edge", 50, 5, 0, 1)
    ]
    assert pairs["cap3"][0]["candidate"]["workflow_status"] == "error"


def test_identify_newly_reached_pairs_rejects_duplicate_pair_members() -> None:
    rows = paired_rows(
        [
            audit_row("baseline_cap2", 0, "unreached"),
            audit_row("baseline_cap2", 0, "unreached"),
            audit_row("cap3", 0, "reached"),
            audit_row("cap4", 0, "reached"),
        ]
    )

    with pytest.raises(ValueError, match="duplicate"):
        identify_newly_reached_pairs(rows)


def test_identify_newly_reached_pairs_rejects_missing_arm() -> None:
    rows = paired_rows(
        [
            audit_row("baseline_cap2", 0, "unreached"),
            audit_row("cap3", 0, "reached"),
        ]
    )

    with pytest.raises(ValueError, match="all three arms"):
        identify_newly_reached_pairs(rows)


def test_identify_newly_reached_pairs_excludes_candidate_unreached_rows() -> None:
    rows = paired_rows(
        [
            audit_row("baseline_cap2", 0, "unreached"),
            audit_row("cap3", 0, "unreached"),
            audit_row("cap4", 0, "unreached"),
        ]
    )

    pairs = identify_newly_reached_pairs(rows)

    assert pairs == {"cap3": [], "cap4": []}


def test_phase_a_markdown_reports_denominators_and_unavailable_fields() -> None:
    markdown = _render_markdown(
        {
            "source": {
                "run_id": "run",
                "commit": "commit",
                "artifact": "artifact",
                "results_sha256": "digest",
            },
            "audit_commit": "audit",
            "candidate_caps": [3, 4],
            "populations": {
                "cap3": {"rows": 2, "certified_rows": 0, "certification_yield": 0.0},
                "cap4": {"rows": 3, "certified_rows": 1, "certification_yield": 1 / 3},
            },
            "unavailable_fields": UNAVAILABLE_FIELDS,
        }
    )

    assert "| 3 | 2 | 0 | 0.0 |" in markdown
    assert "| 4 | 3 | 1 | 0.3333333333333333 |" in markdown
    for field in UNAVAILABLE_FIELDS:
        assert f"- `{field}`" in markdown
