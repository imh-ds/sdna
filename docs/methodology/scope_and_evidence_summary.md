# Scope and evidence summary (plain-language)

Snapshot of what the checked-in simulation evidence does and does not support,
as of 2026-10-03. Sources: `docs/development/falsification_pilot_evidence_v2.md`,
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
3. **A single respondent shifted on the focal pair is found by exact leave-one-
   out influence** well above chance (top-1 recall about 0.57 in the v0.1
   pilot, chance about 1-2%), and a shifted trio about 0.69.
4. **The clean-data tail flag rarely fires** (1/44 in the v0.1 pilot; 2 flags in
   222 finite clean tails in the composite study). This is a descriptive
   rate, not a validated type-I error.

## What the evidence does not support

1. **Reach is not a contamination detector.** A 50% attenuation within two
   deletions is reached by about half of clean datasets in the v0.1 pilot, and
   by 1-27 of 50 clean composite datasets depending on N. It measures how
   fragile an edge is at that sample size.
2. **Subgroup structure is not found by case influence.** In the mixture-
   subgroup scenario, top-k recall was 0.151 against a subgroup fraction of
   about 0.15, which is chance. A subgroup with a different covariance is not a
   few outlying points, so single-case leave-one-out is the wrong tool.
3. **Top-category straight-liners are not found in ceiling-skewed composites.**
   Recall was at or below chance under moderate and severe ceiling skew,
   because an all-5 response vector is typical when many respondents answer
   near 5. Only one contamination type was tested.
4. **Fragility flags have little demonstrated power.** In the composite study
   the tail flag fired in 3 of 122 contaminated finite tails.
5. **Heavy-tailed and highly collinear data** mostly yield no finite fragility
   result under the frozen cap (heavy tails 19/90, collinearity 0/90 reached).
   That is a boundary of the method, not a clean result.
6. **Raw ordinal items, missing data, dependent observations, other `p` or
   item counts, reverse-worded items and response styles are untested.**

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
- A composite study v2 with other contamination types (for example a
  respondent extreme on the focal pair), weaker edges, larger `p`, and
  reverse-worded items would test the influence-detection claims more fairly.
