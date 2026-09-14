"""Tests for the reusable full simulation workflow."""

import numpy as np

from sdna.fragility import FragilityTarget
from simulations.dgp import clean_planted_edge
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
