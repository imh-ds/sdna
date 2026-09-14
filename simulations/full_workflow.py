"""Reusable, status-aware execution of the complete SDNA simulation workflow."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from sdna.calibration import calibrate_fragility
from sdna.estimation import fit_network
from sdna.exceptions import CalibrationError
from sdna.fragility import FragilityTarget, certify_fragility, greedy_fragility
from sdna.influence import exact_loo_influence
from simulations.comparators.bootstrap import shrinkage_bootstrap
from simulations.comparators.wald import wald_partial_correlation
from simulations.dgp import SimulatedDataset
from simulations.metrics import influence_metrics


@dataclass(frozen=True)
class WorkflowSeeds:
    """Named deterministic child seeds for stochastic workflow stages."""

    calibration: int
    bootstrap: int


_STAGE_ERRORS = (CalibrationError, FloatingPointError, np.linalg.LinAlgError, RuntimeError, ValueError)


def derive_workflow_seeds(row_seed: int) -> WorkflowSeeds:
    """Derive independent, reproducible integer seeds for calibration/bootstrap."""
    if isinstance(row_seed, bool) or not isinstance(row_seed, int) or row_seed < 0:
        raise ValueError("row_seed must be a nonnegative integer")
    calibration, bootstrap = np.random.SeedSequence(row_seed).spawn(2)
    return WorkflowSeeds(
        calibration=int(calibration.generate_state(1, dtype=np.uint32)[0]),
        bootstrap=int(bootstrap.generate_state(1, dtype=np.uint32)[0]),
    )


def dataset_digest(dataset: SimulatedDataset) -> str:
    """Return a stable digest of the generated observation matrix."""
    data = np.ascontiguousarray(dataset.X)
    digest = hashlib.sha256()
    digest.update(str(data.shape).encode("ascii"))
    digest.update(data.dtype.str.encode("ascii"))
    digest.update(data.tobytes(order="C"))
    return digest.hexdigest()


def _error_fields(stage: str, error: Exception) -> dict[str, str]:
    return {
        "error_stage": stage,
        "error_type": type(error).__name__,
        "error_message": str(error),
    }


def _set_error(result: dict[str, Any], stage: str, error: Exception) -> None:
    result[f"{stage}_status"] = "error"
    if result["error_stage"] is None:
        result.update(_error_fields(stage, error))


def _initial_result(dataset: SimulatedDataset) -> dict[str, Any]:
    edge = dataset.focal_edge
    return {
        "true_rho": float(dataset.partial_correlation[edge]),
        "observed_rho": None,
        "lambda": None,
        "contamination_count": len(dataset.contaminated_cases),
        "contamination_status": int(bool(dataset.contaminated_cases)),
        "greedy_fragility_50": None,
        "exact_fragility_50": None,
        "certified": None,
        "reached": None,
        "reference_tail_probability": None,
        "reference_reached_fraction": None,
        "wald_z": None,
        "bootstrap_ci_excludes_zero": None,
        "bootstrap_rejected_resamples": None,
        "influence_top_k_precision": None,
        "influence_top_k_recall": None,
        "first_planted_reciprocal_rank": None,
        "planted_absolute_influence_share": None,
        "fragility_status": "error",
        "certification_status": "error",
        "calibration_status": "error",
        "wald_status": "error",
        "bootstrap_status": "error",
        "workflow_status": "error",
        "error_stage": None,
        "error_type": None,
        "error_message": None,
    }


def _finish_status(result: dict[str, Any]) -> None:
    if result["error_stage"] is not None or any(
        result[field] == "error"
        for field in (
            "fragility_status",
            "certification_status",
            "calibration_status",
            "wald_status",
            "bootstrap_status",
        )
    ):
        result["workflow_status"] = "error"
    elif result["fragility_status"] == "unreached" or result["calibration_status"] == (
        "observed_unreached"
    ):
        result["workflow_status"] = "partial"
    else:
        result["workflow_status"] = "ok"


def run_full_workflow(
    dataset: SimulatedDataset,
    *,
    target: FragilityTarget,
    search_cap: int | None,
    calibration_simulations: int,
    bootstrap_samples: int,
    bootstrap_confidence: float,
    certification_combination_budget: int,
    seeds: WorkflowSeeds,
    calibration_require_reached: bool = False,
    calibration_fn: Callable[..., Any] = calibrate_fragility,
    wald_fn: Callable[..., Any] = wald_partial_correlation,
    bootstrap_fn: Callable[..., Any] = shrinkage_bootstrap,
) -> dict[str, Any]:
    """Run every declared estimator stage and preserve stage outcomes."""
    result = _initial_result(dataset)
    edge = dataset.focal_edge

    try:
        fitted = fit_network(dataset.X)
        result["lambda"] = fitted.shrinkage
        result["observed_rho"] = float(fitted.partial_correlation[edge])
    except _STAGE_ERRORS as error:
        for stage in ("fragility", "certification", "calibration", "wald", "bootstrap"):
            result[f"{stage}_status"] = "error"
        result.update(_error_fields("fit", error))
        _finish_status(result)
        return result

    try:
        greedy = greedy_fragility(
            dataset.X,
            edge=edge,
            target=target,
            shrinkage=fitted.shrinkage,
            search_cap=search_cap,
        )
        result["reached"] = greedy.reached
        result["greedy_fragility_50"] = greedy.greedy_count
        result["fragility_status"] = "reached" if greedy.reached else "unreached"
    except _STAGE_ERRORS as error:
        _set_error(result, "fragility", error)
        greedy = None

    if greedy is not None and greedy.reached:
        try:
            certified = certify_fragility(
                dataset.X,
                greedy,
                shrinkage=fitted.shrinkage,
                max_combinations=certification_combination_budget,
            )
            result["exact_fragility_50"] = certified.exact_minimum
            result["certified"] = certified.certified
            result["certification_status"] = (
                "certified" if certified.certified else "not_certified"
            )
        except _STAGE_ERRORS as error:
            _set_error(result, "certification", error)
    elif greedy is not None:
        result["certification_status"] = "skipped_unreached"

    try:
        calibration = calibration_fn(
            dataset.X,
            edge=edge,
            target=target,
            n_sim=calibration_simulations,
            rng=np.random.default_rng(seeds.calibration),
            shrinkage=fitted.shrinkage,
            search_cap=search_cap,
            require_reached=calibration_require_reached,
        )
        result["reference_tail_probability"] = calibration.reference_tail_probability
        result["reference_reached_fraction"] = sum(calibration.reference_reached) / len(
            calibration.reference_reached
        )
        observed_reached = getattr(
            calibration,
            "observed_reached",
            calibration.reference_tail_probability is not None,
        )
        if not observed_reached:
            result["calibration_status"] = "observed_unreached"
        elif all(calibration.reference_reached):
            result["calibration_status"] = "finite"
        else:
            result["calibration_status"] = "right_censored"
    except _STAGE_ERRORS as error:
        _set_error(result, "calibration", error)

    try:
        wald = wald_fn(dataset.X, edge=edge, confidence=bootstrap_confidence)
        result["wald_z"] = wald.z
        result["wald_status"] = "ok"
    except _STAGE_ERRORS as error:
        _set_error(result, "wald", error)

    try:
        bootstrap = bootstrap_fn(
            dataset.X,
            edge=edge,
            n_boot=bootstrap_samples,
            rng=np.random.default_rng(seeds.bootstrap),
            shrinkage=fitted.shrinkage,
            confidence=bootstrap_confidence,
        )
        result["bootstrap_ci_excludes_zero"] = (
            bootstrap.confidence_interval[0] > 0.0 or bootstrap.confidence_interval[1] < 0.0
        )
        result["bootstrap_rejected_resamples"] = bootstrap.rejected_resamples
        result["bootstrap_status"] = "ok"
    except _STAGE_ERRORS as error:
        _set_error(result, "bootstrap", error)

    if dataset.contaminated_cases:
        try:
            influence = exact_loo_influence(dataset.X, fitted).changes[:, edge[0], edge[1]]
            metrics = influence_metrics(
                influence,
                dataset.contaminated_cases,
                len(dataset.contaminated_cases),
            )
            result.update(
                {
                    "influence_top_k_precision": metrics["top_k_precision"],
                    "influence_top_k_recall": metrics["top_k_recall"],
                    "first_planted_reciprocal_rank": metrics[
                        "first_planted_reciprocal_rank"
                    ],
                    "planted_absolute_influence_share": metrics[
                        "planted_absolute_influence_share"
                    ],
                }
            )
        except _STAGE_ERRORS as error:
            if result["error_stage"] is None:
                result.update(_error_fields("influence", error))

    _finish_status(result)
    return result
