import numpy as np

from simulations.ebic_glasso import ebic_glasso
from simulations.edge_recovery import edge_recovery_metrics
from tools.run_estimator_comparison import run, summarize

SMALL = {"n_values": (50,), "truth_draws": 20_000}


def test_ebic_glasso_returns_valid_partial_matrix() -> None:
    rng = np.random.default_rng(0)
    cov = np.eye(5)
    cov[0, 1] = cov[1, 0] = 0.7
    X = rng.multivariate_normal(np.zeros(5), cov, size=400)

    partial, edges = ebic_glasso(X)

    np.testing.assert_allclose(partial, partial.T, atol=1e-12)
    np.testing.assert_allclose(np.diag(partial), 1.0)
    assert partial[0, 1] > 0.3 and edges >= 1


def test_ebic_glasso_can_return_an_empty_network_at_small_n() -> None:
    rng = np.random.default_rng(1)
    partial, edges = ebic_glasso(rng.standard_normal((30, 6)))

    assert edges == 0
    assert np.count_nonzero(partial - np.eye(6)) == 0


def test_tied_scores_receive_expected_top_k_credit() -> None:
    truth = np.eye(4)
    truth[0, 1] = truth[1, 0] = 0.4
    estimated = np.eye(4)  # all off-diagonals tied at zero

    result = edge_recovery_metrics(estimated, truth)

    assert result["n_true_edges"] == 1.0
    assert abs(result["top_k_precision"] - 1 / 6) < 1e-12  # type: ignore[operator]
    assert result["sign_agreement"] == 0.0
    assert result["edge_auc"] == 0.5


def test_run_is_deterministic_worker_invariant_and_summarized() -> None:
    serial = run(2, **SMALL)
    parallel = run(2, workers=2, **SMALL)
    key = ("sdna_edge_auc", "ebic_edge_auc", "ebic_selected_edges")

    assert [[r.get(k) for k in key] for r in serial] == [[r.get(k) for k in key] for r in parallel]
    assert {r["part"] for r in serial} == {"A", "B"}
    summary = summarize(serial)
    assert all("paired_diff_edge_auc_se" in cell for cell in summary)
    assert all(cell["rows"] == 2 for cell in summary)
