import numpy as np

from tools.run_edge_recovery import METRICS, ring_truth, run, summarize


def test_ring_truth_alternates_signs_and_is_valid() -> None:
    covariance, truth = ring_truth(6)

    assert np.min(np.linalg.eigvalsh(covariance)) > 0.0
    assert truth[0, 1] > 0.0 > truth[1, 2]
    assert truth[0, 3] == 0.0
    np.testing.assert_allclose(np.diag(truth), 1.0)


def test_run_is_deterministic_and_summary_reports_counts() -> None:
    first, second = run(2), run(2)

    assert first == second
    summary = summarize(first)
    assert len(summary) == 9
    assert all(f"shrunk_{m}_n" in summary[0] for m in METRICS)
