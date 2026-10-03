import numpy as np
import pytest

from simulations.edge_recovery import (
    edge_recovery_metrics,
    ordinary_partial_correlation,
    recovery_row,
)


def _truth() -> np.ndarray:
    truth = np.eye(4)
    truth[0, 1] = truth[1, 0] = 0.4
    truth[2, 3] = truth[3, 2] = -0.3
    return truth


def test_perfect_estimate_has_perfect_recovery() -> None:
    truth = _truth()
    result = edge_recovery_metrics(truth, truth)

    assert result["n_true_edges"] == 2.0
    assert result["sign_agreement"] == 1.0
    assert result["rank_correlation"] == pytest.approx(1.0)
    assert result["edge_auc"] == 1.0
    assert result["top_k_precision"] == 1.0
    assert result["magnitude_ratio"] == pytest.approx(1.0)


def test_shrunk_estimate_preserves_signs_but_reports_attenuation() -> None:
    truth = _truth()
    estimated = np.eye(4) + 0.25 * (truth - np.eye(4))
    result = edge_recovery_metrics(estimated, truth)

    assert result["sign_agreement"] == 1.0
    assert result["magnitude_ratio"] == pytest.approx(0.25)


def test_flipped_sign_is_detected() -> None:
    truth = _truth()
    estimated = truth.copy()
    estimated[0, 1] = estimated[1, 0] = -0.4
    result = edge_recovery_metrics(estimated, truth)

    assert result["sign_agreement"] == 0.5


def test_metrics_are_none_not_zero_when_undefined() -> None:
    null_truth = np.eye(3)
    result = edge_recovery_metrics(np.eye(3), null_truth)

    assert result["n_true_edges"] == 0.0
    assert result["sign_agreement"] is None
    assert result["edge_auc"] is None
    assert result["rank_correlation"] is None
    assert result["magnitude_ratio"] is None


def test_shape_mismatch_rejected() -> None:
    with pytest.raises(ValueError, match="equal-shaped"):
        edge_recovery_metrics(np.eye(3), np.eye(4))


def test_ordinary_partial_requires_enough_rows() -> None:
    rng = np.random.default_rng(0)
    assert ordinary_partial_correlation(rng.normal(size=(5, 5))) is None
    assert ordinary_partial_correlation(rng.normal(size=(50, 5))) is not None


def test_recovery_row_has_shrunk_and_ordinary_fields() -> None:
    rng = np.random.default_rng(1)
    truth = _truth()
    row = recovery_row(rng.normal(size=(60, 4)), truth)

    assert 0.0 <= row["lambda"] <= 1.0  # type: ignore[operator]
    assert "shrunk_sign_agreement" in row and "ordinary_edge_auc" in row
    assert row["n_true_edges"] == 2.0
