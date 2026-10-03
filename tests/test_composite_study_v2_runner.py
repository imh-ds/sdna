from simulations.composite_dgp_v2 import CONDITIONS, CONTAMINATIONS
from tools.run_composite_study_v2 import run, summarize

SMALL = {
    "calibration_simulations": 2,
    "bootstrap_samples": 5,
    "truth_draws": 20_000,
    "n_values": (40,),
}


def test_run_covers_every_cell_and_keeps_all_rows() -> None:
    rows = run(1, **SMALL)

    expected = 2 * 2 * len(CONDITIONS) * len(CONTAMINATIONS)
    assert len(rows) == expected
    assert {r["contamination"] for r in rows} == set(CONTAMINATIONS)
    assert all(r["wf_workflow_status"] in {"ok", "partial", "error"} for r in rows)
    assert all(r["edge_rule_classifiable"] for r in rows)


def test_run_is_deterministic_and_worker_count_invariant() -> None:
    serial = run(1, **SMALL)
    parallel = run(1, workers=2, **SMALL)
    key = ("shrunk_edge_auc", "wf_observed_rho", "wf_reference_tail_probability")

    assert [[r.get(k) for k in key] for r in serial] == [[r.get(k) for k in key] for r in parallel]


def test_summary_keeps_denominators_and_chance_level() -> None:
    summary = summarize(run(2, **SMALL))
    cell = next(c for c in summary if c["contamination"] == "focal_discordant")

    assert cell["rows"] == 2
    assert cell["chance_top3_recall"] == 3 / 40
    assert "top3_recall_n" in cell and "tail_finite" in cell
    clean = next(c for c in summary if c["contamination"] == "none")
    assert clean["top3_recall"] is None and clean["top3_recall_n"] == 0
