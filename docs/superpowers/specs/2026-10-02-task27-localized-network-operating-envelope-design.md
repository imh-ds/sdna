# Task 27: Localized Network Operating-Envelope Study

## Purpose

Pre-specify and execute a bounded simulation study of whether SDNA's current
case-influence and focal-edge fragility workflow remains useful for local
investigations in sparse, structured networks as the number of variables grows
under low-to-moderate sample sizes.

The target use is a researcher investigating a small set of preselected edges
or cases and using their influence/fragility patterns as clues about a larger
network. This study does not test automatic whole-network discovery, edge
selection across all possible edges, community detection, causal interpretation,
or a claim that SDNA reconstructs the full graph.

## Why this study follows Task 26

Tasks 24–26 found additional search reach at caps 3 and 4, but the additional
rows were not certified under the original budget. Raising the budget improved
certification on the fixed selected Task 25 population, but did not establish
performance on fresh data or larger networks. Those studies kept `p <= 20` and
used one focal edge without a structured community/hub/bridge topology. Task 27
therefore changes the simulated network structure and `p` range while retaining
the established low-sample workflow and reporting its operating limits.

## Design alternatives considered

1. Extend the six existing scenarios to larger `p`. This is inexpensive but
   leaves the evidence centered on a single isolated focal edge.
2. Add a sparse modular graph with explicitly defined local edge contexts and
   known case contamination, then evaluate a frozen `N × p` grid. This directly
   matches the intended localized use and is selected.
3. Compare many graph families, estimators, and network-selection procedures.
   This is deferred because it would combine operating-envelope estimation
   with a broad method-comparison program.

## Simulation model

### Population network

For each `p`, construct `p / 5` contiguous communities of five nodes each
(`p` is divisible by five on the frozen grid). Within each community, connect
nodes as a ring and connect a designated hub node to every other node in that
community. Connect adjacent communities with one bridge edge, from the last
node of one community to the hub of the next. The graph is undirected. As `p`
grows, the number of communities grows while community size, hub degree, and
local bridge structure stay fixed; this isolates network-size growth from
growth in local motif size.

Construct the precision matrix with diagonal entries `1` and off-diagonal
entries `-0.05` for graph edges, with all other entries zero. This makes all
three focal-edge contexts have the same population partial correlation
(`0.05`). A hub has at most five incident edges and every other node has at
most four, so the maximum absolute off-diagonal row sum is at most `0.25`; the
precision matrix is strictly diagonally dominant and positive definite.

Each simulated record targets exactly one pre-specified edge context:

- `within_community`: ring edge between two non-hub nodes;
- `hub_adjacent`: edge from a community hub to a non-hub node;
- `bridge`: edge connecting two adjacent communities.

Use the fixed focal edges `(module 0, node 1)-(module 0, node 2)` for
`within_community`, `(module 0, node 0)-(module 0, node 2)` for
`hub_adjacent`, and `(module 0, node 4)-(module 1, node 0)` for `bridge`.
These classes are mutually exclusive and have equal population partial
correlation, although their local degree contexts differ by construction.

The focal edge is fixed by the generator for each context and recorded in row
metadata. No data-driven edge selection is performed.

### Data conditions

Use the same three conditions for each focal-edge context:

- `clean`: sample from the population network with no planted case;
- `single_case`: choose one case without replacement and add `4.0` to both
  focal-edge variables for that case;
- `coalition`: choose three cases without replacement and add `4.0` to both
  focal-edge variables for each chosen case.

The generator records the exact planted-case indices. For each
`(N, p, condition, replication)`, use one underlying clean draw and one shared
set of planted case indices across the three focal contexts. Apply shifts only
to the selected focal variables. Cap arms share the exact same generated
dataset, case indices, and row seed for a given focal context.

### Frozen matrix

| Setting | Value |
|---|---|
| Root seed | `20261002` |
| `N` values | `50`, `100`, `150` |
| `p` values | `20`, `40`, `60` |
| Communities | `p / 5` contiguous modules, five nodes each (`4`, `8`, or `12`) |
| Focal contexts | `within_community`, `hub_adjacent`, `bridge` |
| Data conditions | `clean`, `single_case`, `coalition` |
| Replications | `10` per `N × p × context × condition` cell |
| Search-cap arms | `baseline_cap2` (`2`), `diagnostic_cap4` (`4`) |
| Fragility target | relative attenuation `0.5` |
| Certification combination budget | `1000` |
| Calibration simulations | `25` |
| Calibration reach mode | right-censored reference tails (`require_reached=False`) |
| Bootstrap draws | `100` |
| Bootstrap confidence | `0.95` |

The matrix contains `3 × 3 × 3 × 3 × 10 × 2 = 1,620` arm rows. The exact
configuration, row seeds, arm pairing keys, and output checksum contract must
be stored in a versioned machine-readable manifest before empirical execution.
The root seed is new; Task 24–26 seeds and artifacts are not reused as study
rows.

## Estimands and metrics

Report metrics separately by `N`, `p`, focal context, condition, and cap. Always
show finite denominators and preserve unreached, uncertified, failed, and
timed-out states as distinct outcomes.

Primary outcomes:

1. **Case influence recovery:** top-`k` precision and recall for known planted
   cases using the workflow's exact leave-one-out influence ranks, where `k`
   equals the number of planted cases. Report only in the two contaminated
   conditions, with both `N` and `p` strata visible.
2. **Focal-edge fragility availability:** report reached rows divided by rows
   completing the fragility stage, fragility-stage failures divided by all
   scheduled rows, certification among reached rows, certified yield among
   all scheduled rows, and budget exhaustion among reached rows. Keep
   unreached, uncertified, failed, and timed-out outcomes distinct. Cap 2 is
   the primary operating workflow; cap 4 is a paired diagnostic sensitivity
   arm.
3. **Clean false-flag behavior:** the number and proportion of clean focal-edge
   rows with descriptive reference-tail probability at or below `0.05`, with
   the number of valid clean rows as denominator and the number of invalid or
   missing rows reported separately. This is a per-prespecified-edge operating
   characteristic, not a network-wide multiplicity-adjusted error rate or a
   confirmatory test.
4. **Runtime and numerical boundary:** per-row and per-cell runtime, errors,
   shrinkage, matrix condition diagnostics, and statuses, summarized without
   excluding failed or incomplete rows from workload accounting.

For every reported proportion, show its numerator and denominator and a
descriptive 95% Wilson interval. Ten replications per cell yield imprecise
estimates; intervals describe that uncertainty and are not pass/fail gates.
The `N=50, p=60` cells (`p > N`) are explicitly labeled high-dimensional
stress cells and interpreted separately from cells with `p < N`.

Secondary summaries may include focal-edge estimate error against the known
population partial correlation and the association between influence rank and
planted status. They must be labeled descriptive and cannot replace the
pre-specified primary outcomes.

## Pairing and reproducibility

Cap arms are paired on `(N, p, focal_context, condition, replication)`. Each
pair shares the data digest, row seed, calibration stream, and bootstrap stream;
only the search cap changes. Seeds are deterministically derived from the new
root seed with independent child streams. The artifact records the exact
configuration checksum, Git commit, package/Python/NumPy versions, focal edge,
planted-case indices, per-stage statuses, and row-level timing.

The hosted run is manual-only and shards work by `p` value, with fixed shard
membership and an aggregate validator. Sharding is a scheduling choice and does
not change the estimand, random seeds, or matrix. Use the existing hosted
benchmark evidence to set a fixed per-shard time ceiling in the implementation
plan; a timed-out or incomplete shard remains incomplete and is not interpreted
as zero performance.

## Acceptance and interpretation

Technical acceptance requires all 1,620 expected rows, balanced cap pairs,
matching paired data/stream identities, valid schema and ranges, correct
focal-context and planted-case metadata, valid summary denominators, and
reproducible deterministic fields under a matched rerun. Incomplete shards,
timeouts, or numerical failures are retained and reported; they cannot be
silently dropped to make the study pass.

The report characterizes observed operating regions and failure boundaries on
this grid. It does not establish a universal `N/p` cutoff, publication-level
power, reliable whole-network recovery, or validity for ordinal, missing,
longitudinal, dependent, or causal data. No result automatically promotes
cap 4, changes the certification budget, changes v0.1 defaults, or authorizes
numerical optimization. Such decisions require a separate, explicit review of
the accepted evidence.

## Implementation boundaries

Expected implementation components are:

- immutable Task 27 simulation manifest and strict loader/validator;
- deterministic sparse modular-network DGP with truth metadata and regression
  coverage;
- paired runner and per-`p` hosted shards;
- artifact validator, aggregate summaries, and user-facing v1 protocol/report;
- an append-only decision-log entry with exact commit and hosted run/artifact
  identities.

The existing v0.1 matrix, Task 24–26 configurations/artifacts, estimator,
production `search_cap=2`, and certification budget remain unchanged. Any
necessary generic runner changes must preserve prior artifact contracts and
have focused regression coverage.
