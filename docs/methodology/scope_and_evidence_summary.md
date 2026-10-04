# Scope and evidence summary (plain-language)

Snapshot of what the checked-in simulation evidence does and does not support,
as of 2026-10-03 (updated after composite v2 and Task 27 evidence). Sources: `docs/development/falsification_pilot_evidence_v2.md`,
`edge_recovery_evidence_v1.md`, `composite_score_evidence_v1.md`, and the
frozen study protocols in `docs/methodology/`. All evidence is simulated, small
(10-50 replications per cell), and descriptive.

## What SDNA is for

A localized diagnostic for **preselected edges** of a shrinkage partial-
correlation network: how sensitive is this edge to removing a few respondents?
It is not whole-network discovery, causal inference, or an ordinal/latent-
variable method.

## What the evidence supports

1. **The base network estimate keeps direction and rank at N=50-150.** In a
   moderate-edge continuous network, signs were right in 98-100% of true-edge
   comparisons and edge-versus-non-edge AUC was 0.87-0.99. Estimates are
   attenuated (about 45-90% of true size), so read them as ordered and
   directional, not as calibrated effect sizes.
2. **Likert composites with ceiling skew still work for direction.** With
   five-item composites, signs were right in at least 97% of comparisons and
   edge AUC was 0.78-0.94 under moderate ceiling skew, at most about 0.06
   below a matched continuous control. Severe ceiling skew at N=50 is marginal
   (edge AUC 0.73).
3. **Respondents extreme on the focal pair are found by exact leave-one-out
   influence** well above chance: top-1 recall about 0.57 in the v0.1 pilot and
   0.74-0.81 (single) / 0.66-0.83 (three) in Task 27; in skewed composites,
   three respondents extreme and discordant on the focal pair were recovered
   at 0.64-1.00 even under severe skew (chance 0.02-0.06).
4. **The clean-data tail flag rarely fires** (1/44 in the v0.1 pilot; 2 flags in
   222 finite clean tails in the composite study). This is a descriptive
   rate, not a validated type-I error.

5. **Small-sample dense estimate versus EBICglasso-style selection.** Against a
   Python approximation of EBICglasso (not validated against `qgraph`), SDNA's
   dense estimate ranked true edges clearly better in 76 of 84 cells and was
   never clearly worse; EBIC-py returned an empty network in 91-96% of
   Gaussian datasets at N=30-50 and still 14-52% at N=300 for weak or skewed
   cases (`estimator_comparison_evidence_v1.md`).

## What the evidence does not support

1. **Reach is not a contamination detector.** A 50% attenuation within two
   deletions is reached by about half of clean datasets in the v0.1 pilot, and
   by 1-27 of 50 clean composite datasets depending on N. It measures how
   fragile an edge is at that sample size.
2. **Subgroup structure is not found by case influence.** In the mixture-
   subgroup scenario, top-k recall was 0.151 against a subgroup fraction of
   about 0.15, which is chance. A subgroup with a different covariance is not a
   few outlying points, so single-case leave-one-out is the wrong tool.
3. **Careless responding is not reliably found by case influence.** In the
   composite studies, all-top-category straight-liners were not found under
   ceiling skew (recall at or near 0, because an all-5 response is typical when
   many answer near 5) and were found only weakly without skew (0.19-0.39 at
   N=100-150, nearly invisible at 12 composites). Random responders were found
   only under ceiling skew (0.10-0.34) and not in unskewed data. Detectability
   depends on how a pattern differs from the sample's typical response.
4. **Fragility flags have little demonstrated power.** The reference-tail flag
   fired in 0 of 927 finite tails for respondents extreme on the focal pair, and
   in about 2% of tails for straight-liners and random responders (size about
   1% under no contamination).
5. **Heavy-tailed and highly collinear data** mostly yield no finite fragility
   result under the frozen cap (heavy tails 19/90, collinearity 0/90 reached).
   That is a boundary of the method, not a clean result.
6. **Raw ordinal items, missing data, dependent observations, other `p` or
   item counts, reverse-worded items and response styles are untested.**
7. **A better estimator than other dense methods.** Ranking edges by the
   graphical-lasso path matches SDNA within about 0.01 edge AUC, and SDNA beats
   the unshrunk partial correlation by only 0.01-0.04. The gap to EBICglasso is
   due to its conservative edge selection, not to a more accurate dense estimate.
   Not tested: `p >= N - 1`, `qgraph`/BGGM, and other selection rules.

## Practical reading for a low-N survey network

Use the network estimate as a directional, rank-ordered hint about which
linkages may exist, bearing in mind attenuation. Use leave-one-out influence
to look for a few individually extreme respondents on an edge you care about,
not to screen for careless responding or subgroups. Treat the fragility
tail flag as a weak, conservative signal. Validate any specific survey design
(items per composite, skew, N) with a simulation matched to it before leaning
on these diagnostics.

## Open items

- Task 27 hosted reproducibility mismatch at `p = 20` (see the handoff).
- Composite study v2 (other contamination types, weaker edges, `p` = 12) is
  done; reverse-worded items, acquiescence, other loadings or item counts, and
  real survey data remain untested.
- Task 27 hosted evidence is recorded (ADR-030); the p=20 mismatch was resolved
  by pinning the OpenBLAS kernel (ADR-029).
