"""Tests for the reusable full simulation workflow."""

from dataclasses import replace

import numpy as np
import pytest

from sdna.fragility import FragilityTarget
from sdna.results import FragilityResult
from simulations import full_workflow
from simulations.dgp import clean_planted_edge, coalition_contamination
from simulations.full_workflow import (
    dataset_digest,
    derive_workflow_seeds,
    run_full_workflow,
)


def test_workflow_seeds_and_dataset_digest_are_deterministic() -> None:
    dataset = clean_planted_edge(20, 5, np.random.default_rng(20260910))

    first = derive_workflow_seeds(20260910)
    second = derive_workflow_seeds(20260910)

    assert first == second
    assert first.calibration != first.bootstrap
    assert dataset_digest(dataset) == dataset_digest(dataset)
    assert dataset_digest(dataset) == dataset_digest(
        clean_planted_edge(20, 5, np.random.default_rng(20260910))
    )


def test_full_workflow_reports_all_stage_statuses() -> None:
    dataset = clean_planted_edge(20, 5, np.random.default_rng(7))

    result = run_full_workflow(
        dataset,
        target=FragilityTarget("relative", 0.5),
        search_cap=2,
        calibration_simulations=1,
        bootstrap_samples=2,
        bootstrap_confidence=0.95,
        certification_combination_budget=20,
        seeds=derive_workflow_seeds(7),
    )

    assert {
        "fragility_status",
        "certification_status",
        "calibration_status",
        "wald_status",
        "bootstrap_status",
        "workflow_status",
    } <= set(result)
    assert result["bootstrap_status"] in {"ok", "error"}
    assert result["calibration_status"] in {
        "finite",
        "right_censored",
        "observed_unreached",
        "error",
    }


def test_full_workflow_labels_right_censored_reference_tail() -> None:
    dataset = clean_planted_edge(20, 5, np.random.default_rng(7))

    result = run_full_workflow(
        dataset,
        target=FragilityTarget("relative", 0.5),
        search_cap=2,
        calibration_simulations=1,
        bootstrap_samples=1,
        bootstrap_confidence=0.95,
        certification_combination_budget=20,
        seeds=derive_workflow_seeds(7),
        calibration_fn=lambda *args, **kwargs: type(
            "CalibrationFixture",
            (),
            {
                "reference_tail_probability": 0.25,
                "reference_reached": (True, False),
                "observed_reached": True,
            },
        )(),
    )

    assert result["calibration_status"] == "right_censored"
    assert result["reference_reached_fraction"] == 0.5


def test_full_workflow_preserves_bootstrap_failure_status() -> None:
    dataset = clean_planted_edge(20, 5, np.random.default_rng(7))

    def failing_bootstrap(*args, **kwargs):
        raise RuntimeError("synthetic bootstrap failure")

    result = run_full_workflow(
        dataset,
        target=FragilityTarget("relative", 0.5),
        search_cap=2,
        calibration_simulations=1,
        bootstrap_samples=1,
        bootstrap_confidence=0.95,
        certification_combination_budget=20,
        seeds=derive_workflow_seeds(7),
        bootstrap_fn=failing_bootstrap,
    )

    assert result["bootstrap_status"] == "error"
    assert result["workflow_status"] == "error"
    assert result["error_stage"] == "bootstrap"


def test_full_workflow_labels_influence_failure_as_workflow_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = coalition_contamination(20, 5, np.random.default_rng(7))

    def failing_influence(*args, **kwargs):
        raise RuntimeError("synthetic influence failure")

    monkeypatch.setattr(full_workflow, "exact_loo_influence", failing_influence)
    result = run_full_workflow(
        dataset,
        target=FragilityTarget("relative", 0.5),
        search_cap=2,
        calibration_simulations=1,
        bootstrap_samples=1,
        bootstrap_confidence=0.95,
        certification_combination_budget=20,
        seeds=derive_workflow_seeds(7),
    )

    assert result["workflow_status"] == "error"
    assert result["error_stage"] == "influence"


def _workflow_fragility_result(reached: bool) -> FragilityResult:
    target = FragilityTarget("relative", 0.5)
    return FragilityResult(
        edge=(0, 1),
        target=target,
        full_value=0.2,
        reached=reached,
        greedy_count=2 if reached else None,
        cases=(),
        trajectory=np.array([0.2]),
        shrinkage=0.1,
    )


def _run_diagnostic_workflow(
    monkeypatch: pytest.MonkeyPatch,
    *,
    greedy_result: FragilityResult,
    certification_result: FragilityResult | None = None,
    certification_error: Exception | None = None,
    patch_certification: bool = True,
) -> dict[str, object]:
    dataset = clean_planted_edge(20, 5, np.random.default_rng(7))
    monkeypatch.setattr(full_workflow, "greedy_fragility", lambda *args, **kwargs: greedy_result)
    if not patch_certification:
        pass
    elif certification_error is not None:
        def raise_certification_error(*args, **kwargs):
            raise certification_error

        monkeypatch.setattr(full_workflow, "certify_fragility", raise_certification_error)
    else:
        assert certification_result is not None
        monkeypatch.setattr(
            full_workflow,
            "certify_fragility",
            lambda *args, **kwargs: certification_result,
        )
    return full_workflow.run_full_workflow(
        dataset,
        target=FragilityTarget("relative", 0.5),
        search_cap=2,
        calibration_simulations=1,
        bootstrap_samples=1,
        bootstrap_confidence=0.95,
        certification_combination_budget=20,
        seeds=derive_workflow_seeds(7),
    )


def test_full_workflow_records_unreached_certification_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run_diagnostic_workflow(
        monkeypatch,
        greedy_result=_workflow_fragility_result(False),
        certification_result=None,
        patch_certification=False,
    )

    assert result["certification_status"] == "skipped_unreached"
    assert result["certification_failure_reason"] == "not_applicable_unreached"
    assert result["certification_budget_exhausted"] is False
    assert result["certification_combinations_checked"] == 0


def test_full_workflow_records_successful_certification_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    certified = _workflow_fragility_result(True)
    certified = replace(
        certified,
        certified=True,
        exact_minimum=1,
        combinations_checked=4,
    )
    result = _run_diagnostic_workflow(
        monkeypatch,
        greedy_result=_workflow_fragility_result(True),
        certification_result=certified,
    )

    assert result["certification_failure_reason"] == "certified"
    assert result["certification_budget_exhausted"] is False
    assert result["certification_combinations_checked"] == 4
    assert result["certification_combination_budget"] == 20


def test_full_workflow_records_budget_exhaustion_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    not_certified = _workflow_fragility_result(True)
    not_certified = replace(not_certified, certified=False, combinations_checked=4)
    result = _run_diagnostic_workflow(
        monkeypatch,
        greedy_result=_workflow_fragility_result(True),
        certification_result=not_certified,
    )

    assert result["certification_failure_reason"] == "combination_budget_exhausted"
    assert result["certification_budget_exhausted"] is True
    assert result["certification_combinations_checked"] == 4


def test_full_workflow_records_prior_error_diagnostic(monkeypatch: pytest.MonkeyPatch) -> None:
    dataset = clean_planted_edge(20, 5, np.random.default_rng(7))

    def failing_fit(*args, **kwargs):
        raise RuntimeError("synthetic fit failure")

    monkeypatch.setattr(full_workflow, "fit_network", failing_fit)
    result = full_workflow.run_full_workflow(
        dataset,
        target=FragilityTarget("relative", 0.5),
        search_cap=2,
        calibration_simulations=1,
        bootstrap_samples=1,
        bootstrap_confidence=0.95,
        certification_combination_budget=20,
        seeds=derive_workflow_seeds(7),
    )

    assert result["certification_failure_reason"] == "not_applicable_prior_error"
    assert result["certification_combinations_checked"] is None


def test_full_workflow_records_certification_error_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run_diagnostic_workflow(
        monkeypatch,
        greedy_result=_workflow_fragility_result(True),
        certification_error=RuntimeError("synthetic certification failure"),
    )

    assert result["certification_status"] == "error"
    assert result["certification_failure_reason"] == "error"
    assert result["certification_budget_exhausted"] is False
