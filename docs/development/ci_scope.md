# CI quality-gate scope

The CI workflow applies different gates to the package and to the experimental
execution harnesses.

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
