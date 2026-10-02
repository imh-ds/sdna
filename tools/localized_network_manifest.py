"""Load and expand the immutable Task 27 localized-network manifest."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

__all__ = [
    "DATA_SEED_FIELDS",
    "LOCALIZED_PAIRING_FIELDS",
    "expand_localized_jobs",
    "load_localized_manifest",
    "localized_data_seed",
    "localized_data_seed_key",
    "localized_manifest_checksum",
    "localized_pairing_keys",
]

LOCALIZED_PAIRING_FIELDS = (
    "N",
    "p",
    "focal_context",
    "condition",
    "replication",
)
DATA_SEED_FIELDS = ("N", "p", "condition", "replication")

_EXPECTED_MANIFEST: dict[str, Any] = {
    "version": 1,
    "study": "localized_network_operating_envelope",
    "seed": 20261002,
    "replications": 10,
    "n_values": [50, 100, 150],
    "p_values": [20, 40, 60],
    "modules": {
        "nodes_per_module": 5,
        "within_module_edges": ["ring", "hub_to_all_other_nodes"],
        "between_module_edges": ["last_node_to_next_module_hub"],
    },
    "population": {
        "precision_diagonal": 1.0,
        "edge_precision": -0.05,
        "focal_partial_correlation": 0.05,
    },
    "focal_contexts": ["within_community", "hub_adjacent", "bridge"],
    "conditions": ["clean", "single_case", "coalition"],
    "condition_settings": {
        "clean": {"planted_case_count": 0, "shift": 0.0},
        "single_case": {"planted_case_count": 1, "shift": 4.0},
        "coalition": {"planted_case_count": 3, "shift": 4.0},
    },
    "arms": [
        {"name": "baseline_cap2", "target": 0.5, "search_cap": 2, "role": "primary"},
        {
            "name": "diagnostic_cap4",
            "target": 0.5,
            "search_cap": 4,
            "role": "diagnostic",
        },
    ],
    "certification_combination_budget": 1000,
    "calibration_simulations": 25,
    "calibration_require_reached": False,
    "reference_tail_treatment": "right_censored",
    "bootstrap_draws": 100,
    "bootstrap_confidence": 0.95,
    "operational_runtime_ceiling_seconds": 3600,
    "actions_timeout_minutes": 70,
    "expected_pairing_keys": 810,
    "expected_rows": 1620,
    "expected_pairing_keys_per_p": 270,
    "expected_rows_per_p": 540,
}


def localized_manifest_checksum(manifest: Mapping[str, Any]) -> str:
    """Return SHA-256 over canonical compact JSON, independent of key order."""
    encoded = json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _validate_localized_manifest(manifest: object) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise TypeError("localized-network manifest must be an object")
    try:
        encoded = _canonical_json(manifest)
    except (TypeError, ValueError) as error:
        raise ValueError("manifest must contain valid canonical JSON values") from error
    if encoded != _canonical_json(_EXPECTED_MANIFEST):
        raise ValueError("manifest does not match the frozen Task 27 contract")
    return manifest


def load_localized_manifest(path: str | Path) -> dict[str, Any]:
    """Load and strictly validate the frozen Task 27 manifest."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    manifest = _validate_localized_manifest(raw)
    # JSON decoding creates fresh containers; return an independent manifest copy.
    return json.loads(_canonical_json(manifest))


def localized_data_seed_key(job: Mapping[str, Any]) -> tuple[int, int, str, int]:
    """Return exactly ``(N, p, condition, replication)`` for data/case seeding.

    Focal context and arm are deliberately excluded so all contexts and caps
    reuse the same clean draw and planted-case indices for a given key.
    """
    missing = [field for field in DATA_SEED_FIELDS if field not in job]
    if missing:
        raise ValueError(f"job is missing data-seed fields: {', '.join(missing)}")
    n, p, condition, replication = (job[field] for field in DATA_SEED_FIELDS)
    if (
        isinstance(n, bool)
        or not isinstance(n, int)
        or isinstance(p, bool)
        or not isinstance(p, int)
        or not isinstance(condition, str)
        or isinstance(replication, bool)
        or not isinstance(replication, int)
    ):
        raise TypeError("data-seed key must contain (int, int, str, int)")
    return (n, p, condition, replication)


def localized_data_seed(
    root_seed: int, data_seed_key: tuple[int, int, str, int]
) -> int:
    """Derive a stable 64-bit data/case seed from the root seed and four-field key."""
    if isinstance(root_seed, bool) or not isinstance(root_seed, int) or root_seed < 0:
        raise ValueError("root_seed must be a nonnegative integer")
    if not isinstance(data_seed_key, tuple) or len(data_seed_key) != len(DATA_SEED_FIELDS):
        raise ValueError("data_seed_key must be (N, p, condition, replication)")
    n, p, condition, replication = data_seed_key
    if (
        isinstance(n, bool)
        or not isinstance(n, int)
        or n < 1
        or isinstance(p, bool)
        or not isinstance(p, int)
        or p < 1
        or not isinstance(condition, str)
        or isinstance(replication, bool)
        or not isinstance(replication, int)
        or replication < 0
    ):
        raise ValueError(
            "data_seed_key must contain (positive N, positive p, condition, replication)"
        )
    encoded = json.dumps(
        [root_seed, *data_seed_key], separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return int.from_bytes(hashlib.sha256(encoded).digest()[:8], byteorder="big")


def expand_localized_jobs(
    manifest: Mapping[str, Any], p_shard: int | None = None
) -> list[dict[str, Any]]:
    """Expand the frozen manifest into deterministic arm-specific jobs."""
    frozen = _validate_localized_manifest(dict(manifest))
    if p_shard is not None:
        if isinstance(p_shard, bool) or not isinstance(p_shard, int):
            raise TypeError("p_shard must be one of the frozen p values")
        if p_shard not in frozen["p_values"]:
            raise ValueError(f"p_shard must be one of {frozen['p_values']}")

    jobs: list[dict[str, Any]] = []
    for arm in frozen["arms"]:
        for n in frozen["n_values"]:
            for p in frozen["p_values"]:
                if p_shard is not None and p != p_shard:
                    continue
                for focal_context in frozen["focal_contexts"]:
                    for condition in frozen["conditions"]:
                        for replication in range(frozen["replications"]):
                            jobs.append(
                                {
                                    "arm": arm["name"],
                                    "N": n,
                                    "p": p,
                                    "focal_context": focal_context,
                                    "condition": condition,
                                    "replication": replication,
                                    "data_seed": localized_data_seed(
                                        frozen["seed"],
                                        (n, p, condition, replication),
                                    ),
                                    "target": arm["target"],
                                    "search_cap": arm["search_cap"],
                                }
                            )
    expected_rows = (
        frozen["expected_rows"]
        if p_shard is None
        else frozen["expected_rows_per_p"]
    )
    if len(jobs) != expected_rows:
        raise ValueError(f"expanded rows={len(jobs)} does not match {expected_rows}")
    return jobs


def localized_pairing_keys(
    manifest: Mapping[str, Any], p_shard: int | None = None
) -> list[tuple[Any, ...]]:
    """Return the ordered unique cap-pair keys, optionally for one p shard."""
    jobs = expand_localized_jobs(manifest, p_shard=p_shard)
    keys = {tuple(job[field] for field in LOCALIZED_PAIRING_FIELDS) for job in jobs}
    ordered = sorted(keys, key=lambda key: (key[0], key[1], key[2], key[3], key[4]))
    expected = (
        _EXPECTED_MANIFEST["expected_pairing_keys"]
        if p_shard is None
        else _EXPECTED_MANIFEST["expected_pairing_keys_per_p"]
    )
    if len(ordered) != expected:
        raise ValueError(f"expanded pairing keys={len(ordered)} does not match {expected}")
    return ordered
