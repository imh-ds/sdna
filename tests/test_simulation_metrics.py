import numpy as np

from simulations.metrics import (
    auc,
    influence_metrics,
    incremental_auc,
    partial_rank_association,
    spearman_correlation,
)
from simulations.summarize import summarize_results, summarize_rows


def test_auc_on_hand_computable_scores() -> None:
    assert auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0


def test_spearman_on_monotone_values() -> None:
    assert spearman_correlation([1, 2, 3], [10, 20, 30]) == 1.0


def test_influence_metrics_recover_planted_cases() -> None:
    result = influence_metrics([0.1, 0.9, 0.2, 0.8], planted_cases=[1, 3], k=2)

    assert result["top_k_precision"] == 1.0
    assert result["top_k_recall"] == 1.0
    assert result["first_planted_reciprocal_rank"] == 1.0
    assert result["planted_absolute_influence_share"] == 1.0


def test_partial_rank_association_controls_a_confounder() -> None:
    x = np.array([1.0, 2.0, 3.0, 4.0])
    y = np.array([1.0, 2.0, 3.0, 4.0])
    control = np.array([1.0, 2.0, 3.0, 4.0])

    assert partial_rank_association(x, y, [control]) == 0.0


def test_incremental_auc_reports_baseline_and_augmented_scores() -> None:
    result = incremental_auc([0, 0, 1, 1], [0.1, 0.2, 0.3, 0.4], [0.0, 0.0, 1.0, 1.0])

    assert result["baseline_auc"] == 1.0
    assert result["augmented_auc"] == 1.0


def test_incremental_auc_fits_predictor_weights() -> None:
    result = incremental_auc(
        [0, 0, 1, 1],
        baseline=[0.0, 10.0, 0.0, 10.0],
        fragility=[0.0, 0.0, 1.0, 1.0],
    )

    assert result["baseline_auc"] == 0.5
    assert result["augmented_auc"] == 1.0


def test_summary_reports_json_and_markdown(tmp_path) -> None:
    rows = [
        {
            "scenario": "clean_planted_edge",
            "observed_rho": "0.2",
            "reference_tail_probability": "0.04",
        },
        {
            "scenario": "coalition_contamination",
            "observed_rho": "0.4",
            "reference_tail_probability": "0.01",
        },
    ]
    assert summarize_rows(rows)["rows"] == 2
    input_csv = tmp_path / "results.csv"
    input_csv.write_text(
        "scenario,observed_rho,reference_tail_probability\n"
        "clean_planted_edge,0.2,0.04\n"
        "coalition_contamination,0.4,0.01\n",
        encoding="utf-8",
    )
    json_output = tmp_path / "summary.json"
    markdown_output = tmp_path / "summary.md"
    summarize_results(input_csv, json_output, markdown_output)

    assert json_output.exists()
    assert "Simulation Summary" in markdown_output.read_text(encoding="utf-8")
