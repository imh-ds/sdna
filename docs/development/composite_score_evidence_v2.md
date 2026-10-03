# Composite-score study evidence v2

Protocol: [`composite_score_study_v2.md`](../methodology/composite_score_study_v2.md)
(frozen before the run; no amendments). v1 evidence is in
`composite_score_evidence_v1.md`. Runner: `tools/run_composite_study_v2.py` at
commit `3a90909` on branch `codex/composite-study-v2`; run locally with
`OPENBLAS_CORETYPE=Haswell`, 8 worker processes, Python 3.14.3, NumPy 2.3.5,
Windows 11, Intel (family 6 model 151) CPU; 3 min 43 s. Raw rows are
regenerable with `python -m tools.run_composite_study_v2 <dir> --workers 8` and
are not committed.

Result accounting: 5,760 of 5,760 scheduled datasets completed (2 `p` x 2
strength x 3 `N` x 4 condition x 4 contamination x 30 replications); 0 workflow
errors; 3,750 `partial` (reach not attained within the cap-2 search) and 2,010
`ok`; 0 cells failed the pre-specified edge rule. Composite-level truth on the
six (p=6) or twelve (p=12) ring pairs was 0.17-0.24 ("strong") and 0.13-0.18
("weak"); non-ring pairs were at most 0.024.

**Dependence caveat.** Every pooled cell below is 120 datasets (2 `p` x 2
strength x 30 replications) at a given condition and `N`. Conditions and
contamination types are matched on the same underlying draws, so rows across
them are not independent, and no intervals are reported.

## 1. Edge recovery on clean composites (contamination `none`)

Means over 120 datasets per cell. Chance is 0.5 for sign agreement and edge AUC.

| Condition | N | Sign agreement | Edge AUC | Top-k precision | Magnitude ratio |
|---|--:|--:|--:|--:|--:|
| continuous_control | 50 / 100 / 150 | 0.88 / 0.96 / 0.99 | 0.76 / 0.85 / 0.93 | 0.58 / 0.68 / 0.79 | 0.40 / 0.52 / 0.68 |
| symmetric | 50 / 100 / 150 | 0.87 / 0.96 / 1.00 | 0.75 / 0.84 / 0.93 | 0.55 / 0.67 / 0.79 | 0.40 / 0.51 / 0.67 |
| moderate_ceiling | 50 / 100 / 150 | 0.82 / 0.94 / 0.99 | 0.71 / 0.82 / 0.91 | 0.53 / 0.65 / 0.77 | 0.37 / 0.49 / 0.64 |
| severe_ceiling | 50 / 100 / 150 | 0.77 / 0.90 / 0.98 | 0.67 / 0.76 / 0.87 | 0.47 / 0.57 / 0.69 | 0.31 / 0.44 / 0.56 |

Matched edge-AUC difference from `continuous_control` (same draws), pooled over
`p` and strength, at N = 50 / 100 / 150: symmetric -0.010 / -0.009 / -0.005;
moderate -0.048 / -0.030 / -0.021; severe -0.092 / -0.085 / -0.060.

Edge AUC by `p` and strength (pooled over `N`), control / symmetric / moderate /
severe: p=6 strong 0.89 / 0.88 / 0.86 / 0.82; p=6 weak 0.79 / 0.79 / 0.74 / 0.69;
p=12 strong 0.91 / 0.90 / 0.88 / 0.83; p=12 weak 0.79 / 0.78 / 0.75 / 0.72.
Weak edges at N = 50 are marginal: edge AUC 0.69 (control) and 0.60-0.64
(severe) at either `p`.

**Reading:** direction and rank are recovered above chance everywhere, and
improve with `N`. Ceiling skew costs accuracy in proportion to severity
(symmetric about 0.01, moderate 0.02-0.05, severe 0.06-0.09 edge AUC).
Weak edges at low `N` under heavy skew are only weakly separated from non-edges.
Magnitudes are attenuated to 0.31-0.68 of composite-level truth.

Robustness of edge recovery to the 3 contaminated respondents (edge AUC /
sign agreement, pooled; control, symmetric, moderate, severe):

| Contamination | control | symmetric | moderate | severe |
|---|---|---|---|---|
| none | 0.84 / 0.95 | 0.84 / 0.94 | 0.81 / 0.91 | 0.77 / 0.88 |
| straight_top | 0.72 / 0.90 | 0.70 / 0.89 | 0.79 / 0.93 | 0.76 / 0.89 |
| focal_discordant | 0.80 / 0.88 | 0.79 / 0.86 | 0.76 / 0.85 | 0.71 / 0.80 |
| random_responder | 0.83 / 0.94 | 0.82 / 0.93 | 0.79 / 0.92 | 0.63 / 0.82 |

Focal-discordant respondents lower sign agreement (down to 0.80 under severe
skew); random responders hurt mainly under severe skew (edge AUC 0.63);
straight-liners hurt mainly without skew.

## 2. Detecting the 3 contaminated respondents (top-3 exact-LOO recall, focal edge)

Pooled over `p` and strength; n = 120 per cell. Chance (3/N) = 0.060 / 0.030 /
0.020 at N = 50 / 100 / 150.

| Contamination | Condition | N=50 | N=100 | N=150 |
|---|---|--:|--:|--:|
| focal_discordant | continuous_control | 0.85 | 0.95 | 0.98 |
| | symmetric | 0.86 | 0.96 | 1.00 |
| | moderate_ceiling | 0.71 | 0.84 | 0.84 |
| | severe_ceiling | 0.64 | 0.69 | 0.74 |
| straight_top | continuous_control | 0.05 | 0.19 | 0.39 |
| | symmetric | 0.03 | 0.21 | 0.39 |
| | moderate_ceiling | 0.02 | 0.00 | 0.01 |
| | severe_ceiling | 0.00 | 0.00 | 0.00 |
| random_responder | continuous_control | 0.01 | 0.01 | 0.00 |
| | symmetric | 0.03 | 0.02 | 0.02 |
| | moderate_ceiling | 0.12 | 0.13 | 0.10 |
| | severe_ceiling | 0.20 | 0.26 | 0.34 |

**Findings:**

1. **Respondents extreme on the focal pair are found at every skew level**,
   far above chance: recall 0.64-1.00, lowest (0.64-0.74) under severe skew. Edge
   strength and `p` mattered little (control 0.88-0.96, ordinal 0.78-0.86 across
   p x strength).
2. **All-top straight-liners are found only without skew and only at larger
   `N`** (0.19-0.39 at N = 100-150, at chance at N = 50), and not at all under
   moderate or severe skew. They are nearly invisible at `p = 12` even in the
   control (0.03-0.04 versus 0.33-0.43 at `p = 6`), because a response shifted on
   all composites at once moves a single edge little.
3. **Random responders are found only under ceiling skew.** In symmetric or
   continuous data recall is at or below chance (0.00-0.03; random responders
   are not influential for an edge when the sample is centered). Under moderate
   and severe skew recall rises to 0.10-0.34, well above chance, because random
   answers then deviate strongly from the top-heavy typical response.
4. The detectability of a contamination pattern depends on how it differs from
   the sample's typical response, not just on how odd it looks in isolation.

## 3. Fragility reach and the tail flag

Pooled; all conditions' rows are counted.

| Contamination | Reach (control / symmetric / moderate / severe) | Flagged / finite tails (same order) |
|---|---|---|
| none | 0.22 / 0.21 / 0.33 / 0.52 | 0/80, 0/77, 0/117, 5/186 |
| straight_top | 0.06 / 0.07 / 0.16 / 0.47 | 0/21, 0/25, 1/59, 5/171 |
| focal_discordant | 0.66 / 0.63 / 0.59 / 0.69 | 0/237, 0/228, 0/212, 0/250 |
| random_responder | 0.25 / 0.26 / 0.21 / 0.24 | 0/90, 0/94, 0/75, 6/88 |

(Each reach figure is reached rows / 360.) Size (contamination `none`): 5 of
460 finite tails flagged (1.1%), all under severe skew. Power: focal_discordant 0
of 927 finite tails, straight_top 6 of 276 (2.2%), random_responder 6 of 347
(1.7%).

**Findings:** the reference-tail flag has essentially no demonstrated power in
this design, including for focal-discordant respondents that influence analysis
finds easily. Reach is not a general contamination signal: it is raised
(0.59-0.69 versus 0.21-0.52) by focal-discordant respondents, lowered by
straight-liners without skew, and unchanged by random responders. Why the flag
stays silent when reach differs is not tested here; one untested possibility is
that calibration references are built from the observed correlation matrix,
which already contains the damage.

## 4. Verdict for the stated use case

For skewed five-item composites at N = 50-150:

- **Supported (descriptive):** the estimated network is directionally
  informative, with the loss from ceiling skew smaller than the loss from small
  `N` or weak edges. Edge AUC at N = 50 with weak edges is marginal (0.6-0.7).
- **Supported (descriptive):** exact case-influence on a prespecified focal edge
  finds respondents who are extreme on that edge's pair (recall 0.64-1.00),
  even under severe skew. Under skew it also finds random responders at a modest
  rate (0.10-0.34).
- **Not supported:** using exact influence to find all-top straight-liners in
  skewed data, or random responders in unskewed data.
- **Not supported:** using the reference-tail flag as a detector; it did not fire
  for any discordant respondents.

## Limits

One loading, one item count, one network family (ring), three contamination
types of exactly three respondents, 30 replications per cell (120 per pooled
cell), local runs on a single machine. Composite-level truth; not the latent
network, reverse-worded items, acquiescence, missing data, or real survey data.
No production default or frozen protocol changed.
