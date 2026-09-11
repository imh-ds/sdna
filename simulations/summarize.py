"""Create machine-readable and human-readable simulation summaries."""

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def summarize_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Summarize row-oriented results by scenario."""
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["scenario"]].append(row)
    scenarios: dict[str, Any] = {}
    for scenario, records in grouped.items():
        flags = [
            float(row["reference_tail_probability"])
            for row in records
            if scenario == "clean_planted_edge" and row.get("reference_tail_probability")
        ]
        scenarios[scenario] = {
            "rows": len(records),
            "mean_observed_rho": sum(float(row["observed_rho"]) for row in records) / len(records),
            "clean_false_flag_rate_at_0.05": (
                sum(value <= 0.05 for value in flags) / len(flags) if flags else None
            ),
        }
    return {"rows": len(rows), "scenarios": scenarios}


def _markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Simulation Summary",
        "",
        "| Scenario | Rows | Mean observed rho | Clean false-flag rate (0.05) |",
        "|---|---:|---:|---:|",
    ]
    for scenario, values in summary["scenarios"].items():
        rate = values["clean_false_flag_rate_at_0.05"]
        rate_text = "n/a" if rate is None else f"{rate:.3f}"
        lines.append(
            f"| {scenario} | {values['rows']} | {values['mean_observed_rho']:.4f} | {rate_text} |"
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
