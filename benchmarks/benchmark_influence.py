"""Small benchmark for exact leave-one-out influence."""

from time import perf_counter

import numpy as np

from sdna.estimation import fit_network
from sdna.influence import analytic_influence, exact_loo_influence


def benchmark(n: int, p: int) -> float:
    rng = np.random.default_rng(20260910 + n + p)
    data = rng.normal(size=(n, p))
    fitted = fit_network(data)
    start = perf_counter()
    exact_loo_influence(data, fitted)
    return perf_counter() - start


def approximation_metrics(n: int, p: int) -> tuple[float, float, float]:
    rng = np.random.default_rng(20260910 + n + p)
    data = rng.normal(size=(n, p))
    fitted = fit_network(data)
    exact = exact_loo_influence(data, fitted).changes
    approx = analytic_influence(fitted).changes
    iu = np.triu_indices(p, 1)
    a = approx[:, iu[0], iu[1]].ravel()
    b = exact[:, iu[0], iu[1]].ravel()
    slope = float(np.polyfit(a, b, 1)[0])
    mae = float(np.mean(np.abs(a - b)))
    maximum = float(np.max(np.abs(a - b)))
    return slope, mae, maximum


if __name__ == "__main__":
    for n, p in ((50, 10), (100, 15), (150, 20)):
        slope, mae, maximum = approximation_metrics(n, p)
        print(
            f"N={n:3d}, p={p:2d}: {benchmark(n, p):.3f}s "
            f"slope={slope:.4f} MAE={mae:.6f} max|error|={maximum:.6f}"
        )
