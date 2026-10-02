# Task 27: Localized Network Operating Envelope (v1 protocol)

**Status:** Pre-specified protocol; hosted execution and empirical findings are pending.

## Purpose and scope

This study evaluates SDNA's existing case-influence and focal-edge fragility workflow for localized investigations in sparse, structured networks as the number of variables grows under low-to-moderate sample sizes. The intended use is to examine a small set of edges or cases chosen before analysis and use their influence or fragility patterns as clues for further investigation.

This is not a study of automatic whole-network discovery, data-driven edge selection over all possible edges, community detection, causal interpretation, or complete graph recovery. It does not establish that SDNA reconstructs a network.

## Frozen design

The machine-readable source of truth is [`localized_network_v1.json`](../../simulations/configs/localized_network_v1.json); the loader rejects deviations from its frozen contract. The planned hosted execution is manual-only (`workflow_dispatch`) and is divided into fixed `p=20`, `p=40`, and `p=60` shards. Sharding does not change the matrix or estimands.

| Component | Prespecified values |
|---|---|
| Root seed | `20261002` |
| Sample sizes (`N`) | `50`, `100`, `150` |
| Variable counts (`p`) | `20`, `40`, `60` |
| Network modules | `p/5` contiguous modules, five nodes each |
| Focal contexts | `within_community`, `hub_adjacent`, `bridge` |
| Conditions | `clean`, `single_case`, `coalition` |
| Replications | `10` in each `N × p × context × condition` cell |
| Arms | `baseline_cap2` (`search_cap=2`, primary); `diagnostic_cap4` (`search_cap=4`, diagnostic only) |
| Fragility target | Relative attenuation `0.5` |
| Certification budget | `1,000` combinations |
| Calibration | `25` simulations; right-censored reference tails (`require_reached=false`) |
| Bootstrap | `100` draws; confidence `0.95` |
| Runtime limits | `3,600` seconds per `p` shard; `70` minutes per Actions job |

The full matrix has `810` pairing keys and `1,620` arm rows. Each `p` shard has `270` pairing keys and `540` arm rows. Pairing keys are `(N, p, focal_context, condition, replication)`; the two arms share the generated dataset, data/case seed, calibration seed, bootstrap seed, and digest. Only the search cap differs. The data/case seed is derived from root seed and `(N, p, condition, replication)`, so the three contexts share the underlying clean draw and planted-case indices.

In plain terms, baseline cap 2 is the primary operating workflow; diagnostic cap 4 is included only as paired sensitivity evidence. Neither arm changes the production configuration.

The population is Gaussian with a sparse modular graph. Each five-node module contains a ring and a hub connected to its other four nodes; adjacent modules are linked by one edge. The precision matrix has diagonal `1` and edge entries `-0.05`, giving each prespecified focal edge a population partial correlation of `0.05`. The focal edges are fixed at `(1,2)` for `within_community`, `(0,2)` for `hub_adjacent`, and `(4,5)` for `bridge`. They are supplied by the generator, not selected from the observations.

Clean data have no planted cases. In `single_case`, one case is sampled without replacement; in `coalition`, three are sampled without replacement. For each planted case, `4.0` is added to the two variables of that context's focal edge. The exact indices are recorded. No Task 24–26 rows or seeds are reused.

The `N=50, p=60` cells have `p > N`. Label these as high-dimensional stress cells and interpret them separately from `p < N` cells. This grid does not locate or imply a general `N/p` boundary.

## Outcomes and denominators

Report by `N × p × focal context × condition × arm`. For every proportion report the numerator, denominator, and descriptive two-sided 95% Wilson interval. These intervals describe sampling uncertainty; they are not pass/fail criteria. If a denominator is zero, report the estimate and interval as undefined (`null`), never as zero.

| Outcome | Numerator / denominator |
|---|---|
| Fragility reach rate | Reached rows / rows completing the fragility stage |
| Fragility-stage failure rate | Fragility-stage errors / all scheduled rows |
| Certification given reach | Certified rows / reached rows |
| Certified yield | Certified rows / all scheduled rows |
| Certification-budget exhaustion given reach | Budget-exhausted rows / reached rows |
| Clean descriptive false-flag rate | Valid clean rows with right-censored reference-tail probability `≤0.05` / clean rows with a valid finite reference-tail probability |

The clean false-flag result is a per-prespecified-edge descriptive operating characteristic. It is not a network-wide result, does not control multiplicity over edges, and is not a confirmatory test. Invalid or missing clean reference-tail values are counted separately and excluded only from this metric's valid-row denominator.

For contaminated conditions, report top-`k` influence precision and recall against the known planted cases, where `k` is the number of planted cases. Report the mean over rows with valid influence output together with both valid-row and scheduled-row counts. Do not include clean rows in these influence metrics. Secondary focal-edge estimation error and influence-rank summaries, if reported, are descriptive.

Also report runtime, numerical diagnostics, and workflow outcomes. Keep the following states distinct: unreached, uncertified (including budget exhaustion), stage error, generation error, timeout, and missing or incomplete shard. Retain scheduled-row denominators when accounting for workload and failures. Never replace a missing, invalid, failed, timed-out, or unavailable metric with zero. An incomplete shard or aggregate remains visibly incomplete; available rows may be described with their actual denominators but cannot be presented as a complete matrix.

## Technical acceptance and empirical interpretation

Technical artifact acceptance checks that all `1,620` expected arm rows and `810` paired keys are present; cap pairs have matching data, stream, and digest identities; row metadata matches the fixed focal truth and planted-case conditions; schemas, values, and denominators validate; deterministic fields reproduce under a matched rerun; and all three fixed shards are complete. Errors and incomplete work remain in the accounting. Technical acceptance means the specified artifacts are complete and internally consistent. It does not mean SDNA performed well, that any operating region is adequate, or that a scientific claim has been confirmed.

Interpret empirical results only on this frozen grid and for these prespecified edges, conditions, estimator settings, and replications. Ten replications per cell are limited and estimates may be imprecise. Do not claim a universal cutoff, general recovery performance, whole-network recovery, or validity for other network structures or data types. In particular, results do not establish performance for ordinal, missing, longitudinal, dependent, or causal data. No outcome or technical acceptance promotes cap 4, changes the production cap, certification budget, estimator settings, or v0.1 defaults; those require a separate review of accepted evidence.

This v1 page contains the protocol only. Hosted results, execution provenance, deviations, and artifact checksums belong in a separate v2 evidence report and an appended decision-log addendum after hosted artifacts have been validated.
