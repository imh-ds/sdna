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
FragilityRecord = tuple[float, float, float, float, float, float]


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
) -> list[FragilityRecord]:
    """Return reached rows with finite exact fragility and comparison fields."""
    records: list[FragilityRecord] = []
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


def _contrast_key(row: Row) -> tuple[int, int, int] | None:
    n, p, replication = [
        _optional_float(row, field) for field in ("N", "p", "replication")
    ]
    if n is None or p is None or replication is None:
        return None
    return int(n), int(p), int(replication)


def _valid_fragility_row(row: Row) -> bool:
    return bool(_paired_fragility_records([row]))


def _contrast_metric_summary(records: Sequence[FragilityRecord]) -> dict[str, Any]:
    """Summarize contrast metrics for one explicitly defined row population."""
    exact_values = [record[0] for record in records]
    observed_values = [abs(record[1]) for record in records]
    wald_values = [abs(record[2]) for record in records]
    n_values = [record[3] for record in records]
    p_values = [record[4] for record in records]
    contamination_values = [int(record[5]) for record in records]

    auc_result: dict[str, float] | None = None
    if len(set(contamination_values)) == 2:
        try:
            auc_result = incremental_auc(contamination_values, observed_values, exact_values)
        except (ValueError, FloatingPointError):
            auc_result = None

    return {
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
    }


def _paired_contrast_summary(
    clean_rows: Sequence[Row],
    contaminated_rows: Sequence[Row],
    clean_scenario: str,
    contaminated_scenario: str,
) -> dict[str, Any]:
    clean_groups: dict[tuple[int, int, int], list[Row]] = defaultdict(list)
    contaminated_groups: dict[tuple[int, int, int], list[Row]] = defaultdict(list)
    for row in clean_rows:
        if (key := _contrast_key(row)) is not None:
            clean_groups[key].append(row)
    for row in contaminated_rows:
        if (key := _contrast_key(row)) is not None:
            contaminated_groups[key].append(row)

    common_keys = set(clean_groups) & set(contaminated_groups)
    matched_keys = {
        key
        for key in common_keys
        if len(clean_groups[key]) == 1 and len(contaminated_groups[key]) == 1
    }
    pairs = [
        (clean_groups[key][0], contaminated_groups[key][0])
        for key in sorted(matched_keys)
    ]
    paired_rows = [row for pair in pairs for row in pair]
    individually_valid_rows = [row for row in paired_rows if _valid_fragility_row(row)]
    individually_valid_records = _paired_fragility_records(individually_valid_rows)
    jointly_valid_pairs = [
        (clean, contaminated)
        for clean, contaminated in pairs
        if _valid_fragility_row(clean) and _valid_fragility_row(contaminated)
    ]
    jointly_valid_rows = [row for pair in jointly_valid_pairs for row in pair]
    jointly_valid_records = _paired_fragility_records(jointly_valid_rows)

    return {
        "clean_scenario": clean_scenario,
        "contaminated_scenario": contaminated_scenario,
        "matched_pairs": len(pairs),
        "unmatched_clean_rows": sum(
            len(records) for key, records in clean_groups.items() if key not in matched_keys
        ),
        "unmatched_contaminated_rows": sum(
            len(records)
            for key, records in contaminated_groups.items()
            if key not in matched_keys
        ),
        "ambiguous_keys": sum(
            1
            for key in common_keys
            if len(clean_groups[key]) != 1 or len(contaminated_groups[key]) != 1
        ),
        "censored_pairs": sum(
            not (_valid_fragility_row(clean) and _valid_fragility_row(contaminated))
            for clean, contaminated in pairs
        ),
        "individually_valid_fragility_rows": len(individually_valid_rows),
        "individually_valid_clean_fragility_rows": sum(
            _valid_fragility_row(clean) for clean, _ in pairs
        ),
        "individually_valid_contaminated_fragility_rows": sum(
            _valid_fragility_row(contaminated) for _, contaminated in pairs
        ),
        "jointly_valid_pair_count": len(jointly_valid_pairs),
        "jointly_valid_fragility_rows": len(jointly_valid_rows),
        "individually_valid_row_metrics": _contrast_metric_summary(individually_valid_records),
        "jointly_valid_pair_metrics": _contrast_metric_summary(jointly_valid_records),
    }


def summarize_paired_contrasts(grouped: Mapping[str, Sequence[Row]]) -> dict[str, Any]:
    """Summarize matched clean/contaminated scenario contrasts."""
    clean_scenario = "clean_planted_edge"
    clean_rows = grouped.get(clean_scenario, [])
    if not clean_rows:
        return {}
    contrasts: dict[str, Any] = {}
    for scenario, records in grouped.items():
        if scenario == clean_scenario:
            continue
        if not any(_optional_float(row, "contamination_status") == 1.0 for row in records):
            continue
        contrast_name = f"clean_vs_{scenario}"
        contrasts[contrast_name] = _paired_contrast_summary(
            clean_rows, records, clean_scenario, scenario
        )
    return contrasts


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
    return {
        "rows": len(rows),
        "scenarios": scenarios,
        "falsification": falsification,
        "paired_contrasts": summarize_paired_contrasts(grouped),
    }


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
    contrasts = summary.get("paired_contrasts", {})
    if contrasts:
        lines.extend(
            [
                "",
                "## Matched-cell Cross-Scenario Contrasts",
                "",
                "| Contrast | Matched cells | Individually valid rows | Jointly valid pairs | Pooled baseline AUC | Pooled augmented AUC | Joint baseline AUC | Joint augmented AUC | Pooled partial rank | Joint partial rank |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for contrast, values in contrasts.items():
            pooled_metrics = values.get("individually_valid_row_metrics") or {}
            pooled_auc = pooled_metrics.get("incremental_auc") or {}
            joint_metrics = values.get("jointly_valid_pair_metrics") or {}
            joint_auc = joint_metrics.get("incremental_auc") or {}
            lines.append(
                f"| {contrast} | {values['matched_pairs']} | "
                f"{values['individually_valid_fragility_rows']} | "
                f"{values['jointly_valid_pair_count']} | "
                f"{_format_metric(pooled_auc.get('baseline_auc'))} | "
                f"{_format_metric(pooled_auc.get('augmented_auc'))} | "
                f"{_format_metric(joint_auc.get('baseline_auc'))} | "
                f"{_format_metric(joint_auc.get('augmented_auc'))} | "
                f"{_format_metric(pooled_metrics.get('fragility_contamination_partial_rank'))} | "
                f"{_format_metric(joint_metrics.get('fragility_contamination_partial_rank'))} |"
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
