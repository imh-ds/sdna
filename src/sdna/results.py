"""Result objects returned by SDNA estimation routines."""

from dataclasses import dataclass
from typing import Literal

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


@dataclass(frozen=True)
class FragilityTarget:
    """Stopping rule for an edge-fragility search."""

    kind: Literal["relative", "absolute", "sign_reversal"]
    value: float | None = None

    def __post_init__(self) -> None:
        if self.kind == "relative":
            if self.value is None or not 0.0 < self.value < 1.0:
                raise ValueError("relative target value must be between 0 and 1")
        elif self.kind == "absolute":
            if self.value is None or self.value < 0.0:
                raise ValueError("absolute target value must be nonnegative")
        elif self.kind == "sign_reversal":
            if self.value is not None:
                raise ValueError("sign_reversal target value must be None")
        else:
            raise ValueError(f"unknown fragility target: {self.kind}")


@dataclass(frozen=True)
class FragilityResult:
    """Outcome of a greedy fragility search."""

    edge: tuple[int, int]
    target: FragilityTarget
    full_value: float
    reached: bool
    greedy_count: int | None
    cases: tuple[int, ...]
    trajectory: np.ndarray
    certified: bool = False
    exact_minimum: int | None = None
    combinations_checked: int = 0


@dataclass(frozen=True)
class CalibrationResult:
    """Observed and clean-reference fragility calibration results."""

    edge: tuple[int, int]
    target: FragilityTarget
    observed_count: int | None
    observed_reached: bool
    reference_counts: tuple[int | None, ...]
    reference_reached: tuple[bool, ...]
    reference_edge_estimates: np.ndarray
    reference_tail_probability: float | None
