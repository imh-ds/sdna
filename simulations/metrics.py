"""Dependency-light metrics for SDNA falsification simulations."""

from collections.abc import Iterable, Sequence

import numpy as np


def _as_vector(values: Iterable[float]) -> np.ndarray:
    vector = np.asarray(list(values), dtype=float)
    if vector.ndim != 1 or vector.size == 0:
        raise ValueError("values must be a nonempty one-dimensional sequence")
    return vector


def _ranks(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(values.size, dtype=float)
    sorted_values = values[order]
    start = 0
    while start < values.size:
        end = start + 1
        while end < values.size and sorted_values[end] == sorted_values[start]:
            end += 1
        ranks[order[start:end]] = (start + end - 1) / 2.0 + 1.0
        start = end
    return ranks


def spearman_correlation(x: Iterable[float], y: Iterable[float]) -> float:
    """Compute tie-aware Spearman correlation without SciPy."""
    first, second = _as_vector(x), _as_vector(y)
    if first.size != second.size:
        raise ValueError("x and y must have equal length")
    first_ranks, second_ranks = _ranks(first), _ranks(second)
    if np.std(first_ranks) == 0.0 or np.std(second_ranks) == 0.0:
        return 0.0
    return float(np.corrcoef(first_ranks, second_ranks)[0, 1])


def auc(labels: Iterable[int], scores: Iterable[float]) -> float:
    """Compute binary ROC AUC by positive/negative pair comparison."""
    truth = np.asarray(list(labels), dtype=int)
    values = _as_vector(scores)
    if truth.size != values.size or not np.all(np.isin(truth, [0, 1])):
        raise ValueError("labels must be binary and match scores")
    positives, negatives = values[truth == 1], values[truth == 0]
    if positives.size == 0 or negatives.size == 0:
        raise ValueError("labels must contain both classes")
    comparisons = positives[:, None] - negatives[None, :]
    wins = np.count_nonzero(comparisons > 0)
    ties = np.count_nonzero(comparisons == 0)
    return float((wins + 0.5 * ties) / comparisons.size)


def partial_rank_association(
    x: Iterable[float], y: Iterable[float], controls: Sequence[Iterable[float]]
) -> float:
    """Compute rank association between x and y after linear rank adjustment."""
    first, second = _as_vector(x), _as_vector(y)
    control_matrix = np.column_stack([_ranks(_as_vector(control)) for control in controls])
    if first.size != second.size or control_matrix.shape[0] != first.size:
        raise ValueError("all variables must have equal length")
    design = np.column_stack([np.ones(first.size), control_matrix])
    first_residual = _ranks(first) - design @ np.linalg.lstsq(
        design, _ranks(first), rcond=None
    )[0]
    second_residual = _ranks(second) - design @ np.linalg.lstsq(
        design, _ranks(second), rcond=None
    )[0]
    if np.std(first_residual) == 0.0 or np.std(second_residual) == 0.0:
        return 0.0
    return float(np.corrcoef(first_residual, second_residual)[0, 1])


def influence_metrics(
    influence: Iterable[float], planted_cases: Iterable[int], k: int
) -> dict[str, float]:
    """Summarize top-k recovery and absolute influence concentration."""
    values = _as_vector(influence)
    planted = set(int(index) for index in planted_cases)
    if not planted or k < 1:
        raise ValueError("planted_cases must be nonempty and k must be positive")
    if any(index < 0 or index >= values.size for index in planted):
        raise ValueError("planted case index is out of bounds")
    top_indices = np.argsort(-np.abs(values))[:k]
    hits = planted.intersection(top_indices.tolist())
    ranked = np.argsort(-np.abs(values)).tolist()
    first_rank = next(index for index, case in enumerate(ranked, 1) if case in planted)
    total = float(np.sum(np.abs(values)))
    share = 0.0 if total == 0.0 else float(np.sum(np.abs(values[list(planted)])) / total)
    return {
        "top_k_precision": len(hits) / k,
        "top_k_recall": len(hits) / len(planted),
        "first_planted_reciprocal_rank": 1.0 / first_rank,
        "planted_absolute_influence_share": share,
    }


def incremental_auc(
    labels: Iterable[int], baseline: Iterable[float], fragility: Iterable[float]
) -> dict[str, float]:
    """Compare fitted baseline and augmented linear probability scores.

    Predictors are standardized before least-squares fitting to the binary
    labels. The augmented score estimates predictor weights from the data,
    rather than assigning baseline and fragility an arbitrary equal weight.
    AUC is evaluated in-sample and is therefore a scoring benchmark, not an
    estimate of out-of-sample predictive performance.
    """
    base, extra = _as_vector(baseline), _as_vector(fragility)
    if base.size != extra.size:
        raise ValueError("baseline and fragility must have equal length")
    raw_labels = np.asarray(list(labels))
    if raw_labels.ndim != 1 or raw_labels.size != base.size:
        raise ValueError("labels must be binary and match scores")
    if not np.all(np.isin(raw_labels, [0, 1])):
        raise ValueError("labels must be binary and match scores")
    truth = raw_labels.astype(int)

    def fitted_score(predictors: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        scales = np.std(predictors, axis=0)
        standardized = (predictors - np.mean(predictors, axis=0)) / np.where(
            scales == 0.0, 1.0, scales
        )
        design = np.column_stack([np.ones(predictors.shape[0]), standardized])
        coefficients = np.linalg.lstsq(design, truth, rcond=None)[0]
        return design @ coefficients, coefficients

    baseline_score, baseline_coefficients = fitted_score(base[:, None])
    augmented_score, augmented_coefficients = fitted_score(
        np.column_stack([base, extra])
    )
    return {
        "baseline_auc": auc(truth, baseline_score),
        "augmented_auc": auc(truth, augmented_score),
        "baseline_coefficient": float(baseline_coefficients[1]),
        "augmented_baseline_coefficient": float(augmented_coefficients[1]),
        "augmented_fragility_coefficient": float(augmented_coefficients[2]),
    }
