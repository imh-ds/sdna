# Certification-budget sensitivity study v2: hosted results

**Status:** Task 26 Task 6 hosted acceptance complete. The v1 page remains the
frozen pre-specification; this v2 records execution, results, and interpretation
without changing the protocol.

The binding protocol is the [v1 pre-specification](certification_budget_sensitivity_study_v1.md),
along with its [design](../superpowers/specs/2026-09-14-task26-certification-budget-sensitivity-design.md),
[implementation plan](../superpowers/plans/2026-09-14-task26-certification-budget-sensitivity.md),
and [frozen manifest](../../simulations/configs/certification_budget_sensitivity_v1.json).
The decision log records implementation and acceptance provenance in
[ADR-025's Task 6 addendum](../development/decisions.md).

## Accepted hosted run

The [accepted GitHub Actions run](https://github.com/imh-ds/sdna/actions/runs/35015629850)
completed successfully on `main`, commit
`225aabe2a757a01720c00ec05f307219e930afad`. It ran from 2026-09-15 19:46:32
to 19:49:13 UTC (2 minutes 41 seconds). Its preparation, all four budget arms,
per-arm validators, aggregate validation, and final completeness gate passed.

The exact Task 25 population source was run `34895397606`, commit
`7b22b3fca39888e1a452cb5a7ad8ec244ccd752e`, with `results.csv` SHA-256
`4ec0068d8fe2b2b62df45fccbbf71f884c50589e319e48c3a2400111ae051918` and
manifest checksum
`b47842e33092b9431220204f46c77723f2465f86a1685e1cd1c90e601bedd4ff`.
The nested Task 24 source was run `34871220664`, commit
`338b0d95cdb312b2805affb0de458e06508d80f0`, with `results.csv` SHA-256
`110d0b4f266b253251ac1a64bb4195b61722008d426b74c75802d3de57b43d87` and
manifest checksum
`415576f1fec5ccd2a47e0ad411d29e4d48c6e8e370609ae495ccc877fe74e974`.

The validated selection manifest checksum is
`125f5dc52e6669c36c2f095759a24324e55dee504b23429ed9d721c95ee55b23`.
The frozen study manifest checksum is
`5601beebd6ff398b518e5d64646a3ce507c5cc9b3fa87d1ebc785b997c6e46fb`.
It contains 44 cap-3 rows and 68 cap-4 rows, with 44 overlapping pairing
keys and 68 unique keys. These remain separate cap-specific denominators; the
overlap is not collapsed or counted as 112 unique keys.

## Results

Each budget arm completed and validated 112 rows (44 cap 3, 68 cap 4). The
aggregate contains the expected 448 cap-budget rows. All five aggregate checks
passed: all budget arms are present, valid, and complete; the expected total
was observed; and the cap-specific populations remain separate. No row had a
workflow error or nonempty error stage. Across all rows, calibration was
right-censored as pre-specified, and Wald, bootstrap, and overall workflow
statuses were `ok`.

| Combination budget | Cap-3 certified | Cap-3 exhausted | Cap-4 certified | Cap-4 exhausted | Runner time (s) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1,000 | 0/44 (0.0%) | 44 | 0/68 (0.0%) | 68 | 36.84 |
| 5,000 | 18/44 (40.9%) | 26 | 18/68 (26.5%) | 50 | 49.17 |
| 10,000 | 36/44 (81.8%) | 8 | 36/68 (52.9%) | 32 | 81.62 |
| 20,000 | 44/44 (100.0%) | 0 | 44/68 (64.7%) | 24 | 64.15 |

Across all four budgets and both cap populations, there were 196 certified
rows and 252 valid `combination_budget_exhausted` outcomes. There were no arm
timeouts, incomplete arms, or failed arms in the accepted run. Per-key
certification did not revert from certified at a lower budget to uncertified
at a higher budget.

As a secondary descriptive check, the 44 overlapping pairing keys had the same
certification indicator under cap 3 and cap 4 at each budget (zero discordant
keys). The 24 cap-4-only keys did not certify at any tested budget. This is a
description of the selected cells, not a cap comparison or promotion claim;
the cap-specific denominators and Task 25 selection rule remain as
pre-specified.

## Runtime and practical scope

The four arm runners took 36.84, 49.17, 81.62, and 64.15 seconds respectively
(231.79 arm-seconds in total). The longest arm used about 4.5% of its
1,800-second computation ceiling; the longest GitHub Actions budget job took
1 minute 38 seconds, well below the 40-minute job limit. For this exact
112-row-per-budget workload, the measured runtime does not justify optimization
before expanding the experiment.

These timings are an observed limit for the committed v0.1 matrix only: six
scenarios, the fixed Task 25 population, 25 calibration simulations, 100
bootstrap replicates, and four declared budgets. They do not establish a
universal runtime bound for larger populations, additional replications,
different DGPs, or new budgets.

## Failed initial attempt and correction

The [first manual run, `35014406444`](https://github.com/imh-ds/sdna/actions/runs/35014406444)
on commit
`423600357c9f9ac765be962d1bd8e14789e608fe`, is a failed diagnostic attempt and
is not included in the results above. All four arms stopped after five rows
with `ValueError: could not convert string to float: ''`; aggregation correctly
marked the study incomplete. The next selected `heavy_tails` row had an empty
`parameter` field because that DGP, like the other unparameterized scenarios,
does not consume a numeric scenario parameter. Task 26's canonicalizer had
incorrectly coerced every scenario's field to `float`.

The correction in [PR #21](https://github.com/imh-ds/sdna/pull/21) converts the parameter only for
`clean_planted_edge` and `coalition_contamination`, preserving `None` for other
scenarios. It changed neither the selection nor any pre-specified study
constant. The regression fixture now models the source schema. The corrected
code passed the 262-test suite, Ruff, strict mypy, and a real local 1,000-budget
arm (112/112 valid rows) before the manual workflow was rerun on the merged
commit.

## Artifact identity and checksums

The run retains these GitHub Actions artifacts for 90 days:

- `sdna-certification-budget-sensitivity-35015629850`
- `sdna-certification-budget-selection-35015629850`
- `sdna-certification-budget-arm-1000-35015629850`
- `sdna-certification-budget-arm-5000-35015629850`
- `sdna-certification-budget-arm-10000-35015629850`
- `sdna-certification-budget-arm-20000-35015629850`

Aggregate output SHA-256 values (the selection manifest's file hash is distinct
from its canonical selection checksum):

| Aggregate file | SHA-256 |
| --- | --- |
| `results.csv` | `92d0324dea5ec018b806dcfdea91cae689dbd9b1a29040342d27de4b680aff21` |
| `summary.json` | `7b7e88e8312ab3c09a59606b050567a8b9b2ae44c8efe7fb720809fc7ba7f173` |
| `summary.md` | `8f61511b4fd44f2ad63094ef2dcb1b026c672e93302d5177ab473de895f3a8f2` |
| `selection_manifest.json` | `9a06ba50b765f4614646a7e7dbdbd01c0dabe3108bfd6034e2ca2c2ff1a39163` |
| `arm_status_1000.json` | `121b1cf7fbd70ced4ac566f94a490be72e7e8cb8211cc2be5ce50e1dc73f0110` |
| `arm_status_5000.json` | `4a9d120450c1c9940252d3512d9826cffb851a3881866db70948c96ac97d8d62` |
| `arm_status_10000.json` | `c6f9fec422f6edb03eca09c8768cb915b8ae71b4c85a8768ad23dc1cc4f97b75` |
| `arm_status_20000.json` | `109c05b169a59753330a1035ca492882fb34b2a207d8a02eb157844d62fec196` |

Hashes below were independently computed from the downloaded per-budget arm
artifacts. The status hashes match the aggregate's copied per-budget status
files above.

| Budget | `results.csv` | `results.metadata.json` | `arm_status.json` | `arm_validation.json` |
| ---: | --- | --- | --- | --- |
| 1,000 | `f40f8d36918022bacc6408cfbc8ec88843f4b9836d9edc43cec3c5a97ccce2fb` | `9aa604637b35a05a08526f807e44ea701f2716d47cd425df1f1a1df359940ae8` | `121b1cf7fbd70ced4ac566f94a490be72e7e8cb8211cc2be5ce50e1dc73f0110` | `e47f382355675a28f892051fd81d5da27b91c0dd276c9bd57579645e769f4462` |
| 5,000 | `f528d88321f62d7c5f72cc352d05a7f05972a8248340a41b7427aaf2bdd0c7d0` | `3f4057b513fdbbe355513ede9a5f0a7ba17bac9aa34bf774c17e9d14a99fc161` | `4a9d120450c1c9940252d3512d9826cffb851a3881866db70948c96ac97d8d62` | `b60658037dbb09bb2c1a6b69c505e3ccfae746ef0fcb9bfb4eff6419e9356f74` |
| 10,000 | `034b4ee0d652dca16c2aeb10a496a9d6c42de8a3c5b0ba79dbb627174947a231` | `5f40653f079e9599ac5cad46c16018c42bf6b9c22fcb9fa1b77a1a3018b9fe56` | `c6f9fec422f6edb03eca09c8768cb915b8ae71b4c85a8768ad23dc1cc4f97b75` | `3c46c8bb7bd776949e409258e3fa07dc9ce3cf801d87822181845479aa59adfd` |
| 20,000 | `9d19b6f7bf38da0a47f0a19f3a63c4c41c133e01ae6670eb6d4d091c82bf836f` | `5f7c699d37f90edf9c781d54f6475cdb673dbe8aae59294d15e13687ce8fa9d3` | `109c05b169a59753330a1035ca492882fb34b2a207d8a02eb157844d62fec196` | `21eaf1a7cd8a2768e40c152fc9d0a587116df4ec20abba7310708c0a2ebb3008` |

The accepted environment was Python `3.11.16`, NumPy `2.4.6`, package
`0.1.0a0`, on Linux x86-64. The complete source identities, full run history,
and correction files are itemized in the linked decision-log addendum.

## Interpretation and limits

The results show budget sensitivity for these fixed Task 25 newly reached
records: the 1,000-combination baseline certified none, while certification
counts rose over the pre-specified grid. At 20,000, 24 of the 68 cap-4 records
still exhausted the row budget. The findings are conditional on this selected
population and protocol; they do not estimate performance on a fresh sample.

No cap is promoted and no production certification budget is changed. The
1,000 setting remains the declared Task 25 baseline; Task 26 is evidence, not
a production decision. Any additional budget range, optimization work, or
expanded population requires a new pre-specification before execution.
