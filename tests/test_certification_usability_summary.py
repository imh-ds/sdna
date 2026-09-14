"""Tests for certification-usability summaries and reference validation."""

import importlib
from collections.abc import Sequence
from pathlib import Path

import pytest

from tools.cap_expansion_manifest import load_cap_expansion_manifest
from tools.certification_usability_manifest import load_certification_usability_manifest
from tools.summarize_certification_usability import (
    _summarize_population,
    _validate_diagnostic_row,
    compare_instrumented_rows_to_reference,
    summarize_certification_usability,
    validate_certification_usability,
)

summary_module = importlib.import_module("tools.summarize_certification_usability")

SOURCE_MANIFEST_PATH = Path("simulations/configs/cap_expansion_v1.json")
AUDIT_MANIFEST_PATH = Path("simulations/configs/certification_usability_v1.json")


def instrumented_row(
    arm: str,
    replication: int,
    fragility_status: str,
    *,
    certification_status: str,
    reason: str,
    workflow_status: str = "ok",
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
        "calibration_status": "finite" if fragility_status == "reached" else "observed_unreached",
        "wald_status": "ok",
        "bootstrap_status": "ok",
        "workflow_status": workflow_status,
        "certified": certification_status == "certified" if fragility_status == "reached" else None,
        "exact_fragility_50": 1 if certification_status == "certified" else None,
        "reference_tail_probability": 0.1 if fragility_status == "reached" else None,
        "reference_reached_fraction": 1.0 if fragility_status == "reached" else 0.0,
        "bootstrap_rejected_resamples": 0,
        "certification_combinations_checked": 4 if fragility_status == "reached" else 0,
        "certification_combination_budget": 1000,
        "certification_budget_exhausted": reason == "combination_budget_exhausted",
        "certification_failure_reason": reason,
        "error_stage": None,
        "error_type": None,
        "error_message": None,
        "observed_rho": 0.2,
    }


def paired_rows(rows: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    return list(rows)


def test_summary_reports_certification_yield_and_stratified_denominators() -> None:
    manifest = load_cap_expansion_manifest(SOURCE_MANIFEST_PATH)
    audit_manifest = load_certification_usability_manifest(AUDIT_MANIFEST_PATH)
    rows = paired_rows(
        [
            instrumented_row("baseline_cap2", 0, "unreached", certification_status="skipped_unreached", reason="not_applicable_unreached"),
            instrumented_row("cap3", 0, "reached", certification_status="certified", reason="certified"),
            instrumented_row("cap4", 0, "unreached", certification_status="skipped_unreached", reason="not_applicable_unreached"),
            instrumented_row("baseline_cap2", 1, "unreached", certification_status="skipped_unreached", reason="not_applicable_unreached"),
            instrumented_row("cap3", 1, "unreached", certification_status="skipped_unreached", reason="not_applicable_unreached"),
            instrumented_row("cap4", 1, "reached", certification_status="not_certified", reason="combination_budget_exhausted"),
            instrumented_row("baseline_cap2", 2, "reached", certification_status="certified", reason="certified"),
            instrumented_row("cap3", 2, "reached", certification_status="certified", reason="certified"),
            instrumented_row("cap4", 2, "reached", certification_status="certified", reason="certified"),
        ]
    )

    summary = summarize_certification_usability(rows, manifest, audit_manifest)

    assert summary["populations"]["cap3"]["rows"] == 1
    assert summary["populations"]["cap3"]["certified_rows"] == 1
    assert summary["populations"]["cap3"]["certification_yield"] == 1.0
    assert summary["populations"]["cap4"]["rows"] == 1
    assert summary["populations"]["cap4"]["certified_rows"] == 0
    assert summary["populations"]["cap4"]["reason_counts"] == {
        "combination_budget_exhausted": 1
    }
    assert summary["populations"]["cap3"]["strata"]["clean_planted_edge|50|5"]["rows"] == 1


@pytest.mark.parametrize("field", ["data_seed", "dataset_digest", "workflow_status"])
def test_reference_comparison_rejects_original_field_mutations(field: str) -> None:
    reference = [instrumented_row("cap3", 0, "reached", certification_status="certified", reason="certified")]
    mutated = [dict(reference[0])]
    mutated[0][field] = "different" if field != "workflow_status" else "error"

    with pytest.raises(ValueError, match=field):
        compare_instrumented_rows_to_reference(mutated, reference)


def test_reference_comparison_accepts_cross_runtime_numeric_rounding() -> None:
    reference = [instrumented_row("cap3", 0, "reached", certification_status="certified", reason="certified")]
    rounded = [dict(reference[0])]
    rounded[0]["observed_rho"] = 0.2000000000001

    compare_instrumented_rows_to_reference(rounded, reference)


def test_summary_counts_serialized_budget_exhaustion_flag() -> None:
    row = instrumented_row(
        "cap3",
        0,
        "reached",
        certification_status="not_certified",
        reason="combination_budget_exhausted",
    )
    row["certification_budget_exhausted"] = "True"

    population = _summarize_population(
        [{"candidate": row, "pair_key": ("clean_planted_edge", 50, 5, 0, 0)}]
    )

    assert population["budget_exhausted_rows"] == 1


def test_reference_comparison_rejects_substantive_numeric_change() -> None:
    reference = [instrumented_row("cap3", 0, "reached", certification_status="certified", reason="certified")]
    changed = [dict(reference[0])]
    changed[0]["observed_rho"] = 0.21

    with pytest.raises(ValueError, match="observed_rho"):
        compare_instrumented_rows_to_reference(changed, reference)


def test_diagnostic_validator_accepts_certified_row() -> None:
    row = instrumented_row(
        "cap3",
        0,
        "reached",
        certification_status="certified",
        reason="certified",
    )

    _validate_diagnostic_row(
        row,
        {
            "not_applicable_unreached",
            "not_applicable_prior_error",
            "certified",
            "combination_budget_exhausted",
            "not_certified_other",
            "error",
        },
        1000,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("certification_failure_reason", "unexpected"),
        ("certification_combination_budget", 999),
        ("certification_budget_exhausted", True),
        ("certification_combinations_checked", -1),
    ],
)
def test_diagnostic_validator_rejects_inconsistent_row(field: str, value: object) -> None:
    row = instrumented_row(
        "cap3",
        0,
        "reached",
        certification_status="certified",
        reason="certified",
    )
    row[field] = value

    with pytest.raises(ValueError):
        _validate_diagnostic_row(
            row,
            {
                "not_applicable_unreached",
                "not_applicable_prior_error",
                "certified",
                "combination_budget_exhausted",
                "not_certified_other",
                "error",
            },
            1000,
        )


def test_reference_validator_passes_source_manifest_path_to_cap_validator(
    tmp_path: Path, monkeypatch
) -> None:
    source_manifest = tmp_path / "cap-expansion.json"
    audit_manifest = tmp_path / "certification-usability.json"
    source_manifest.write_text("{}", encoding="utf-8")
    audit_manifest.write_text("{}", encoding="utf-8")
    for name in ("results.csv", "results.metadata.json", "summary.json"):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    audit_config = {"source_results_sha256": "source-digest"}
    manifest = {"expected_rows": 0}
    expected_fields = summary_module.CAP_EXPANSION_FIELDNAMES + summary_module.CERTIFICATION_DIAGNOSTIC_FIELDNAMES
    seen: list[object] = []

    def fake_validate(*args: object) -> None:
        seen.append(args[3])

    monkeypatch.setattr(summary_module, "load_cap_expansion_manifest", lambda _: manifest)
    monkeypatch.setattr(summary_module, "load_certification_usability_manifest", lambda _: audit_config)
    monkeypatch.setattr(summary_module, "validate_cap_expansion", fake_validate)
    monkeypatch.setattr(summary_module, "_sha256_file", lambda _: "source-digest")
    monkeypatch.setattr(summary_module, "_read_rows", lambda _: (expected_fields, []))
    monkeypatch.setattr(summary_module, "_validate_instrumented_rows", lambda *args: None)
    monkeypatch.setattr(summary_module, "compare_instrumented_rows_to_reference", lambda *args: None)
    monkeypatch.setattr(summary_module, "_validate_metadata", lambda *args: None)
    monkeypatch.setattr(summary_module, "summarize_certification_usability", lambda *args: {})
    monkeypatch.setattr(summary_module, "_metadata_provenance", lambda _: {})
    monkeypatch.setattr(summary_module, "_summaries_match", lambda *args: True)

    validate_certification_usability(
        tmp_path / "results.csv",
        tmp_path / "results.metadata.json",
        tmp_path / "summary.json",
        tmp_path / "source-results.csv",
        tmp_path / "source-metadata.json",
        tmp_path / "source-summary.json",
        source_manifest,
        audit_manifest,
    )

    assert seen == [source_manifest]
