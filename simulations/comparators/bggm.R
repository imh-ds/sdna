#!/usr/bin/env Rscript

# BGGM comparator with explicit prior/model settings.
# Usage: Rscript bggm.R input.csv output.csv [iterations] [seed]

required_version <- "2.0.0"
if (!requireNamespace("BGGM", quietly = TRUE)) {
  stop(sprintf("Install pinned package BGGM==%s before running this comparator", required_version))
}
if (as.character(utils::packageVersion("BGGM")) != required_version) {
  stop(sprintf("BGGM must be version %s (found %s)", required_version, utils::packageVersion("BGGM")))
}

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2L) stop("Usage: Rscript bggm.R input.csv output.csv [iterations] [seed]")
input_path <- args[[1L]]
output_path <- args[[2L]]
iterations <- if (length(args) >= 3L) as.integer(args[[3L]]) else 10000L
seed <- if (length(args) >= 4L) as.integer(args[[4L]]) else 20260910L
if (is.na(iterations) || iterations < 1L) stop("iterations must be a positive integer")
if (is.na(seed)) stop("seed must be an integer")
data <- utils::read.csv(input_path, check.names = FALSE)
if (ncol(data) < 2L || any(!vapply(data, is.numeric, logical(1)))) {
  stop("input.csv must contain at least two numeric variable columns")
}

# BGGM is Bayesian: these settings must be reported with posterior summaries.
settings <- list(
  type = "continuous",
  iterations = iterations,
  prior = "BGGM package default continuous prior; verify in pinned package",
  seed = seed
)
set.seed(settings$seed)
fit <- BGGM::estimate(Y = as.matrix(data), type = settings$type, iter = settings$iterations)
summary_fit <- summary(fit)
if (is.null(summary_fit$summary)) {
  stop("BGGM summary did not expose a summary table; inspect the pinned API")
}
posterior <- as.data.frame(summary_fit$summary)
if (nrow(posterior) == 0L) stop("BGGM returned no posterior edge summaries")
posterior$method <- "BGGM"
posterior$analysis_type <- "posterior_edge_summary"
posterior$prior <- settings$prior
posterior$iterations <- settings$iterations
posterior$seed <- settings$seed
utils::write.csv(posterior, output_path, row.names = FALSE)
capture.output(utils::sessionInfo(), file = paste0(output_path, ".sessionInfo.txt"))
