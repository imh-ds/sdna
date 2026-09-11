"""Shared pytest configuration for the SDNA test suite."""

import numpy as np
import pytest


@pytest.fixture
def gaussian_data() -> np.ndarray:
    rng = np.random.default_rng(20260910)
    factors = rng.normal(size=(40, 2))
    loadings = rng.normal(size=(2, 5)) * 0.35
    return rng.normal(size=(40, 5)) + factors @ loadings
