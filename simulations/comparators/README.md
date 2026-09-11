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

Install these exact versions in an `renv` project and commit the generated
`renv.lock` file before running a publication comparison. Each script checks
the installed versions and fails rather than silently using a different API.

## Inputs and outputs

Both scripts accept a numeric CSV data matrix and write a CSV result. The
intended neutral edge schema is row-oriented and includes:

```text
method,analysis_type,edge,node_i,node_j,estimate,lower,upper,statistic,prior
```

Additional comparator-specific columns are permitted. Python summarization
should treat missing interval/statistic fields as unavailable, not as zero.

## Estimands and workflow distinctions

`ebicglasso.R` estimates an EBICglasso network through `bootnet`. If a positive
bootstrap count is supplied, it writes two separate RDS artifacts:

1. `type="nonparametric"`: nonparametric edge-bootstrap uncertainty;
2. `type="case"`: case-dropping centrality stability.

The second is not an edge bootstrap and must not be reported as one.

`bggm.R` reports posterior edge summaries from a continuous BGGM model and
includes iteration count, seed, and prior description in its output. Posterior
summaries are not frequentist confidence intervals and must remain labeled as
such.

Before making claims about comparator behavior, run these scripts against the
same versioned datasets and settings as the Python methods, retain `sessionInfo()`
and `renv.lock`, and consume only the neutral CSV outputs in downstream code.
