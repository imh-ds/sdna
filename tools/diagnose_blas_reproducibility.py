"""Record how seeded Task 27 data generation varies with the BLAS/LAPACK environment.

Writes one JSON object describing the CPU, NumPy/OpenBLAS build, relevant
environment variables, and byte-level digests of (a) the current
``multivariate_normal`` (SVD) generation path, (b) the SVD sign pattern of the
population covariance, and (c) a Cholesky-based alternative, for each Task 27
``p``. Diagnostic only: it does not change any study path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
from typing import Any

import numpy as np

from simulations.localized_network_dgp import SUPPORTED_P, build_localized_population

N_ROWS = 150
SEED = 12345
ENV_KEYS = ("OPENBLAS_CORETYPE", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")


def _digest(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()[:16]


def cpu_model() -> str | None:
    path = Path("/proc/cpuinfo")
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    return platform.processor() or None


def probe() -> dict[str, Any]:
    result: dict[str, Any] = {
        "cpu_model": cpu_model(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "env": {key: os.environ.get(key) for key in ENV_KEYS},
        "per_p": {},
    }
    config = np.show_config(mode="dicts")
    if isinstance(config, dict):
        blas = config.get("Build Dependencies", {}).get("blas", {})
        result["blas"] = {k: blas.get(k) for k in ("name", "version", "openblas configuration")}
    for p in SUPPORTED_P:
        covariance = build_localized_population(p).covariance
        child, _ = np.random.SeedSequence(SEED).spawn(2)
        data = np.random.default_rng(child).multivariate_normal(
            np.zeros(p), covariance, size=N_ROWS
        )
        _, _, vt = np.linalg.svd(covariance)
        signs = np.sign(vt[np.arange(p), np.argmax(np.abs(vt), axis=1)]).astype(int)
        z = np.random.default_rng(child).standard_normal((N_ROWS, p))
        cholesky_data = z @ np.linalg.cholesky(covariance).T
        result["per_p"][str(p)] = {
            "mvn_svd_digest": _digest(data),
            "mvn_svd_first_value": float(data[0, 0]),
            "svd_sign_pattern": "".join("+" if s > 0 else "-" for s in signs),
            "cholesky_digest": _digest(cholesky_data),
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(probe(), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
