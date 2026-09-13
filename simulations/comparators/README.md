# R comparator scripts

These scripts are separate from the Python shrinkage-bootstrap comparator and
must not be used to infer what `bootnet` or BGGM would report from Python
results.

## Reproducible environment

The reference pins for this comparator milestone are:

| Package | Version | Role |
|---|---:|---|
| `qgraph` | `1.9.8` | EBICglasso graph implementation |
| `bootnet` | `1.6` | EBICglasso estimation and bootstrap workflows |
| `BGGM` | `2.0.0` | Bayesian Gaussian graphical model |

The committed [`renv.lock`](renv.lock) records the R version and direct
comparator package pins. From this directory, restore the environment before
running a comparison:

```text
Rscript -e "renv::restore(lockfile = 'renv.lock', prompt = FALSE)"
```

The lockfile is intentionally minimal until a networked R environment resolves
the full transitive dependency set; `renv::restore()` should be followed by an
`renv::snapshot()` in that environment if a fully materialized lock is needed.
Each script checks the installed direct package versions and fails rather than
silently using a different API.

## Inputs and outputs

Both scripts accept a numeric CSV data matrix and write a CSV result. The
intended neutral edge schema is row-oriented and includes:

```text
method,analysis_type,edge,node_i,node_j,estimate,lower,upper,statistic,prior,seed
```

Additional comparator-specific columns are permitted. Python summarization
should treat missing interval/statistic fields as unavailable, not as zero.

## Estimands and workflow distinctions

### Python Wald comparator

`wald_partial_correlation` is an intentional ordinary-partial benchmark. It
fits the full data with `fit_network(data)` and therefore lets the estimator
re-estimate its shrinkage value. It does not accept or reuse a fixed lambda
from an SDNA deletion or calibration run. This keeps the comparator aligned
with its ordinary-partial assumption, but means its interval and `z` statistic
must not be described as uncertainty for the fixed-shrinkage SDNA estimand.
Adding fixed-lambda Wald resampling would be a separate comparator design and
would require its own API and validation.

`ebicglasso.R` estimates an EBICglasso network through `bootnet`. If a positive
bootstrap count is supplied, it writes two separate RDS artifacts:

1. `type="nonparametric"`: nonparametric edge-bootstrap uncertainty;
2. `type="case"`: case-dropping centrality stability.

The second is not an edge bootstrap and must not be reported as one.

`bggm.R` reports posterior edge summaries from a continuous BGGM model and
includes iteration count, seed, and prior description in its output. Posterior
summaries are not frequentist confidence intervals and must remain labeled as
such.

Both scripts accept an explicit seed after their optional resampling/iteration
count. The default seed is `20260910`, and the selected seed is written to the
CSV output:

```text
Rscript ebicglasso.R input.csv output.csv 1000 20260910
Rscript bggm.R input.csv output.csv 10000 20260910
```

Before making claims about comparator behavior, run these scripts against the
same versioned datasets and settings as the Python methods, retain `sessionInfo()`
and the restored environment, and consume only the neutral CSV outputs in
downstream code.
