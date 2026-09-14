"""Audit newly reached cap-expansion pairs for certification usability."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.cap_expansion_manifest import CAP_ARM_NAMES, PAIRING_FIELDS, load_cap_expansion_manifest
from tools.certification_usability_manifest import load_certification_usability_manifest
from tools.summarize_cap_expansion import validate_cap_expansion

UNAVAILABLE_FIELDS = [
    "certification_combinations_checked",
    "certification_combination_budget",
    "certification_failure_reason",
]

__all__ = [
    "audit_certification_usability",
    "identify_newly_reached_pairs",
]


def _pairing_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    missing = [field for field in PAIRING_FIELDS if field not in row]
    if missing:
        raise ValueError(f"row is missing pairing fields: {missing}")
    try:
        return (
            str(row["scenario"]),
            int(row["N"]),
            int(row["p"]),
            int(row["parameter_id"]),
            int(row["replication"]),
        )
    except (TypeError, ValueError) as error:
        raise ValueError("row has invalid pairing fields") from error


def _key_order(key: tuple[Any, ...]) -> tuple[Any, ...]:
    scenario, n, p, parameter_id, replication = key
    return n, p, scenario, parameter_id, replication


def identify_newly_reached_pairs(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Return exact cap-2-unreached/candidate-reached pair records."""
    grouped: dict[tuple[Any, ...], dict[str, dict[str, Any]]] = defaultdict(dict)
    for raw_row in rows:
        row = dict(raw_row)
        arm = row.get("arm")
        if arm not in CAP_ARM_NAMES:
            raise ValueError(f"unknown cap-expansion arm: {arm!r}")
        key = _pairing_key(row)
        if arm in grouped[key]:
            raise ValueError(f"duplicate {arm} row for pairing key {key}")
        grouped[key][str(arm)] = row

    pairs = {"cap3": [], "cap4": []}
    for key in sorted(grouped, key=_key_order):
        arm_rows = grouped[key]
        if set(arm_rows) != set(CAP_ARM_NAMES):
            raise ValueError(f"pair {key} does not contain all three arms")
        baseline = arm_rows["baseline_cap2"]
        if baseline.get("fragility_status") != "unreached":
            continue
        for candidate_arm in ("cap3", "cap4"):
            candidate = arm_rows[candidate_arm]
            if candidate.get("fragility_status") == "reached":
                pairs[candidate_arm].append(
                    {
                        "pair_key": key,
                        "baseline": dict(baseline),
                        "candidate": dict(candidate),
                    }
                )
    return pairs


def _sha256_file(path: str | Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _read_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _json_pair(pair: Mapping[str, Any]) -> dict[str, Any]:
    key = pair["pair_key"]
    return {
        "pair_key": {
            field: value for field, value in zip(PAIRING_FIELDS, key, strict=True)
        },
        "baseline": pair["baseline"],
        "candidate": pair["candidate"],
    }


def _render_markdown(report: Mapping[str, Any]) -> str:
    source = report["source"]
    lines = [
        "# Certification usability Phase A audit",
        "",
        "This is a read-only audit of the accepted Task 24 artifact. It does not",
        "rerun the simulation or promote a search cap.",
        "",
        "## Source artifact",
        "",
        f"- Actions run: `{source['run_id']}`",
        f"- Source commit: `{source['commit']}`",
        f"- Artifact: `{source['artifact']}`",
        f"- Results SHA-256: `{source['results_sha256']}`",
        f"- Audit commit: `{report['audit_commit']}`",
        "",
        "## Newly reached populations",
        "",
        "`U_to_R(c)` contains matched rows unreached at cap 2 and reached at",
        "candidate cap `c`. Downstream failures remain in the denominator.",
        "",
        "| Candidate cap | U→R rows | Certified rows | Certification yield |",
        "| ---: | ---: | ---: | ---: |",
    ]
    for cap in report["candidate_caps"]:
        values = report["populations"][f"cap{cap}"]
        lines.append(
            f"| {cap} | {values['rows']} | {values['certified_rows']} | "
            f"{values['certification_yield']} |"
        )
    lines.extend(
        [
            "",
            "## Fields unavailable in the Task 24 CSV",
            "",
        ]
    )
    lines.extend(f"- `{field}`" for field in report["unavailable_fields"])
    lines.extend(
        [
            "",
            "The Task 24 `not_certified` status is preserved as recorded. A",
            "dedicated certification reason and combination-budget diagnostic",
            "require the conditional instrumented rerun defined by Task 25.",
            "",
            "## Interpretation",
            "",
            "This audit describes the rows that became reachable; it does not",
            "treat reachability as certification or change the cap-2 baseline.",
            "",
        ]
    )
    return "\n".join(lines)


def audit_certification_usability(
    results_csv: str | Path,
    metadata_json: str | Path,
    summary_json: str | Path,
    source_manifest: str | Path,
    audit_manifest: str | Path,
    output_json: str | Path,
    output_markdown: str | Path,
) -> None:
    """Validate the Task 24 artifact and write a Phase A audit report."""
    manifest = load_cap_expansion_manifest(source_manifest)
    audit_config = load_certification_usability_manifest(audit_manifest)
    validate_cap_expansion(results_csv, metadata_json, summary_json, manifest)
    rows = _read_rows(results_csv)
    pairs = identify_newly_reached_pairs(rows)

    source_results_sha256 = _sha256_file(results_csv)
    if source_results_sha256 != audit_config["source_results_sha256"]:
        raise ValueError("source results checksum does not match audit manifest")

    populations: dict[str, dict[str, Any]] = {}
    for candidate_arm, candidate_pairs in pairs.items():
        certified_rows = sum(
            pair["candidate"].get("certification_status") == "certified"
            for pair in candidate_pairs
        )
        denominator = len(candidate_pairs)
        populations[candidate_arm] = {
            "rows": denominator,
            "certified_rows": certified_rows,
            "certification_yield": (
                certified_rows / denominator if denominator else None
            ),
        }

    report: dict[str, Any] = {
        "study": audit_config["study"],
        "phase": "A",
        "audit_commit": _git_commit(),
        "candidate_caps": audit_config["candidate_caps"],
        "primary_population": audit_config["primary_population"],
        "primary_endpoint": audit_config["primary_endpoint"],
        "unavailable_fields": UNAVAILABLE_FIELDS,
        "source": {
            "run_id": audit_config["source_run_id"],
            "commit": audit_config["source_commit"],
            "artifact": audit_config["source_artifact"],
            "manifest_checksum": audit_config["source_manifest_checksum"],
            "results_sha256": source_results_sha256,
        },
        "populations": populations,
        "pairs": {
            candidate_arm: [_json_pair(pair) for pair in candidate_pairs]
            for candidate_arm, candidate_pairs in pairs.items()
        },
    }
    output_file = Path(output_json)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    Path(output_markdown).write_text(_render_markdown(report), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results_csv", type=Path)
    parser.add_argument("metadata_json", type=Path)
    parser.add_argument("summary_json", type=Path)
    parser.add_argument("source_manifest", type=Path)
    parser.add_argument("audit_manifest", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("output_markdown", type=Path)
    args = parser.parse_args()
    audit_certification_usability(
        args.results_csv,
        args.metadata_json,
        args.summary_json,
        args.source_manifest,
        args.audit_manifest,
        args.output_json,
        args.output_markdown,
    )


if __name__ == "__main__":
    main()
