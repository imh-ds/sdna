# SDNA Methodology Supplement: Specifications, Fixes, and a Working Core

Companion to *Structured Deletion and Case-Influence Analysis for Small-Sample
Conditional Association Networks*. This document proposes concrete
replacements for the parts of the revision that were left open, and reports
numerical verification for each. A tested reference implementation accompanies
it (`sdna.py`).

The framing assumption is yours: the algorithmic pieces need not be new. The
contribution is a question the behavioral-science toolkit currently cannot
answer, packaged so that applied researchers will actually use it. Everything
below is aimed at that.

---

## 0. The central architectural change

The current draft makes random balanced deletion the engine and case influence
an output derived from it. I think that is backwards, for a reason that is
arithmetic rather than stylistic.

With *N* = 100 and 10% deletion, the chance that a specific coalition of three
influential cases is deleted together is about 0.0007. At 30% it is about
0.025. Under the nonparametric bootstrap the chance that all three are absent
from a resample is about 0.049. Random deletion is therefore *less* likely than
the bootstrap to produce a replicate free of a coalition, and bootstrap
resamples additionally duplicate outliers, widening intervals further.

This was confirmed in simulation. In a planted design (*N* = 100, *p* = 8,
three outliers manufacturing an edge between two independent variables), the
standard deviation across 10% deletion replicates was **2.7× smaller** than the
bootstrap standard deviation. Any statistic built on the marginal deletion
distribution — scaled dispersion, quantile sensitivity, sign stability — will
lose a head-to-head against bootnet on contamination sensitivity.

The fix is not a better deletion fraction. It is to stop using random deletion
to *find* influential cases, and compute influence directly.

**Proposed architecture:**

| Layer | Role | Replaces |
|---|---|---|
| Closed-form influence | find case-edge dependence exactly, in one pass | random deletion as the discovery engine |
| Greedy coalition search | find the worst *m*-case subset, defeating masking | hoping a random fold contains the coalition |
| Exact refit verification | confirm the approximation | — |
| Clean-reference simulation | calibrate every statistic against a matched honest edge | the unresolved null-construction problem |
| Structured deletion | retained for dispersion and block/temporal designs | remains, but demoted |

Deletion keeps a real job (Section 6), but it is no longer load-bearing.

---

## 1. The closed-form influence function

For this estimator the per-case influence on every edge is available
analytically. Standardize once, let `Z` be the standardized data, `R` the
correlation matrix, `λ` the shrinkage intensity, `Ω = ((1-λ)R + λI)^{-1}`, and
`ρ_ij = -Ω_ij / sqrt(Ω_ii Ω_jj)`.

**Step 1. Influence on the Pearson correlation** (classical result):

```
dR^(k)_ij = z_ki z_kj − (R_ij / 2)(z_ki² + z_kj²)
```

Note this is automatically zero on the diagonal, so the perturbed matrix stays
a valid correlation matrix to first order.

**Step 2. Through the shrinkage step and the inverse.** With `λ` held fixed,
`dR̂ = (1−λ) dR`, and the derivative of a matrix inverse gives:

```
dΩ^(k) = −(1−λ) · Ω dR^(k) Ω
```

**Step 3. Through the partial-correlation transform.** Differentiating
`ρ_ij = −Ω_ij (Ω_ii Ω_jj)^{−1/2}`:

```
dρ_ij = −dΩ_ij / sqrt(Ω_ii Ω_jj) − (ρ_ij / 2)(dΩ_ii/Ω_ii + dΩ_jj/Ω_jj)
```

**Step 4. Convert to a deletion effect.** `ψ_k,ij = −dρ_ij / (N−1)` approximates
the change in `ρ_ij` from removing case *k*.

This produces the full **N × p × p influence tensor** in O(N p³), which for
*N* = 150 and *p* = 20 is milliseconds. It requires no resampling at all.

### Verification

Checked against exact leave-one-out refits:

| N | p | λ | corr(closed form, exact LOO) | max abs error |
|---|---|---|---|---|
| 60 | 8 | 0.66 | 0.99909 | 0.0083 |
| 100 | 12 | 0.51 | 0.99961 | 0.0042 |
| 150 | 15 | 0.86 | 0.99994 | 0.0005 |

The first-order form slightly understates magnitude (regression slope on exact
LOO ≈ 1.04–1.11, shrinking toward 1 as *N* grows). Rankings are unaffected.
When absolute magnitudes matter, calibrate the scale by regressing ψ on exact
LOO, which costs *N* inversions and takes under a second. The implementation
exposes this as `calibrate_scale=True`.

### What this does for the paper

It converts Section 10 of your draft from "a Monte Carlo quantity whose
precision depends on the number of partitions" into an exact derivative with a
closed form. That removes the open design question about how many partitions
are needed for `I_{k,ij}`, removes Monte Carlo error from the headline output,
and gives a reviewer something to check by hand.

---

## 2. The Network Fragility Index

This is the statistic I would build the paper around. It replaces sign
stability, which I would cut.

> **NFI(i,j)** = the smallest number of cases whose removal reduces `|ρ̂_ij|`
> to a specified fraction of its full-sample value.

Report it as a count and as a percentage of *N*. Use target = 0.5 (halving) as
the default, with sign reversal and "drop below a substantive threshold"
available as variants when the study has a smallest effect size of interest.

**Why this and not scaled dispersion.** It answers the question a behavioral
scientist actually has, in a sentence they can put in an abstract: *this edge
disappears if you drop 2 of 87 participants*. It has no units problem, no
calibration-free number between 0 and 1 that readers will misread as a
probability, and no dependence on Monte Carlo replication count. bootnet cannot
produce it, and neither can a posterior. It is also the direct network analogue
of the fragility index used in clinical trials, which gives you a familiar
precedent to cite in the framing.

### Computation: greedy with refresh

```
keep ← all cases
repeat:
    fit network on keep (λ fixed at full-sample value)
    if |ρ_ij| ≤ target × |ρ_ij^full|: stop
    compute influence ψ on keep
    remove the case whose deletion most reduces |ρ_ij|
```

Recomputing influence after each removal is what defeats masking. Verified
against brute force over all C(40,3) = 9,880 triples: greedy-with-refresh
recovered the exact optimal coalition; one-shot top-*m* selection picked a
slightly different set but achieved essentially the same effect (ρ after
removal −0.0315 vs −0.0312 for the true optimum). Use refresh; it costs one
inversion per step.

**Always verify by exact refit.** The reported NFI should be the number of
cases that *actually* move the estimate when removed, not the linear
prediction. The implementation does this.

---

## 3. Clean-reference calibration: a concrete answer to the null problem

Your Section 18.4 leaves null construction unresolved, and the IPF-constrained
null I suggested earlier answers the wrong question. The question is not "is
this edge zero" — BGGM and Wald intervals already answer that, better. The
question is **"is this edge more case-dependent than a genuine edge of this
magnitude would be at this sample size?"**

That has a clean reference model: **the fitted network itself.**

```
1. Fit the shrinkage network to the observed data.
2. Take the implied covariance Σ = Ω⁻¹, rescaled to unit diagonal.
3. Simulate n_sim datasets of size N from MVN(0, Σ).
   These contain a genuine edge of the estimated magnitude, no contamination,
   and perfectly exchangeable cases.
4. Compute NFI on each simulated dataset for the same edge.
5. Compare the observed NFI against that distribution.
```

This preserves the full multivariate structure that naive permutation destroys,
requires no constrained fitting, and generalizes to every statistic in the
framework, not just sign behavior. It is the same logic as a parametric
bootstrap, with the estimand being fragility rather than the edge weight.

### Does it work?

Matched on edge magnitude (|ρ| in 0.18–0.32), comparing genuine edges against
edges manufactured by three outliers:

| Design | mean \|ρ\| | NFI median | NFI IQR | AUC |
|---|---|---|---|---|
| N=100, p=8, genuine | 0.218 | 8 | 7–9 | — |
| N=100, p=8, contaminated | 0.215 | 2 | 2–3 | **1.000** |
| N=60, p=6, genuine | 0.218 | 6 | 5–7 | — |
| N=60, p=6, contaminated | 0.243 | 2 | 2–3 | **0.989** |

A cutoff at the clean 5th percentile gave 100% sensitivity and 93–95%
specificity. The edges are matched on observed magnitude, so this is not the
index rediscovering effect size.

For comparison, in the same contaminated design the **bootstrap 95% interval
excluded zero in 69% of replications**. bootnet's default workflow reports the
manufactured edge as a credible finding roughly seven times in ten. That single
comparison is your paper's motivating result.

### One caveat to handle in writing

NFI is a small integer, so the empirical *p*-value is coarse. In the end-to-end
demo the contaminated edge landed at *p* = 0.09 despite NFI = 2 against an
expected 5. Two fixes, use both:

- Report the **ratio** NFI_observed / NFI_expected alongside the *p*-value.
  It is continuous-ish and more informative than a discretized tail
  probability.
- Interpolate by computing NFI across a grid of targets (0.9, 0.8, ..., 0.3)
  and comparing the whole trajectory against the reference band. This is your
  robustness path, rebuilt on a statistic that has a reference.

That trajectory-versus-band plot should be the paper's main figure. It is the
robustness path idea from your original draft, preserved, but now with
something to compare against.

---

## 4. Revised output set

Cut to four per-edge quantities plus one matrix:

| Output | Definition | Role |
|---|---|---|
| `ρ̂_ij` | full-sample shrinkage partial correlation | effect size |
| `NFI_ij` | min cases to halve the edge, verified by refit | headline robustness |
| `NFI_ij / E[NFI \| clean]` | ratio to clean reference | calibrated interpretation |
| `drivers_ij` | the removed cases, named | the substantive payoff |
| `Ψ` | N × p × p influence tensor | heatmaps, case-level summaries |

**Drop:** sign stability and `Z^sign` (degenerate at low deletion fractions,
and NFI at target = 0 with a sign check answers the same question properly);
magnitude retention; per-edge regularization gap `G` (λ is a scalar, so the
adaptive path shifts nearly all edges by a common factor — report λ per
replicate and one global attenuation summary instead).

**Keep but demote:** scaled deletion dispersion and the 95th-percentile
deviation. They are honest uncertainty-adjacent summaries and cost nothing once
you are already refitting, but they should not carry the argument.

---

## 5. Case-level outputs, which are your actual differentiator

The influence tensor supports three summaries that no existing network tool
produces. Give each a named place in the output.

**Case leverage.** `L_k = Σ_ij |ψ_k,ij|` over all edges. Identifies observations
that reshape the whole network. Calibrate against the clean reference the same
way as NFI, and plot as a ranked dotplot with the reference band.

**Influence signatures.** Each row of `Ψ` is a case's fingerprint across edges.
Correlating rows reveals coalitions: several cases with near-identical
signatures are jointly driving the same structure even when no single deletion
reveals it. Cluster the rows and report the clusters. This catches masking
without any search at all, and it is cheap.

**Edge concentration.** For each edge, the share of total absolute influence
held by the top 5% of cases. Bounded, comparable across edges, and calibratable
against the clean reference.

---

## 6. What structured deletion is still for

Three jobs, all real:

1. **Non-exchangeable designs.** Block deletion has no closed-form analogue
   when the blocks are what you care about. Leave-region-out, leave-site-out,
   leave-clinic-out remain refit-based.
2. **Temporal dependence.** See Section 7 — moving-block deletion is
   essential and cannot be replaced by case influence.
3. **Verification.** Every NFI is confirmed by an actual refit. The
   approximation finds candidates; deletion proves them.

What it should no longer be used for is discovering influential individual
cases. Reframing Section 7 of your draft along these lines shortens it and
makes the remaining deletion machinery easier to justify.

---

## 7. Reposition the application: intensive longitudinal data

Country-level comparative data is a defensible motivating example but a thin
market. The large behavioral-science use case sitting in your exact *N* range
is **idiographic ESM, EMA, and daily-diary networks**, where *N* is the number
of measurement occasions for one person — routinely 50 to 150 — and the units
are beeps or days.

This is a better fit than the country case for four reasons:

- The sample size range matches exactly, without special pleading.
- The units are scientifically meaningful. "This rumination–affect edge exists
  because of one bad fortnight" is a clinical finding, not a diagnostic note.
- The field is active, methodologically self-aware, and already worried about
  the exact problem (person-specific networks estimated from short series,
  with no way to ask whether a few occasions drive the result).
- It gives block deletion real work: temporal dependence violates
  exchangeability, so the correct variant is **moving-block or
  contiguous-window deletion**, with an established resampling literature
  behind it.

The closed-form influence carries over directly; what changes is the reference
model in Section 3, which must simulate from a fitted model with the observed
temporal dependence (e.g., a VAR(1) with the estimated innovation covariance)
rather than i.i.d. draws. That is a specific, tractable extension.

I would consider making this the lead application and keeping the country case
as the second example. It roughly triples the addressable audience and it
converts your finite-population section from a caveat into a method.

---

## 8. Practical specifications still missing

**Missing data.** Not currently addressed, and at *N* = 50 it matters. Proposed
policy: multiple imputation (*m* ≈ 20), run the full pipeline within each
imputed dataset, and report NFI as the median across imputations with the range.
Do not pool the influence tensors across imputations — report the proportion of
imputations in which each case appears among the drivers, which is more
interpretable and avoids pretending imputed rows are exchangeable with observed
ones. Flag pairwise deletion as unsafe here, since a non-PSD correlation matrix
breaks the inversion the whole method rests on.

**Operating envelope.** You are right to refuse a universal *N/p* rule, but
shipping with no guidance guarantees misuse. Suggested interim: the software
emits a warning when `p(p+1)/2 > N/2`, and refuses silently-wrong behavior by
reporting the condition number of the shrunk correlation matrix in every
output. Replace with simulation-derived guidance later.

**Ordinal data.** Polychoric correlations break the influence derivation, since
the classical Pearson influence function in Step 1 no longer applies. Two
honest options: restrict version 1 to continuous and nonparanormal-transformed
data, or derive the influence function for the polychoric estimator separately.
I would restrict version 1 and say so.

**Fixed vs adaptive λ.** Keep the distinction, but simplify the reporting.
Fixed λ for everything in the main analysis; report the adaptive-λ trajectory
as a single global attenuation curve in the supplement.

---

## 9. Revised validation plan

Your Section 17 is sound in structure. Three changes.

**Simulation 1 (falsification) should be re-scoped.** The original test asks
whether the robustness statistic is a reparameterized signal-to-noise ratio.
For NFI the answer is partly yes by construction — fragility scales with |ρ|
and *N*, which is why the calibration in Section 3 matches on magnitude. The
sharper test is: *conditional on |ρ̂| and N, does NFI carry information?* Run it
as a partial rank correlation, and report the incremental AUC for contamination
detection over a Wald z alone. The Section 3 result (AUC ≈ 1.0 on
magnitude-matched edges) suggests this passes, but it needs a proper sweep.

**Simulation 2 needs more contamination types.** Currently one design. Add:
single high-leverage case; a coalition of 3–5; a coherent subgroup (10–20% of
the sample with a genuinely different covariance, which is the mixture case and
the most common real scenario); heavy tails with no discrete outliers. The
subgroup case is the one where I would expect NFI to behave differently, since
the "contamination" is 15 cases rather than 3, and it is worth knowing whether
the method degrades gracefully or misleads.

**Add a false-positive study.** Clean data, no contamination, 45 edges. What
fraction of edges get flagged as fragile at the proposed cutoff? The
specificity numbers above (93–95%) imply roughly 2–3 false flags per 45-edge
network, which needs a multiplicity discussion in the paper before a reviewer
raises it.

---

## 10. Deliverables and sequence

The methodological content is close to sufficient. What is missing is
evidence and tooling, in this order:

1. **The re-analysis.** Take a published small-*N* network paper with open data
   and show a reported edge depends on two or three identifiable units. One
   convincing real example will do more than the entire simulation program,
   because it demonstrates a question the field cannot currently ask. Target
   something with meaningful units: a clinical sample, a team-level dataset, or
   a published idiographic ESM network.
2. **The R package.** Adoption in this literature tracks tooling, and bootnet's
   advantage is that it is already installed. Minimum viable surface:
   `sdna(data)` returning the network, the influence tensor, and an edge table;
   `plot()` for the influence heatmap and the fragility trajectory band; and a
   `bootnet`-compatible input path so migration costs nothing. The Python
   reference implementation ports in roughly a day.
3. **The simulation study**, scoped as in Section 9.
4. **The paper**, framed around the 69% number: a standard workflow reports a
   manufactured edge as credible roughly seven times in ten, and here is a
   diagnostic that catches it and names the cases responsible.

---

## Appendix: what the reference implementation does

`sdna.py` implements the pipeline with numpy only.

```python
from sdna import analyze
out = analyze(X, node_names=cols, case_names=ids)
for e in out["edges"]:
    print(e["edge"], e["rho"], e["fragility"], e["p_value"], e["driving_cases"])
```

Demonstration output (N=90, p=6, genuine edges planted at .45 and .40,
plus a fake edge manufactured by 3 outliers):

```
edge           rho  frag   exp      p  drivers
V5--V6      +0.287     2   5.0  0.090  [53, 30]      <- manufactured
V2--V5      -0.126     3   3.0  0.610  [0, 53, 15]
V1--V6      +0.227     5   4.0  0.710  [53, 30, 24, 0, 64]
V1--V3      +0.294    11   6.0  0.990  [29, 35, 54, ...]   <- genuine
V2--V4      +0.287    12   6.0  0.990  [61, 38, 67, ...]   <- genuine
```

The planted contaminants were cases 0, 30, and 53. The fake edge has the
lowest fragility in the network, sits below its clean reference, and names two
of the three culprits directly. The genuine edges of nearly identical magnitude
require 11 and 12 deletions against an expected 6.

Functions: `fit`, `influence`, `fragility`, `calibrate`, `analyze`.
Verification scripts for the tables in Sections 1–3 are in
the `verification/` folder.
