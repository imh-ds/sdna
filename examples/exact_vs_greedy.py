"""Compare greedy fragility with bounded exact certification."""

import numpy as np

from sdna.fragility import FragilityTarget, certify_fragility, greedy_fragility


def main() -> None:
    rng = np.random.default_rng(20260910)
    data = rng.normal(size=(20, 5))
    target = FragilityTarget("relative", 0.5)
    greedy = greedy_fragility(data, edge=(0, 1), target=target, search_cap=4)
    print(greedy)
    if greedy.reached:
        print(certify_fragility(data, greedy, max_combinations=200_000))


if __name__ == "__main__":
    main()
