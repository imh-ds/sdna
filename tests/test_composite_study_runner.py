from simulations.composite_dgp import CONDITIONS
from tools.run_composite_study import run, summarize

SMALL = {"calibration_simulations": 2, "bootstrap_samples": 5, "truth_draws": 20_000}


def test_run_covers_every_cell_and_keeps_all_rows() -> None:
    rows = run(1, n_values=(40,), **SMALL)

    assert len(rows) == len(CONDITIONS) * 2
    assert {r["condition"] for r in rows} == set(CONDITIONS)
    assert {r["careless"] for r in rows} == {0, 3}
    assert all(r["wf_workflow_status"] in {"ok", "partial", "error"} for r in rows)


def test_run_is_deterministic() -> None:
    first = run(1, n_values=(40,), **SMALL)
    second = run(1, n_values=(40,), **SMALL)
    key = ("shrunk_edge_auc", "wf_observed_rho", "wf_reference_tail_probability")

    assert [[r[k] for k in key] for r in first] == [[r[k] for k in key] for r in second]


def test_summary_reports_denominators_and_chance_level() -> None:
    summary = summarize(run(2, n_values=(40,), **SMALL))
    cell = next(c for c in summary["cells"] if c["condition"] == "symmetric")

    assert cell["clean_rows"] == 2 and cell["careless_rows"] == 2
    assert cell["chance_top3_recall"] == 3 / 40
    assert "careless_top3_recall_n" in cell
    assert len(summary["matched_contrasts"]) == len(CONDITIONS) - 1
