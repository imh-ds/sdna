"""Result objects returned by SDNA estimation routines."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class NetworkDiagnostics:
    """Numerical diagnostics for a fitted network."""

    rank: int
    min_eigenvalue_correlation: float
    min_eigenvalue_shrunk_correlation: float
    condition_number: float


@dataclass(frozen=True)
class NetworkFit:
    """Shrinkage partial-correlation network and its intermediate matrices."""

    standardized: np.ndarray
    correlation: np.ndarray
    shrunk_correlation: np.ndarray
    precision: np.ndarray
    partial_correlation: np.ndarray
    shrinkage: float
    diagnostics: NetworkDiagnostics


@dataclass(frozen=True)
class InfluenceResult:
    """Case-level influence changes for a fitted network."""

    changes: np.ndarray
    method: str
