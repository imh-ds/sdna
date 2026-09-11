"""Input validation for the SDNA numerical core."""

import numpy as np


def validate_data(X: np.ndarray) -> np.ndarray:
    """Convert and validate a continuous-observation data matrix."""
    data = np.asarray(X, dtype=float)
    if data.ndim != 2:
        raise ValueError("X must be a 2-D data matrix")
    if not np.all(np.isfinite(data)):
        raise ValueError("X must contain only finite values")
    n, p = data.shape
    if n < 3:
        raise ValueError("X must have at least 3 rows")
    if p < 2:
        raise ValueError("X must have at least 2 columns")
    if np.any(np.ptp(data, axis=0) == 0.0):
        raise ValueError("X must not contain zero variance columns")
    return data


def validate_shrinkage(shrinkage: float) -> float:
    """Validate a fixed shrinkage intensity."""
    value = float(shrinkage)
    if not np.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError("shrinkage must be between 0 and 1")
    return value
