# Task 27 p=20 reproducibility mismatch: diagnosis

Date: 2026-10-03. Scope: why the hosted baseline run `37074098652` and matched
rerun `37075156838` (both on `f48f18a`) disagreed on all 540 `p = 20` rows
while `p = 40` and `p = 60` matched. This diagnosis does not change the frozen
protocol, manifest, or the exact-match acceptance rule.

## Conclusion

The cause is **CPU-dependent BLAS kernel selection**, not a seed-contract bug,
not randomness inside a run, and not the degenerate-spectrum hypothesis in the
earlier handoff. NumPy's wheel ships OpenBLAS with dynamic architecture
dispatch. GitHub-hosted `ubuntu-latest` runners are heterogeneous (AMD EPYC and
Intel Xeon models), so identical seeded code selects different matrix
kernels and produces different floating-point bits. Pinning
`OPENBLAS_CORETYPE=Haswell` makes the generated data bit-identical across all
CPU models observed.

## Evidence

1. **Artifacts confirm the symptom.** Downloaded shard artifacts for both runs:
   `dataset_digest` differs in 540/540 `p = 20` rows and 0/540 `p = 40` rows.
   Both runs recorded the same commit, Python 3.11.16, NumPy 2.4.6, seeds.
2. **Spectrum is not degenerate (hypothesis refuted).** For the population
   covariance, adjacent singular-value gaps were at least 6e-4 (`p = 20`),
   1.6e-4 (`p = 40`), 6.9e-5 (`p = 60`); no repeated values. The SVD basis is
   not arbitrary.
3. **Mechanism reproduced locally.** Forcing different OpenBLAS kernels with
   `OPENBLAS_CORETYPE` on one machine changed the seeded
   `multivariate_normal` output. Singular values and vectors agreed to about
   1e-15, but the **sign of a few singular vectors flipped** (0 of 20 rows at
   `p = 20`, 1-2 of 40/60), and matrix products differed in the last bits.
   Sign flips make materially different (distributionally equivalent) datasets
   (max absolute difference about 3.3 at `p = 40/60`); last-bit differences
   alone give about 1e-12 at `p = 20`. A Cholesky-based generator agreed
   across kernels to about 1e-15 but not to the bit.
4. **Hosted confirmation** (workflow `BLAS reproducibility probe`, run
   `37145105026`, branch `codex/task27-p20-diagnosis`; 10 repeats x 2 modes
   on `ubuntu-latest`, NumPy 2.4.6, OpenBLAS 0.3.31):
   - Runner CPUs seen: AMD EPYC 7763, 9V45, 9V74; Intel Xeon Platinum 8370C;
     Intel Xeon 6973P-C.
   - **Native dispatch:** two distinct output families at *every* `p`.
     EPYC 7763 produced one digest; EPYC 9V45/9V74 and Xeon 8370C produced
     another (SVD data digest, and Cholesky digest too).
   - **`OPENBLAS_CORETYPE=Haswell`:** one digest per `p` across all 10 runs and
     all 4 CPU models seen in that mode, for the SVD path and the Cholesky path.
5. **Why only `p = 20` mismatched.** The kernel families split at every `p`
   (item 4), so `p = 40` and `p = 60` matching was luck: those two shards
   landed on the same CPU family in both runs, while the `p = 20` shards did
   not. Run-to-run CPU assignment of the `p = 20` shards cannot be recovered
   now because the study artifacts do not record the CPU model.

## Change made

`.github/workflows/localized-network.yml` shard job now sets
`OPENBLAS_CORETYPE: Haswell` (job-level env; covers data generation and all
downstream linear algebra). A contract test
(`test_shard_job_pins_the_openblas_kernel_for_cross_runner_reproducibility`)
protects it. No manifest, DGP, runner schema, validator, or acceptance rule
changed. `tools/diagnose_blas_reproducibility.py` and a dispatch-only
`blas-reproducibility-probe.yml` are added for re-verification.

## What this does not establish

- It does not show the original `p = 20` runs landed on different CPUs; that
  is inferred (the hosted fleet splits exactly this way) but unrecorded.
- Pinning Haswell was verified on the data-generation probe, not yet on a full
  study run. Thread-count sensitivity (seen locally at the last-bit level) is
  not pinned; hosted runners have a fixed vCPU count, but this is a residual
  risk.
- Kernel pinning assumes every runner supports AVX2 kernels, true for all CPU
  models seen.

## Required next steps (not done here)

1. Merge the pin. Existing runs `37074098652`/`37075156838` stay failed and
   must not be reused as accepted evidence (ADR-027 rule).
2. Dispatch a fresh baseline and matched rerun of `localized-network.yml` at
   the merged commit. Acceptance still requires exact deterministic-field
   matches.
3. Only if that passes, write the Task 27 evidence report and decision-log
   addendum.
