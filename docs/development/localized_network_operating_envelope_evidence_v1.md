# Task 27 localized-network operating-envelope evidence v1

Protocols: [`localized_network_operating_envelope_v1.md`](../methodology/localized_network_operating_envelope_v1.md)
(frozen design) and [`..._v2.md`](../methodology/localized_network_operating_envelope_v2.md)
(acceptance procedure). Nothing in either protocol was changed. Reasoning for the
environment pin that made acceptance possible is in
[`task27_p20_reproducibility_diagnosis.md`](task27_p20_reproducibility_diagnosis.md)
and ADR-029.

## 1. Provenance and technical acceptance

| Item | Value |
|---|---|
| Commit (both runs) | `b6b70d49452bd5e3fa5fb9eb9e1be7e61117fe14` (includes `OPENBLAS_CORETYPE: Haswell`) |
| Workflow | `.github/workflows/localized-network.yml`, `workflow_dispatch`, `ref=refs/heads/main` |
| Baseline run | `37148609781`: three shards and aggregate succeeded; intermediate `awaiting_matched_rerun` |
| Matched-rerun run | `37149291740`: three shards and aggregate succeeded; final gate evaluated here |
| Environment | Python 3.11.16, NumPy 2.4.6, package `0.1.0a0` |
| Manifest checksum | `f163ce9e528de59312abe785a5dda984ba8ee4f3c1c124c853bc78a76001bf48` |
| Summary artifact | `localized-network-aggregate-37149291740`, `summary.json` sha256 `cc012a6434c40ebef1c625fd1a5ffa82cd8045897b7b0c19c17ea8cd39f9dc0c` |
| Acceptance | `acceptance_status = complete`; 1,620 / 1,620 rows valid and available; 810 / 810 pairing keys; 0 missing or duplicate arm pairs; 0 shard issues; all 3 shards `complete` |
| Matched rerun | `status = matched`; 1,620 rows compared; `mismatch_count = 0`; `elapsed_seconds` excluded per the v2 contract |
| Workflow outcomes | 1,328 `ok`, 292 `partial` (unreached fragility search); 0 `error` rows |

Note on labels: in the summary JSON the field `primary_run_id` is `37149291740`
and `rerun_run_id` is `37148609781`, i.e. the run that evaluated the gate is
labeled "primary". The baseline run is the earlier one (`37148609781`).

Shard `results.csv` sha256 (each equals the `files.results.csv` hash in its
own `results.metadata.json`):

| Shard | Baseline `37148609781` | Matched `37149291740` |
|---|---|---|
| p=20 | `a8c5145ee907ed3095a98a4ffdbd53985a64b97eec79191bb83d93e6935ec6c5` | `5728c83d5d96255aabe2e4e6dbd6431c16e5dbb625c08cf8fddea23a5482588a` |
| p=40 | `e071440fed09ee965d1a73835216a22f27b250786009d521aac5a91c3c28e360` | `bb74cecb8d058a7e6dc6120fc5e14f4c10fea393c3fa430a445303d484f1d4ce` |
| p=60 | `7e10ed42324d443cca2dbffebd4a19d0a1315acb561569d77f7c6cab36043f85` | `7bc700ef558c60b095b7e08e40c342b1de4b8a281fecf0d688b311233ea95968` |

The file hashes differ between runs only because `elapsed_seconds` is
recorded per row; all deterministic fields match. Shard wall time: p=20
152-153 s, p=40 149-154 s, p=60 549-601 s (limit 3,600 s). Mean per-row time
rose with `p` and `N` (0.13 s at N=50, p=20 up to 1.05 s at N=150, p=60).

Superseded runs `37070756141`, `37072478469` (invalid artifact downloader),
`37074098652` and `37075156838` (matched-rerun mismatch on `p=20`) and the
cancelled `37148484842` (dispatched before the pin was on `main`) are **not**
evidence and are not used below.

Technical acceptance means the specified artifacts are complete, internally
consistent, and reproduce under a matched rerun. It is not a statement that
SDNA performed well.

## 2. How to read the numbers

- **Row-level counts are not independent.** The three focal contexts share one
  clean draw and planted-case indices per `(N, p, condition, replication)`, and
  the two arms share the dataset. Any pooled proportion below effectively rests
  on about one third as many datasets as rows (for example 90 datasets per
  condition within one arm, not 270). Wilson intervals in `summary.json` are
  row-level and optimistic when pooled. Cell level (`N x p x context x
  condition x arm`) has 10 rows each; intervals there are wide.
- **The focal edge is nearly null.** The population partial correlation is 0.05
  and the estimator shrank heavily: mean lambda 0.92-0.98 across `N x p`, and
  mean condition number 1.06-1.18 (max 1.77), i.e. the shrunk correlation matrix
  is close to the identity. The relative 50% attenuation target is applied to
  a very small estimate.
- Baseline cap 2 is the primary workflow; cap 4 is diagnostic only. No result
  here promotes cap 4, a budget, or a default.

## 3. Results (pooled; point estimates; numerator / denominator in rows)

### 3.1 Fragility reach and certification by arm and condition

| Arm | Condition | Reached | Certified yield | Certified given reach | Budget exhausted given reach |
|---|---|--:|--:|--:|--:|
| baseline cap 2 | clean | 188/270 = 0.70 | 188/270 = 0.70 | 188/188 | 0/188 |
| baseline cap 2 | single_case | 223/270 = 0.83 | 223/270 = 0.83 | 223/223 | 0/223 |
| baseline cap 2 | coalition | 190/270 = 0.70 | 190/270 = 0.70 | 190/190 | 0/190 |
| diagnostic cap 4 | clean | 221/270 = 0.82 | 188/270 = 0.70 | 188/221 = 0.85 | 33/221 = 0.15 |
| diagnostic cap 4 | single_case | 241/270 = 0.89 | 223/270 = 0.83 | 223/241 = 0.93 | 18/241 = 0.07 |
| diagnostic cap 4 | coalition | 265/270 = 0.98 | 190/270 = 0.70 | 190/265 = 0.72 | 75/265 = 0.28 |

- **Reach does not separate clean from contaminated at cap 2**: clean 0.70,
  coalition 0.70, single case 0.83. Reach here mostly reflects how easily a
  50% relative attenuation of a near-null estimate is met, not contamination.
- **Cap 4 adds reach but no certified rows.** Certified counts are identical
  at both caps (188, 223, 190). All 126 certification-budget exhaustions in the
  matrix (33 + 18 + 75) are cap-4 rows reached beyond what the 1,000-combination
  budget could certify. This repeats the Task 24-26 pattern in a different
  design and does not support promoting cap 4 under the current budget.
- Fragility-stage errors: 0. Certification errors: 0. Unreached rows: 292 in
  total (209 at cap 2, 83 at cap 4); these are kept in every denominator and
  are `partial` workflow outcomes, not failures.

### 3.2 Clean descriptive false-flag rate (reference-tail probability <= 0.05)

0 of 188 valid clean rows at cap 2 and 0 of 221 at cap 4 (zero in every
`N x p` cell; invalid clean reference rows: 0). This is a per-prespecified-edge
descriptive rate, not a validated type-I error, and the protocol does not
define a flag rate for contaminated rows, so this study provides **no
evidence on the flag's power**.

### 3.3 Influence recovery (exact leave-one-out, baseline arm; identical for cap 4)

Top-k precision equals recall here (k equals the number planted). All 90 rows
per cell below were valid (0 influence-stage failures).

| Condition | N=50 | N=100 | N=150 | Chance (k/N) |
|---|--:|--:|--:|---|
| single_case (k=1) | 0.756 | 0.811 | 0.744 | 0.020 / 0.010 / 0.007 |
| coalition (k=3) | 0.656 | 0.752 | 0.833 | 0.060 / 0.030 / 0.020 |

By `p` (20 / 40 / 60): single_case 0.689 / 0.800 / 0.822; coalition 0.689 /
0.800 / 0.752. By context (bridge / hub_adjacent / within_community):
single_case 0.789 / 0.767 / 0.756; coalition 0.741 / 0.741 / 0.759.

In this design, with the planted shift placed on the focal pair, exact
case influence on the focal edge recovered the planted cases far above chance
in every `N`, `p`, and context margin, including the `N=50, p=60` stress cells
where `p > N` and no stage failed. Coalition recall rose with `N`.

### 3.4 Numerical diagnostics (baseline arm, by `N x p`)

| N | p | mean lambda | mean condition number (max) |
|--:|--:|--:|---|
| 50 | 20 / 40 / 60 | 0.934 / 0.960 / 0.962 | 1.18 (1.77) / 1.15 (1.56) / 1.17 (1.56) |
| 100 | 20 / 40 / 60 | 0.924 / 0.960 / 0.969 | 1.14 (1.49) / 1.10 (1.29) / 1.10 (1.28) |
| 150 | 20 / 40 / 60 | 0.929 / 0.946 / 0.977 | 1.11 (1.53) / 1.12 (1.41) / 1.06 (1.23) |

## 4. Interpretation and limits

Supported on this frozen grid, for these prespecified edges:

1. The full workflow runs without stage failure at `p` up to 60, including
   `p > N`, and reproduces bit-for-bit under a matched rerun once the BLAS
   kernel is pinned.
2. Exact leave-one-out influence on a prespecified focal edge finds an
   additive +4 shift planted on that edge's variables (1 or 3 cases) with
   recall 0.66-0.83, versus chance of 0.01-0.06.
3. Higher search caps raise reach but, at the 1,000-combination budget, do not
   raise certified yield.

Not supported:

- That reach or the clean false-flag result detects contamination: reach is
  similar for clean and coalition data, and no flag-rate-on-contaminated
  outcome was specified.
- Anything about edges that are truly strong. The focal truth is 0.05 and the
  estimates are close to null because of heavy shrinkage; the study does not
  measure recovery of a real edge, whole-network structure, or performance for
  ordinal, missing, dependent, or non-Gaussian data.
- Precision beyond 10 datasets per cell. Pooled rates rest on dependent rows
  (Section 2).
- Any change to production cap, budget, estimator settings, or defaults.

Companion evidence for edge direction and rank recovery at low `N` is in
`edge_recovery_evidence_v1.md` and `composite_score_evidence_v1.md`.
