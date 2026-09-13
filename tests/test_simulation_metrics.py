import numpy as np

from simulations.metrics import (
    auc,
    incremental_auc,
    influence_metrics,
    partial_rank_association,
    spearman_correlation,
)
from simulations.summarize import summarize_results, summarize_rows


def hand_computable_falsification_rows() -> list[dict[str, str]]:
    """Return a small fixture with both contamination classes and valid metrics."""
    common = {
        "scenario": "coalition_contamination",
        "replication": "0",
        "seed": "123",
        "lambda": "0.1",
        "fragility_target": "0.5",
        "true_rho": "0.0",
        "contamination_count": "0",
        "reference_tail_probability": "0.01",
        "reference_reached_fraction": "1.0",
        "bootstrap_rejected_resamples": "0",
        "influence_top_k_precision": "0.5",
        "influence_top_k_recall": "0.5",
        "first_planted_reciprocal_rank": "0.5",
        "planted_absolute_influence_share": "0.3",
        "bootstrap_ci_excludes_zero": "1",
    }
    rows: list[dict[str, str]] = []
    for index, values in enumerate(
        [
            (0, 50, 5, 0.1, 0.2, 0.1, 0.1, 0),
            (0, 60, 5, 0.2, 0.4, 0.2, 0.2, 0),
            (1, 70, 10, 0.8, 2.0, 0.7, 0.6, 1),
            (1, 80, 10, 0.9, 2.5, 0.9, 0.8, 1),
        ]
    ):
        contamination, n, p, observed, wald, greedy, exact, certified = values
        row = common | {
            "replication": str(index),
            "N": str(n),
            "p": str(p),
            "observed_rho": str(observed),
            "wald_z": str(wald),
            "contamination_count": str(3 if contamination else 0),
            "contamination_status": str(contamination),
            "greedy_fragility_50": str(greedy),
            "exact_fragility_50": str(exact),
            "certified": str(certified),
            "reached": "True",
        }
        rows.append(row)
    return rows


def censored_clean_rows() -> list[dict[str, str | None]]:
    """Return clean rows whose fragility and reference results are censored."""
    return [
        {
            "scenario": "clean_planted_edge",
            "N": "50",
            "p": "5",
            "observed_rho": "0.1",
            "wald_z": "0.2",
            "contamination_count": "0",
            "contamination_status": "0",
            "greedy_fragility_50": None,
            "exact_fragility_50": None,
            "certified": "0",
            "reached": "False",
            "reference_tail_probability": None,
            "reference_reached_fraction": "0.0",
        }
    ]


def hand_computable_paired_contrast_rows() -> list[dict[str, str | None]]:
    """Return matched clean/contaminated rows with one censored pair."""
    rows: list[dict[str, str | None]] = []
    values = [
        (50, 5, 0.1, 0.2, 0.1, 0.8),
        (60, 6, 0.2, 0.4, 0.2, 0.7),
        (70, 7, 0.3, 0.6, 0.3, 0.9),
        (80, 8, 0.4, 0.8, 0.4, 1.0),
    ]
    for replication, (
        n,
        p,
        clean_rho,
        contaminated_rho,
        clean_exact,
        contaminated_exact,
    ) in enumerate(values):
        common = {
            "replication": str(replication),
            "N": str(n),
            "p": str(p),
            "wald_z": str(clean_rho * 2.0),
            "greedy_fragility_50": str(clean_exact),
            "certified": "True",
            "reached": "True",
        }
        rows.append(
            common
            | {
                "scenario": "clean_planted_edge",
                "observed_rho": str(clean_rho),
                "contamination_status": "0",
                "exact_fragility_50": str(clean_exact),
            }
        )
        contaminated = common | {
            "scenario": "coalition_contamination",
            "observed_rho": str(contaminated_rho),
            "wald_z": str(contaminated_rho * 2.0),
            "contamination_status": "1",
            "exact_fragility_50": str(contaminated_exact),
            "greedy_fragility_50": str(contaminated_exact),
        }
        if replication == 3:
            contaminated["reached"] = "False"
            contaminated["certified"] = "False"
            contaminated["exact_fragility_50"] = None
            contaminated["greedy_fragility_50"] = None
        rows.append(contaminated)
    return rows


def test_auc_on_hand_computable_scores() -> None:
    assert auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0


def test_spearman_on_monotone_values() -> None:
    assert spearman_correlation([1, 2, 3], [10, 20, 30]) == 1.0


def test_influence_metrics_recover_planted_cases() -> None:
    result = influence_metrics([0.1, 0.9, 0.2, 0.8], planted_cases=[1, 3], k=2)

    assert result["top_k_precision"] == 1.0
    assert result["top_k_recall"] == 1.0
    assert result["first_planted_reciprocal_rank"] == 1.0
    assert np.isclose(result["planted_absolute_influence_share"], 0.85)


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


def test_summary_reports_incremental_auc_and_rank_associations() -> None:
    summary = summarize_rows(hand_computable_falsification_rows())
    result = summary["falsification"]["coalition_contamination"]

    assert result["incremental_auc"]["augmented_auc"] >= result["incremental_auc"]["baseline_auc"]
    assert result["fragility_vs_abs_observed_rho_spearman"] is not None
    assert result["fragility_contamination_partial_rank"] is not None


def test_summary_preserves_null_for_single_class_or_censored_metrics() -> None:
    result = summarize_rows(censored_clean_rows())["falsification"]["clean_planted_edge"]

    assert result["incremental_auc"] is None
    assert result["mean_exact_fragility"] is None


def test_summary_reports_paired_cross_scenario_contrast() -> None:
    summary = summarize_rows(hand_computable_paired_contrast_rows())
    result = summary["paired_contrasts"]["clean_vs_coalition_contamination"]

    assert result["matched_pairs"] == 4
    assert result["censored_pairs"] == 1
    assert result["individually_valid_fragility_rows"] == 7
    assert result["jointly_valid_pair_count"] == 3
    assert result["jointly_valid_fragility_rows"] == 6
    expected_joint_auc = incremental_auc(
        [0, 1, 0, 1, 0, 1],
        [0.1, 0.2, 0.2, 0.4, 0.3, 0.6],
        [0.1, 0.8, 0.2, 0.7, 0.3, 0.9],
    )
    assert result["jointly_valid_pair_metrics"]["incremental_auc"] == expected_joint_auc
    pooled_metrics = result["individually_valid_row_metrics"]
    assert pooled_metrics["incremental_auc"]["augmented_auc"] >= pooled_metrics["incremental_auc"]["baseline_auc"]
    assert pooled_metrics["fragility_contamination_partial_rank"] is not None


def test_contrast_metrics_use_exact_row_populations() -> None:
    summary = summarize_rows(hand_computable_paired_contrast_rows())
    result = summary["paired_contrasts"]["clean_vs_coalition_contamination"]

    assert result["individually_valid_clean_fragility_rows"] == 4
    assert result["individually_valid_contaminated_fragility_rows"] == 3
    assert result["jointly_valid_pair_count"] == 3

    expected_pooled_auc = incremental_auc(
        [0, 1, 0, 1, 0, 1, 0],
        [0.1, 0.2, 0.2, 0.4, 0.3, 0.6, 0.4],
        [0.1, 0.8, 0.2, 0.7, 0.3, 0.9, 0.4],
    )
    expected_joint_auc = incremental_auc(
        [0, 1, 0, 1, 0, 1],
        [0.1, 0.2, 0.2, 0.4, 0.3, 0.6],
        [0.1, 0.8, 0.2, 0.7, 0.3, 0.9],
    )
    assert result["individually_valid_row_metrics"]["incremental_auc"] == expected_pooled_auc
    assert result["jointly_valid_pair_metrics"]["incremental_auc"] == expected_joint_auc


def test_summary_omits_unmatched_cross_scenario_contrasts() -> None:
    rows = hand_computable_paired_contrast_rows()
    rows = [
        row
        for row in rows
        if row["scenario"] != "clean_planted_edge" or row["replication"] != "3"
    ]

    result = summarize_rows(rows)["paired_contrasts"]["clean_vs_coalition_contamination"]

    assert result["matched_pairs"] == 3
    assert result["unmatched_contaminated_rows"] == 1
