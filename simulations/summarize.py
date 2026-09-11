"""Create machine-readable and human-readable simulation summaries."""

import csv
import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from simulations.metrics import incremental_auc, partial_rank_association, spearman_correlation

Row = Mapping[str, Any]


def _optional_float(row: Row, field: str) -> float | None:
    """Parse a finite numeric field, preserving missing and censored values."""
    value = row.get(field)
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in {"", "none", "nan", "na", "n/a"}:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _optional_bool(row: Row, field: str) -> bool | None:
    """Parse the Boolean spellings emitted by CSV and JSON writers."""
    value = row.get(field)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1"}:
            return True
        if normalized in {"false", "0"}:
            return False
    parsed = _optional_float(row, field)
    if parsed in {0.0, 1.0}:
        return bool(parsed)
    return None


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _safe_spearman(first: Sequence[float], second: Sequence[float]) -> float | None:
    if len(first) < 2 or len(first) != len(second):
        return None
    try:
        result = spearman_correlation(first, second)
    except (ValueError, FloatingPointError):
        return None
    return result if math.isfinite(result) else None


def _safe_partial_rank(
    first: Sequence[float], second: Sequence[float], controls: Sequence[Sequence[float]]
) -> float | None:
    if len(first) < 2 or len(first) != len(second) or any(
        len(control) != len(first) for control in controls
    ):
        return None
    try:
        result = partial_rank_association(first, second, controls)
    except (ValueError, FloatingPointError, np.linalg.LinAlgError):
        return None
    return result if math.isfinite(result) else None


def _paired_fragility_records(
    rows: Sequence[Row],
) -> list[tuple[float, float, float, float, float, float]]:
    """Return reached rows with finite exact fragility and comparison fields."""
    records: list[tuple[float, float, float, float, float, float]] = []
    for row in rows:
        if _optional_bool(row, "reached") is not True:
            continue
        exact = _optional_float(row, "exact_fragility_50")
        observed = _optional_float(row, "observed_rho")
        wald = _optional_float(row, "wald_z")
        n = _optional_float(row, "N")
        p = _optional_float(row, "p")
        contamination = _optional_float(row, "contamination_status")
        if None in {exact, observed, wald, n, p, contamination}:
            continue
        assert exact is not None
        assert observed is not None
        assert wald is not None
        assert n is not None
        assert p is not None
        assert contamination is not None
        records.append((exact, observed, wald, n, p, contamination))
    return records


def _falsification_summary(rows: Sequence[Row]) -> dict[str, Any]:
    """Summarize one scenario while excluding censored and undefined metrics."""
    paired = _paired_fragility_records(rows)
    exact_values = [record[0] for record in paired]
    observed_values = [abs(record[1]) for record in paired]
    wald_values = [abs(record[2]) for record in paired]
    contamination_values = [int(record[5]) for record in paired]
    n_values = [record[3] for record in paired]
    p_values = [record[4] for record in paired]

    auc_result: dict[str, float] | None = None
    if len(set(contamination_values)) == 2:
        try:
            auc_result = incremental_auc(contamination_values, observed_values, exact_values)
        except (ValueError, FloatingPointError):
            auc_result = None

    greedy_values = [
        value
        for row in rows
        if _optional_bool(row, "reached") is True
        for value in [_optional_float(row, "greedy_fragility_50")]
        if value is not None
    ]
    exact_and_greedy = [
        (exact, greedy)
        for row in rows
        if _optional_bool(row, "reached") is True
        for exact in [_optional_float(row, "exact_fragility_50")]
        for greedy in [_optional_float(row, "greedy_fragility_50")]
        if exact is not None and greedy is not None
    ]
    certification_values = [
        value for row in rows if (value := _optional_bool(row, "certified")) is not None
    ]
    reached_values = [
        value for row in rows if (value := _optional_bool(row, "reached")) is not None
    ]
    reference_reach_values = [
        value
        for row in rows
        if (value := _optional_float(row, "reference_reached_fraction")) is not None
    ]

    influence_fields = {
        "mean_influence_top_k_precision": "influence_top_k_precision",
        "mean_influence_top_k_recall": "influence_top_k_recall",
        "mean_first_planted_reciprocal_rank": "first_planted_reciprocal_rank",
        "mean_planted_absolute_influence_share": "planted_absolute_influence_share",
    }
    result: dict[str, Any] = {
        "rows": len(rows),
        "fragility_vs_abs_observed_rho_spearman": _safe_spearman(
            exact_values, observed_values
        ),
        "fragility_vs_abs_wald_z_spearman": _safe_spearman(exact_values, wald_values),
        "fragility_contamination_partial_rank": (
            _safe_partial_rank(
                exact_values,
                contamination_values,
                [observed_values, n_values, p_values],
            )
            if len(set(contamination_values)) == 2
            else None
        ),
        "incremental_auc": auc_result,
        "mean_exact_fragility": _mean(exact_values),
        "mean_greedy_fragility": _mean(greedy_values),
        "greedy_overestimation_rate": (
            sum(greedy > exact for exact, greedy in exact_and_greedy) / len(exact_and_greedy)
            if exact_and_greedy
            else None
        ),
        "certification_rate": (
            sum(certification_values) / len(certification_values) if certification_values else None
        ),
        "fragility_reach_rate": (
            sum(reached_values) / len(reached_values) if reached_values else None
        ),
        "reference_reach_rate": _mean(reference_reach_values),
    }
    for output_field, input_field in influence_fields.items():
        values = [
            value
            for row in rows
            if (value := _optional_float(row, input_field)) is not None
        ]
        result[output_field] = _mean(values)
    return result


def summarize_scenario_rows(rows: Sequence[Row]) -> dict[str, Any]:
    """Return falsification metrics for one scenario's row records."""
    return _falsification_summary(rows)


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize row-oriented results by scenario."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["scenario"])].append(row)
    scenarios: dict[str, Any] = {}
    falsification: dict[str, Any] = {}
    for scenario, records in grouped.items():
        observed = [
            value for row in records if (value := _optional_float(row, "observed_rho")) is not None
        ]
        flags = [
            value
            for row in records
            if scenario == "clean_planted_edge"
            if (value := _optional_float(row, "reference_tail_probability")) is not None
        ]
        scenarios[scenario] = {
            "rows": len(records),
            "mean_observed_rho": _mean(observed),
            "clean_false_flag_rate_at_0.05": (
                sum(value <= 0.05 for value in flags) / len(flags) if flags else None
            ),
        }
        falsification[scenario] = summarize_scenario_rows(records)
    return {"rows": len(rows), "scenarios": scenarios, "falsification": falsification}


def _format_metric(value: Any, digits: int = 3) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Simulation Summary",
        "",
        "| Scenario | Rows | Mean observed rho | Clean false-flag rate (0.05) | Fragility/rho Spearman | Augmented AUC | Influence recall | Certification rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for scenario, values in summary["scenarios"].items():
        rate = values["clean_false_flag_rate_at_0.05"]
        falsification = summary.get("falsification", {}).get(scenario, {})
        mean_rho = values["mean_observed_rho"]
        auc_values = falsification.get("incremental_auc") or {}
        lines.append(
            "| "
            f"{scenario} | {values['rows']} | {_format_metric(mean_rho, 4)} | "
            f"{_format_metric(rate)} | "
            f"{_format_metric(falsification.get('fragility_vs_abs_observed_rho_spearman'))} | "
            f"{_format_metric(auc_values.get('augmented_auc'))} | "
            f"{_format_metric(falsification.get('mean_influence_top_k_recall'))} | "
            f"{_format_metric(falsification.get('certification_rate'))} |"
        )
    return "\n".join(lines) + "\n"


def summarize_results(
    input_csv: str | Path, json_output: str | Path, markdown_output: str | Path
) -> None:
    """Read simulation CSV and write JSON plus Markdown summaries."""
    with Path(input_csv).open(newline="", encoding="utf-8") as handle:
        summary = summarize_rows(list(csv.DictReader(handle)))
    Path(json_output).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    Path(markdown_output).write_text(_markdown(summary), encoding="utf-8")
