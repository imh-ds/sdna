"""Validate Task 25 and freeze the exact Task 26 selected populations."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.audit_certification_usability import identify_newly_reached_pairs
from tools.cap_expansion_manifest import PAIRING_FIELDS
from tools.certification_budget_sensitivity_manifest import (
    certification_budget_sensitivity_manifest_checksum,
    load_certification_budget_sensitivity_manifest,
)
from tools.certification_usability_manifest import (
    certification_usability_manifest_checksum,
    load_certification_usability_manifest,
)
from tools.summarize_certification_usability import validate_certification_usability

__all__ = [
    "build_selection_manifest",
    "load_selection_manifest",
    "prepare_certification_budget_sensitivity",
]

_PRODUCTION_POPULATION_ROWS = {"cap3": 44, "cap4": 68}
_SELECTION_FIELDS = {
    "schema_version",
    "study",
    "study_manifest_checksum",
    "source_task25",
    "source_task24",
    "candidate_caps",
    "expected_population_rows",
    "populations",
    "overlap_rows",
    "unique_pair_keys",
    "selection_checksum",
}


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _canonical_checksum(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _selection_checksum(selection: Mapping[str, Any]) -> str:
    unsigned = {key: value for key, value in selection.items() if key != "selection_checksum"}
    return _canonical_checksum(unsigned)


def _task25_identity(study_manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "run_id": study_manifest["source_task25_run_id"],
        "commit": study_manifest["source_task25_commit"],
        "artifact": study_manifest["source_task25_artifact"],
        "results_sha256": study_manifest["source_task25_results_sha256"],
        "manifest_checksum": study_manifest["source_task25_manifest_checksum"],
    }


def _task24_identity(study_manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "run_id": study_manifest["source_task24_run_id"],
        "commit": study_manifest["source_task24_commit"],
        "artifact": study_manifest["source_task24_artifact"],
        "results_sha256": study_manifest["source_task24_results_sha256"],
        "manifest_checksum": study_manifest["source_task24_manifest_checksum"],
    }


def _json_pair(pair: Mapping[str, Any]) -> dict[str, Any]:
    key = pair["pair_key"]
    return {
        "pair_key": {field: value for field, value in zip(PAIRING_FIELDS, key, strict=True)},
        "baseline": dict(pair["baseline"]),
        "candidate": dict(pair["candidate"]),
    }


def _normalized_pair_key(row: Mapping[str, Any]) -> tuple[str, int, int, int, int]:
    try:
        return (
            str(row["scenario"]),
            int(row["N"]),
            int(row["p"]),
            int(row["parameter_id"]),
            int(row["replication"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("selection row has invalid pairing fields") from error


def _pair_key_from_json(value: object) -> tuple[str, int, int, int, int]:
    if not isinstance(value, dict) or set(value) != set(PAIRING_FIELDS):
        raise ValueError("pair_key fields do not match the selection contract")
    return _normalized_pair_key(value)


def _key_order(key: tuple[str, int, int, int, int]) -> tuple[Any, ...]:
    scenario, n, p, parameter_id, replication = key
    return n, p, scenario, parameter_id, replication


def _expected_counts(study_manifest: Mapping[str, Any]) -> dict[str, int]:
    value = study_manifest.get("expected_population_rows")
    if not isinstance(value, dict) or set(value) != {"cap3", "cap4"}:
        raise ValueError("expected_population_rows must declare cap3 and cap4")
    counts: dict[str, int] = {}
    for cap in ("cap3", "cap4"):
        count = value[cap]
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("expected population counts must be nonnegative integers")
        counts[cap] = count
    return counts


def build_selection_manifest(
    task25_rows: Sequence[Mapping[str, Any]],
    study_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Return exact, cap-specific Task 25 selections without collapsing overlap."""
    expected_counts = _expected_counts(study_manifest)
    pairs = identify_newly_reached_pairs(task25_rows)
    observed_counts = {cap: len(pairs[cap]) for cap in ("cap3", "cap4")}
    if observed_counts != expected_counts:
        raise ValueError(
            f"selected population count mismatch: expected {expected_counts}, "
            f"observed {observed_counts}"
        )

    populations = {cap: [_json_pair(pair) for pair in pairs[cap]] for cap in ("cap3", "cap4")}
    cap_keys = {cap: {tuple(pair["pair_key"]) for pair in pairs[cap]} for cap in ("cap3", "cap4")}
    selection: dict[str, Any] = {
        "schema_version": study_manifest["output_schema_version"],
        "study": study_manifest["study"],
        "study_manifest_checksum": (
            certification_budget_sensitivity_manifest_checksum(study_manifest)
        ),
        "source_task25": _task25_identity(study_manifest),
        "source_task24": _task24_identity(study_manifest),
        "candidate_caps": list(study_manifest["candidate_caps"]),
        "expected_population_rows": dict(expected_counts),
        "populations": populations,
        "overlap_rows": len(cap_keys["cap3"] & cap_keys["cap4"]),
        "unique_pair_keys": len(cap_keys["cap3"] | cap_keys["cap4"]),
    }
    selection["selection_checksum"] = _selection_checksum(selection)
    return selection


def _require_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    return value


def _validate_entry(
    raw_entry: object,
    cap: str,
) -> tuple[str, int, int, int, int]:
    entry = _require_mapping(raw_entry, f"{cap} selection entry")
    if "baseline" not in entry:
        raise ValueError(f"{cap} selection entry is missing its baseline row")
    if "candidate" not in entry:
        raise ValueError(f"{cap} selection entry is missing its candidate row")
    if set(entry) != {"pair_key", "baseline", "candidate"}:
        raise ValueError(f"{cap} selection entry fields do not match the contract")

    pair_key = _pair_key_from_json(entry["pair_key"])
    baseline = _require_mapping(entry["baseline"], "baseline row")
    candidate = _require_mapping(entry["candidate"], "candidate row")
    if baseline.get("arm") != "baseline_cap2":
        raise ValueError("selection baseline row must use arm 'baseline_cap2'")
    if candidate.get("arm") != cap:
        raise ValueError(f"selection candidate row must use arm {cap!r}")
    if baseline.get("fragility_status") != "unreached":
        raise ValueError("selection baseline row must be unreached")
    if candidate.get("fragility_status") != "reached":
        raise ValueError("selection candidate row must be reached")
    if _normalized_pair_key(baseline) != pair_key:
        raise ValueError("baseline row does not match pair_key")
    if _normalized_pair_key(candidate) != pair_key:
        raise ValueError("candidate row does not match pair_key")
    return pair_key


def load_selection_manifest(
    path: str | Path,
    study_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Load and fully validate a self-checksummed Task 26 selection manifest."""
    selection = _require_mapping(
        json.loads(Path(path).read_text(encoding="utf-8")), "selection manifest"
    )
    if set(selection) != _SELECTION_FIELDS:
        raise ValueError("selection manifest fields do not match the contract")
    if selection["selection_checksum"] != _selection_checksum(selection):
        raise ValueError("selection checksum does not match its contents")
    if selection["schema_version"] != study_manifest["output_schema_version"]:
        raise ValueError("selection schema version does not match the study manifest")
    if selection["study"] != study_manifest["study"]:
        raise ValueError("selection study does not match the study manifest")
    expected_manifest_checksum = certification_budget_sensitivity_manifest_checksum(study_manifest)
    if selection["study_manifest_checksum"] != expected_manifest_checksum:
        raise ValueError("selection study manifest checksum does not match")
    if selection["source_task25"] != _task25_identity(study_manifest):
        raise ValueError("selection Task 25 source identity does not match")
    if selection["source_task24"] != _task24_identity(study_manifest):
        raise ValueError("selection Task 24 source identity does not match")
    if selection["candidate_caps"] != list(study_manifest["candidate_caps"]):
        raise ValueError("selection candidate caps do not match")

    expected_counts = _expected_counts(study_manifest)
    if selection["expected_population_rows"] != expected_counts:
        raise ValueError("selection expected population counts do not match")
    populations = _require_mapping(selection["populations"], "selection populations")
    if set(populations) != {"cap3", "cap4"}:
        raise ValueError("selection populations must contain cap3 and cap4")

    cap_keys: dict[str, set[tuple[str, int, int, int, int]]] = {}
    for cap in ("cap3", "cap4"):
        entries = populations[cap]
        if not isinstance(entries, list):
            raise TypeError(f"{cap} selection population must be a list")
        if len(entries) != expected_counts[cap]:
            raise ValueError(f"{cap} population count does not match")
        keys = [_validate_entry(entry, cap) for entry in entries]
        if len(set(keys)) != len(keys):
            raise ValueError(f"duplicate candidate key in {cap} population")
        if keys != sorted(keys, key=_key_order):
            raise ValueError(f"{cap} population is not in canonical order")
        cap_keys[cap] = set(keys)

    overlap_rows = len(cap_keys["cap3"] & cap_keys["cap4"])
    unique_pair_keys = len(cap_keys["cap3"] | cap_keys["cap4"])
    if selection["overlap_rows"] != overlap_rows:
        raise ValueError("selection overlap count does not match populations")
    if selection["unique_pair_keys"] != unique_pair_keys:
        raise ValueError("selection unique pair-key count does not match populations")
    return selection


def _validate_task25_manifest_identity(
    task25_manifest_path: str | Path,
    study_manifest: Mapping[str, Any],
) -> None:
    task25_manifest = load_certification_usability_manifest(task25_manifest_path)
    if (
        certification_usability_manifest_checksum(task25_manifest)
        != study_manifest["source_task25_manifest_checksum"]
    ):
        raise ValueError("Task 25 manifest checksum does not match the study manifest")
    nested_identity = {
        "source_run_id": study_manifest["source_task24_run_id"],
        "source_commit": study_manifest["source_task24_commit"],
        "source_artifact": study_manifest["source_task24_artifact"],
        "source_results_sha256": study_manifest["source_task24_results_sha256"],
        "source_manifest_checksum": study_manifest["source_task24_manifest_checksum"],
    }
    for field, expected in nested_identity.items():
        if task25_manifest[field] != expected:
            raise ValueError(f"Task 25 manifest {field} does not match Task 24 identity")


def prepare_certification_budget_sensitivity(
    task25_results_csv: str | Path,
    task25_metadata_json: str | Path,
    task25_summary_json: str | Path,
    source_results_csv: str | Path,
    source_metadata_json: str | Path,
    source_summary_json: str | Path,
    source_manifest_path: str | Path,
    task25_manifest_path: str | Path,
    study_manifest_path: str | Path,
    output_path: str | Path,
) -> None:
    """Validate the accepted Task 25 artifact before freezing its populations."""
    study_manifest = load_certification_budget_sensitivity_manifest(study_manifest_path)
    if _expected_counts(study_manifest) != _PRODUCTION_POPULATION_ROWS:
        raise ValueError("production preparation requires exactly 44 cap-3 and 68 cap-4 rows")
    _validate_task25_manifest_identity(task25_manifest_path, study_manifest)

    validate_certification_usability(
        task25_results_csv,
        task25_metadata_json,
        task25_summary_json,
        source_results_csv,
        source_metadata_json,
        source_summary_json,
        source_manifest_path,
        task25_manifest_path,
    )
    if _sha256_file(task25_results_csv) != study_manifest["source_task25_results_sha256"]:
        raise ValueError("Task 25 results checksum does not match the study manifest")

    selection = build_selection_manifest(_read_rows(task25_results_csv), study_manifest)
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(selection, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task25_results_csv", type=Path)
    parser.add_argument("task25_metadata_json", type=Path)
    parser.add_argument("task25_summary_json", type=Path)
    parser.add_argument("source_results_csv", type=Path)
    parser.add_argument("source_metadata_json", type=Path)
    parser.add_argument("source_summary_json", type=Path)
    parser.add_argument("source_manifest_path", type=Path)
    parser.add_argument("task25_manifest_path", type=Path)
    parser.add_argument("study_manifest_path", type=Path)
    parser.add_argument("output_path", type=Path)
    args = parser.parse_args()
    prepare_certification_budget_sensitivity(**vars(args))


if __name__ == "__main__":
    main()
