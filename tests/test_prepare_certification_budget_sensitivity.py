"""Tests for Task 26 exact population selection and preparation."""

import copy
import csv
import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pytest

import tools.prepare_certification_budget_sensitivity as prepare_module
from tools.certification_budget_sensitivity_manifest import (
    certification_budget_sensitivity_manifest_checksum,
    load_certification_budget_sensitivity_manifest,
)
from tools.prepare_certification_budget_sensitivity import (
    build_selection_manifest,
    load_selection_manifest,
    prepare_certification_budget_sensitivity,
)

MANIFEST_PATH = Path("simulations/configs/certification_budget_sensitivity_v1.json")
TASK25_MANIFEST_PATH = Path("simulations/configs/certification_usability_v1.json")
STUDY_MANIFEST = load_certification_budget_sensitivity_manifest(MANIFEST_PATH)


def _row(
    arm: str,
    *,
    n: int,
    p: int,
    scenario: str,
    parameter_id: int,
    replication: int,
    fragility_status: str,
    workflow_status: str = "ok",
) -> dict[str, Any]:
    return {
        "arm": arm,
        "scenario": scenario,
        "N": n,
        "p": p,
        "parameter_id": parameter_id,
        "replication": replication,
        "fragility_status": fragility_status,
        "workflow_status": workflow_status,
        "data_seed": 1000 + replication,
        "calibration_seed": 2000 + replication,
        "bootstrap_seed": 3000 + replication,
        "dataset_digest": f"digest-{n}-{p}-{replication}",
    }


def _pair_rows(
    *,
    n: int,
    p: int,
    scenario: str,
    parameter_id: int,
    replication: int,
    cap3_reached: bool,
    cap4_reached: bool,
) -> list[dict[str, Any]]:
    common = {
        "n": n,
        "p": p,
        "scenario": scenario,
        "parameter_id": parameter_id,
        "replication": replication,
    }
    return [
        _row("baseline_cap2", fragility_status="unreached", **common),
        _row(
            "cap3",
            fragility_status="reached" if cap3_reached else "unreached",
            workflow_status="error" if cap3_reached and n == 150 else "ok",
            **common,
        ),
        _row(
            "cap4",
            fragility_status="reached" if cap4_reached else "unreached",
            **common,
        ),
    ]


def _task25_rows() -> list[dict[str, Any]]:
    rows = [
        *_pair_rows(
            n=150,
            p=20,
            scenario="single_influential_case",
            parameter_id=1,
            replication=2,
            cap3_reached=True,
            cap4_reached=False,
        ),
        *_pair_rows(
            n=100,
            p=10,
            scenario="heavy_tails",
            parameter_id=0,
            replication=1,
            cap3_reached=False,
            cap4_reached=True,
        ),
        *_pair_rows(
            n=50,
            p=5,
            scenario="clean_planted_edge",
            parameter_id=0,
            replication=0,
            cap3_reached=True,
            cap4_reached=True,
        ),
    ]
    return list(reversed(rows))


def _test_manifest() -> dict[str, Any]:
    manifest = copy.deepcopy(STUDY_MANIFEST)
    manifest["expected_population_rows"] = {"cap3": 2, "cap4": 2}
    manifest["expected_rows_per_budget"] = 4
    return manifest


def _pair_key(entry: Mapping[str, Any]) -> tuple[Any, ...]:
    key = entry["pair_key"]
    return (
        key["scenario"],
        key["N"],
        key["p"],
        key["parameter_id"],
        key["replication"],
    )


def _resign(selection: dict[str, Any]) -> None:
    unsigned = {key: value for key, value in selection.items() if key != "selection_checksum"}
    encoded = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
    selection["selection_checksum"] = hashlib.sha256(encoded).hexdigest()


def _write_selection(tmp_path: Path, selection: Mapping[str, Any]) -> Path:
    path = tmp_path / "selection.json"
    path.write_text(json.dumps(selection), encoding="utf-8")
    return path


def test_selection_manifest_preserves_cap_overlap_and_exact_rows() -> None:
    manifest = _test_manifest()

    selection = build_selection_manifest(_task25_rows(), manifest)

    assert len(selection["populations"]["cap3"]) == 2
    assert len(selection["populations"]["cap4"]) == 2
    assert selection["overlap_rows"] == 1
    assert selection["unique_pair_keys"] == 3
    assert selection["populations"]["cap3"][0]["candidate"]["arm"] == "cap3"
    assert selection["populations"]["cap3"][1]["candidate"]["workflow_status"] == ("error")
    assert selection["populations"]["cap3"][0]["baseline"]["arm"] == ("baseline_cap2")
    assert [_pair_key(entry) for entry in selection["populations"]["cap3"]] == [
        ("clean_planted_edge", 50, 5, 0, 0),
        ("single_influential_case", 150, 20, 1, 2),
    ]
    assert [_pair_key(entry) for entry in selection["populations"]["cap4"]] == [
        ("clean_planted_edge", 50, 5, 0, 0),
        ("heavy_tails", 100, 10, 0, 1),
    ]


def test_selection_manifest_records_source_identity_and_canonical_checksum() -> None:
    manifest = _test_manifest()

    selection = build_selection_manifest(_task25_rows(), manifest)

    assert selection["study_manifest_checksum"] == (
        certification_budget_sensitivity_manifest_checksum(manifest)
    )
    assert selection["source_task25"] == {
        "run_id": "34895397606",
        "commit": "7b22b3fca39888e1a452cb5a7ad8ec244ccd752e",
        "artifact": "sdna-certification-usability-34895397606",
        "results_sha256": ("4ec0068d8fe2b2b62df45fccbbf71f884c50589e319e48c3a2400111ae051918"),
        "manifest_checksum": ("b47842e33092b9431220204f46c77723f2465f86a1685e1cd1c90e601bedd4ff"),
    }
    assert selection["source_task24"]["run_id"] == "34871220664"
    unsigned = {key: value for key, value in selection.items() if key != "selection_checksum"}
    expected_checksum = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert selection["selection_checksum"] == expected_checksum


def test_selection_builder_requires_exact_declared_population_counts() -> None:
    with pytest.raises(ValueError, match="population count"):
        build_selection_manifest(_task25_rows(), STUDY_MANIFEST)


def test_selection_loader_accepts_overlap_and_returns_fresh_data(tmp_path: Path) -> None:
    manifest = _test_manifest()
    path = _write_selection(tmp_path, build_selection_manifest(_task25_rows(), manifest))

    first = load_selection_manifest(path, manifest)
    first["populations"]["cap3"].clear()
    second = load_selection_manifest(path, manifest)

    assert len(second["populations"]["cap3"]) == 2
    assert len(second["populations"]["cap4"]) == 2
    assert second["overlap_rows"] == 1


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("source_task25", "results_sha256", "0" * 64),
        ("source_task25", "run_id", "other"),
        ("source_task25", "commit", "0" * 40),
        ("source_task25", "artifact", "other"),
        ("source_task24", "results_sha256", "0" * 64),
    ],
)
def test_selection_loader_rejects_changed_source_identity(
    tmp_path: Path, section: str, field: str, value: object
) -> None:
    manifest = _test_manifest()
    selection = build_selection_manifest(_task25_rows(), manifest)
    selection[section][field] = value
    _resign(selection)

    with pytest.raises(ValueError, match="source"):
        load_selection_manifest(_write_selection(tmp_path, selection), manifest)


def test_selection_loader_rejects_changed_cap_population(tmp_path: Path) -> None:
    manifest = _test_manifest()
    selection = build_selection_manifest(_task25_rows(), manifest)
    selection["populations"]["cap3"][0]["candidate"]["arm"] = "cap4"
    _resign(selection)

    with pytest.raises(ValueError, match="candidate"):
        load_selection_manifest(_write_selection(tmp_path, selection), manifest)


def test_selection_loader_rejects_duplicate_candidate_key(tmp_path: Path) -> None:
    manifest = _test_manifest()
    selection = build_selection_manifest(_task25_rows(), manifest)
    selection["populations"]["cap3"][1] = copy.deepcopy(selection["populations"]["cap3"][0])
    _resign(selection)

    with pytest.raises(ValueError, match="duplicate"):
        load_selection_manifest(_write_selection(tmp_path, selection), manifest)


def test_selection_loader_rejects_missing_baseline_row(tmp_path: Path) -> None:
    manifest = _test_manifest()
    selection = build_selection_manifest(_task25_rows(), manifest)
    del selection["populations"]["cap4"][0]["baseline"]
    _resign(selection)

    with pytest.raises(ValueError, match="baseline"):
        load_selection_manifest(_write_selection(tmp_path, selection), manifest)


def test_selection_loader_rejects_changed_selection_checksum(tmp_path: Path) -> None:
    manifest = _test_manifest()
    selection = build_selection_manifest(_task25_rows(), manifest)
    selection["selection_checksum"] = "0" * 64

    with pytest.raises(ValueError, match="checksum"):
        load_selection_manifest(_write_selection(tmp_path, selection), manifest)


def _production_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for replication in range(68):
        rows.extend(
            _pair_rows(
                n=50 + 50 * (replication % 3),
                p=5 + 5 * (replication % 2),
                scenario=f"scenario-{replication % 6}",
                parameter_id=replication,
                replication=replication,
                cap3_reached=replication < 44,
                cap4_reached=True,
            )
        )
    return rows


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    row_list = list(rows)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row_list[0]))
        writer.writeheader()
        writer.writerows(row_list)


def test_preparation_validates_task25_before_reading_and_writes_44_68(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task25_results = tmp_path / "task25-results.csv"
    _write_csv(task25_results, _production_rows())
    output = tmp_path / "selection.json"
    calls: list[str] = []
    real_read_rows = prepare_module._read_rows

    def fake_validate(*args: object) -> None:
        calls.append("validate")

    def checked_read_rows(path: str | Path) -> list[dict[str, str]]:
        assert calls == ["validate"]
        calls.append("read")
        return real_read_rows(path)

    monkeypatch.setattr(prepare_module, "validate_certification_usability", fake_validate)
    monkeypatch.setattr(prepare_module, "_read_rows", checked_read_rows)
    monkeypatch.setattr(
        prepare_module,
        "_sha256_file",
        lambda _: STUDY_MANIFEST["source_task25_results_sha256"],
    )

    prepare_certification_budget_sensitivity(
        task25_results,
        tmp_path / "task25-metadata.json",
        tmp_path / "task25-summary.json",
        tmp_path / "task24-results.csv",
        tmp_path / "task24-metadata.json",
        tmp_path / "task24-summary.json",
        Path(STUDY_MANIFEST["source_manifest"]),
        TASK25_MANIFEST_PATH,
        MANIFEST_PATH,
        output,
    )

    assert calls == ["validate", "read"]
    selection = load_selection_manifest(output, STUDY_MANIFEST)
    assert len(selection["populations"]["cap3"]) == 44
    assert len(selection["populations"]["cap4"]) == 68


def test_preparation_rejects_nonproduction_expected_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    altered = _test_manifest()
    monkeypatch.setattr(
        prepare_module,
        "load_certification_budget_sensitivity_manifest",
        lambda _: altered,
    )

    with pytest.raises(ValueError, match="44 cap-3 and 68 cap-4"):
        prepare_certification_budget_sensitivity(
            tmp_path / "task25-results.csv",
            tmp_path / "task25-metadata.json",
            tmp_path / "task25-summary.json",
            tmp_path / "task24-results.csv",
            tmp_path / "task24-metadata.json",
            tmp_path / "task24-summary.json",
            tmp_path / "source-manifest.json",
            tmp_path / "task25-manifest.json",
            tmp_path / "study-manifest.json",
            tmp_path / "selection.json",
        )
