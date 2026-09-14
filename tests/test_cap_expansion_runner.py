"""Tests for the paired full-workflow cap-expansion runner."""

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from tools import run_cap_expansion as cap_runner
from tools.cap_expansion_manifest import PAIRING_FIELDS


MANIFEST_PATH = Path("simulations/configs/cap_expansion_v1.json")


def _small_jobs() -> list[dict[str, object]]:
    return [
        {
            "arm": arm,
            "scenario": "clean_planted_edge",
            "parameter_id": 0,
            "parameter": 0.2,
            "replication": 0,
            "N": 12,
            "p": 3,
            "target": 0.5,
            "search_cap": cap,
        }
        for arm, cap in (("baseline_cap2", 2), ("cap3", 3), ("cap4", 4))
    ]


def test_cap_expansion_runner_reuses_data_and_child_seeds(tmp_path, monkeypatch) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest.update(
        {
            "calibration_simulations": 1,
            "bootstrap_samples": 2,
            "certification_combination_budget": 20,
        }
    )
    monkeypatch.setattr(cap_runner, "load_cap_expansion_manifest", lambda _: manifest)
    monkeypatch.setattr(cap_runner, "expand_cap_expansion_jobs", lambda _: _small_jobs())

    generated: list[np.ndarray] = []
    original_generate = cap_runner.generate_cap_expansion_dataset

    def tracked_generate(job, seed, frozen_manifest):
        dataset = original_generate(job, seed, frozen_manifest)
        generated.append(dataset.X.copy())
        return dataset

    monkeypatch.setattr(cap_runner, "generate_cap_expansion_dataset", tracked_generate)
    output = tmp_path / "cap-expansion.csv"

    cap_runner.run_cap_expansion(MANIFEST_PATH, output)

    with output.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row[field] for field in PAIRING_FIELDS)].append(row)

    assert len(rows) == 3
    assert len(grouped) == 1
    assert {row["arm"] for row in next(iter(grouped.values()))} == {
        "baseline_cap2",
        "cap3",
        "cap4",
    }
    group = next(iter(grouped.values()))
    for field in ("data_seed", "calibration_seed", "bootstrap_seed", "dataset_digest"):
        assert len({row[field] for row in group}) == 1
    assert len(generated) == 1

    metadata = json.loads(output.with_suffix(".metadata.json").read_text(encoding="utf-8"))
    assert metadata["rows"] == 3
    assert metadata["arm_rows"] == {"baseline_cap2": 1, "cap3": 1, "cap4": 1}
    assert set(metadata["timing"]["arm_elapsed_seconds"]) == {
        "baseline_cap2",
        "cap3",
        "cap4",
    }
