# CI quality-gate scope

The CI workflow applies different gates to the package and to the experimental
execution harnesses.

## Workflow triggers and required checks

Pull requests run both repository checks:

- `Test`, which runs the Python-version test matrix, Ruff, strict package
  mypy, and coverage-enabled tests.
- `Simulation smoke test`, which runs the fixed-seed end-to-end simulation,
  summary generation, and invariant validation.

The workflows also run on pushes to `main` and can be started manually. They
do not run a second copy for ordinary feature-branch pushes when a pull request
is open. Each workflow cancels an older in-progress run for the same pull
request or branch when a newer commit supersedes it.

For protected `main`, configure the check names `Test / Python 3.11`,
`Test / Python 3.12`, `Test / Python 3.13`, and `Simulation smoke test` as
required status checks in GitHub branch protection. The full validation matrix
remains a separate, explicitly invoked research workflow rather than a
pull-request gate.

The reduced validation matrix is defined in
`simulations/configs/validation_matrix.json` and runs through
`.github/workflows/validation-matrix.yml`. It is available through manual
dispatch. The fixed configuration covers all six scenarios, `N=[50, 100]`,
`p=[5, 10]`, and two replications per cell (48 rows total), with five
calibration simulations and twenty bootstrap draws.
The workflow uses the smoke safety caps and uploads the exact configuration,
run metadata, CSV results, JSON summary, and Markdown summary as a 30-day
artifact. These outputs are reproducibility and workflow evidence, not
publication-level operating-characteristic results.

## Ruff

Ruff checks all repository Python areas that are part of the development
workflow:

- `src`
- `tests`
- `simulations`
- `benchmarks`
- `tools`

This catches formatting, import, and common correctness issues throughout the
code that contributors run or modify.

## mypy

Strict mypy checks only `src/sdna`, the distributable library and its public
implementation contract. `simulations/`, `benchmarks/`, and `tools/` are
experimental harnesses with dynamically shaped row dictionaries and helper
records; they currently have known strict-mypy errors that are not part of the
package type contract. Expanding the type gate to those directories would
require a separate typing-cleanup task rather than silently weakening the
existing package gate.

Those harnesses remain CI-covered by Ruff and the test suite. A future typing
task can promote them into the mypy gate once their data structures and error
handling are explicitly typed.
