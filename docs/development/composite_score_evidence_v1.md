# Composite-score study evidence v1

Protocol: [`composite_score_study_v1.md`](../methodology/composite_score_study_v1.md)
(frozen before the run, including Amendment 1 on the true-edge definition).
Runner: `tools/run_composite_study.py` at commit `5fd2c59` on branch
`codex/viability-checks`; Python 3.14.3, NumPy 2.3.5; 1,500 datasets
(3 N x 5 conditions x 2 contamination levels x 50 replications), 3 minutes
locally, no workflow errors in any row. Raw rows are regenerable with
`python tools/run_composite_study.py <dir>` and are not committed. Every cell
has 50 clean and 50 careless-respondent rows.

Setting recap: p = 6 composites of 5 items each, latent partial correlations
about +/-0.29 (composite-level truth about 0.17-0.24 on the six designed edges),
focal edge (0, 1), frozen production workflow (cap 2, budget 1,000, 25
calibration sims, 100 bootstrap draws). "Careless" = 3 respondents replaced by
all-top-category straight-liners (all items 5; continuous control: all items 2.0).

## 1. Edge recovery on clean composites (the base layer)

Means over 50 datasets per cell; chance is 0.5 for sign and edge AUC.

| Condition | N | Sign agreement | Edge AUC | Top-k precision | Magnitude ratio | Matched AUC diff vs control |
|---|--:|--:|--:|--:|--:|--:|
| continuous_control | 50 / 100 / 150 | 0.98 / 0.99 / 1.00 | 0.84 / 0.91 / 0.97 | 0.72 / 0.79 / 0.91 | 0.58 / 0.70 / 0.77 | (reference) |
| symmetric | 50 / 100 / 150 | 0.97 / 0.98 / 1.00 | 0.83 / 0.90 / 0.96 | 0.70 / 0.79 / 0.89 | 0.57 / 0.69 / 0.76 | -0.012 / -0.018 / -0.009 |
| moderate_ceiling | 50 / 100 / 150 | 0.97 / 0.98 / 0.99 | 0.78 / 0.88 / 0.94 | 0.68 / 0.79 / 0.87 | 0.55 / 0.66 / 0.74 | -0.057 / -0.031 / -0.029 |
| moderate_heterogeneous | 50 / 100 / 150 | 0.97 / 0.98 / 0.99 | 0.78 / 0.89 / 0.94 | 0.67 / 0.79 / 0.89 | 0.55 / 0.68 / 0.74 | -0.055 / -0.024 / -0.024 |
| severe_ceiling | 50 / 100 / 150 | 0.92 / 0.97 / 0.98 | 0.73 / 0.84 / 0.91 | 0.64 / 0.73 / 0.81 | 0.48 / 0.58 / 0.68 | -0.109 / -0.076 / -0.057 |

**Reading:** with composites, SDNA's estimator still recovers edge direction
(sign agreement at least 0.92 everywhere, at least 0.97 for symmetric to
moderate ceiling) and ranks designed edges above non-edges well above chance.
Ceiling skew costs accuracy in proportion to its severity: moderate ceiling
lowers edge AUC by roughly 0.03-0.06, severe ceiling by 0.06-0.11, relative
to the matched continuous control. Edge AUC at N=50 under severe ceiling is
0.73, usable as a hint but weak; at N=150 it is 0.91. Magnitudes are
attenuated to roughly half to three-quarters of composite-level truth.
Heterogeneous thresholds behaved like the matching homogeneous condition.

Robustness to the 3 straight-liners (careless datasets): sign agreement
0.85-1.00 and edge AUC 0.62-0.95, similar to or slightly below clean; the
estimator is not wrecked by 3 top-category straight-liners, though N=50
symmetric/control fall to AUC about 0.62-0.64.

## 2. Fragility availability and the tail flag

For the focal true edge, counts of 50 clean rows:

- Reached (50% attenuation within 2 deletions) ranged 1-27 and fell with N
  in every condition (control 22 -> 12 -> 1; severe ceiling 27 -> 25 -> 14).
  Reached rows were all certified. Reach here reflects how fragile a *genuine*
  edge is at small N; it is not a contamination detector.
- Every reached row had a right-censored reference tail (some calibration
  references did not reach), i.e. finite tails come from the censored-tail
  rule, not from fully observed reference distributions.
- Clean tail flags (tail probability at or below 0.05): zero in 14 of 15
  cells; the only flags were 2 of 14 finite tails (severe ceiling, N=150). No
  evidence of inflated false flags, with the caveat that denominators are small
  (1-27 finite tails per cell) and this is not a validated type-I error rate.
- The same flag does not detect the planted respondents either: among careless
  datasets only 1 of 29 (severe, N=50) and 2 of 11 (severe, N=150) flagged
  and none elsewhere. The tail flag has little demonstrated power in this design.

## 3. Detecting the planted straight-liners (top-3 exact-LOO recall)

| Condition | N=50 | N=100 | N=150 | Chance (3/N) |
|---|--:|--:|--:|--:|
| continuous_control | 0.08 | 0.48 | 0.79 | 0.06 / 0.03 / 0.02 |
| symmetric | 0.07 | 0.51 | 0.82 | same |
| moderate_ceiling | 0.01 | 0.03 | 0.00 | same |
| moderate_heterogeneous | 0.02 | 0.03 | 0.00 | same |
| severe_ceiling | 0.01 | 0.00 | 0.00 | same |

**Finding (negative):** under moderate or severe ceiling skew, SDNA's exact
case-influence on the focal edge does **not** find all-top-category
straight-liners; recall is at or *below* chance. This is mechanistic rather than
a bug: when much of the sample already sits near the top category, an all-5
respondent is a typical response vector, not a high-leverage point for one
partial correlation. Where the pattern is genuinely extreme (control and
symmetric), recall rises with N (0.07-0.08 at N=50, about 0.5 at N=100, about 0.8
at N=150), so even there N=50 detection is at chance.

## Limits of this evidence

- One contamination type (straight-lining at the top category) was planted. It
  is not the only or most probable careless pattern, and it is a poor test of
  influence detection under ceiling skew for the mechanistic reason above. The
  null result does not show SDNA cannot detect other influential respondents
  (for example a respondent extremely low on the focal pair).
- One network (p = 6 ring, edges about 0.2), one reliability level, one set of
  cutpoints, 50 replications per cell. Cell estimates are diagnostic, not precise.
- Truth is the composite-level network from 1,000,000 simulated draws, not the
  latent network and not a real-data target. No reverse-worded items,
  acquiescence style, missing data, or ordinal estimator was studied.

## Verdict for the stated use case

Supported as descriptive evidence: for composite scores with moderate ceiling
skew, the estimated network is directionally informative at N=50-150
(signs right in at least 97% of designed-edge comparisons and edge AUC 0.78-0.94),
only modestly worse than continuous data. Severe ceiling skew at N=50 is
marginal (AUC 0.73). Not supported: using SDNA's case-influence or fragility
flag to find careless/straight-lining respondents in ceiling-skewed composites,
or reading reach as a contamination signal.
