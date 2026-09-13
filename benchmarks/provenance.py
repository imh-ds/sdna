"""Shared provenance helpers for reproducible benchmark artifacts."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from sdna import __version__


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _inferred_settings(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    settings: dict[str, Any] = {}
    for field in ("N", "p", "seed", "repeats", "calibration_simulations", "search_cap"):
        values = sorted({row[field] for row in rows if field in row}, key=lambda value: str(value))
        if values:
            settings[field] = values[0] if len(values) == 1 else values
    return settings


def benchmark_payload(
    benchmark: str,
    rows: Sequence[Mapping[str, Any]],
    settings: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return benchmark rows with environment and configuration provenance."""
    metadata = {
        "benchmark": benchmark,
        "git_commit": _git_commit(),
        "package_version": __version__,
        "python_version": sys.version,
        "numpy_version": np.__version__,
        "settings": dict(settings) if settings is not None else _inferred_settings(rows),
    }
    return {"metadata": metadata, "rows": list(rows)}


def write_payload(
    benchmark: str,
    rows: Sequence[Mapping[str, Any]],
    output: str | Path,
    settings: Mapping[str, Any] | None = None,
) -> None:
    """Write a benchmark JSON artifact with auditable provenance."""
    payload = benchmark_payload(benchmark, rows, settings)
    Path(output).write_text(json_dumps(payload), encoding="utf-8")


def json_dumps(payload: Mapping[str, Any]) -> str:
    """Serialize benchmark payloads with stable indentation and a final newline."""
    import json

    return json.dumps(payload, indent=2) + "\n"
