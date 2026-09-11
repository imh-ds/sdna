"""Small benchmark for exact leave-one-out influence."""

from time import perf_counter

import numpy as np

from sdna.estimation import fit_network
from sdna.influence import exact_loo_influence


def benchmark(n: int, p: int) -> float:
    rng = np.random.default_rng(20260910 + n + p)
    data = rng.normal(size=(n, p))
    fitted = fit_network(data)
    start = perf_counter()
    exact_loo_influence(data, fitted)
    return perf_counter() - start


if __name__ == "__main__":
    for n, p in ((50, 10), (100, 15), (150, 20)):
        print(f"N={n:3d}, p={p:2d}: {benchmark(n, p):.3f}s")
