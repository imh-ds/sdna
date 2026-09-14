"""Run the paired cap-expansion workflow with certification diagnostics."""

from __future__ import annotations

import argparse
from pathlib import Path

from tools.run_cap_expansion import run_cap_expansion

__all__ = ["run_certification_usability"]


def run_certification_usability(config_path: str | Path, output_path: str | Path) -> None:
    """Run the frozen cap-expansion matrix with diagnostics enabled."""
    run_cap_expansion(
        config_path,
        output_path,
        include_certification_diagnostics=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    run_certification_usability(args.config, args.output)


if __name__ == "__main__":
    main()
