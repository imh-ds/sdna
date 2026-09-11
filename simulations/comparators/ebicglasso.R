#!/usr/bin/env Rscript

# EBICglasso / bootnet comparator.
# Usage: Rscript ebicglasso.R input.csv output.csv [n_boots] [seed]

required <- c(qgraph = "1.9.8", bootnet = "1.6")
for (pkg in names(required)) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    stop(sprintf("Install pinned package %s==%s before running this comparator", pkg, required[[pkg]]))
  }
  if (as.character(utils::packageVersion(pkg)) != required[[pkg]]) {
    stop(sprintf("Package %s must be version %s (found %s)", pkg, required[[pkg]], utils::packageVersion(pkg)))
  }
}

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2L) {
  stop("Usage: Rscript ebicglasso.R input.csv output.csv [n_boots] [seed]")
}
input_path <- args[[1L]]
output_path <- args[[2L]]
n_boots <- if (length(args) >= 3L) as.integer(args[[3L]]) else 0L
seed <- if (length(args) >= 4L) as.integer(args[[4L]]) else 20260910L
if (is.na(n_boots) || n_boots < 0L) stop("n_boots must be a non-negative integer")
if (is.na(seed)) stop("seed must be an integer")
set.seed(seed)
data <- utils::read.csv(input_path, check.names = FALSE)
if (ncol(data) < 2L || any(!vapply(data, is.numeric, logical(1)))) {
  stop("input.csv must contain at least two numeric variable columns")
}

network <- bootnet::estimateNetwork(data, default = "EBICglasso")
graph <- network$graph
if (is.null(graph)) stop("bootnet did not return an EBICglasso graph")
edge_indices <- which(upper.tri(graph), arr.ind = TRUE)
result <- data.frame(
  method = "bootnet_ebicglasso",
  analysis_type = "network_estimation",
  edge = sprintf("%d-%d", edge_indices[, 1], edge_indices[, 2]),
  node_i = edge_indices[, 1],
  node_j = edge_indices[, 2],
  estimate = graph[edge_indices],
  lower = NA_real_,
  upper = NA_real_,
  statistic = NA_real_,
  prior = NA_character_,
  seed = seed,
  bootstrap_replicates = n_boots,
  stringsAsFactors = FALSE
)

# These are intentionally separate analyses. Nonparametric edge bootstrap
# estimates edge uncertainty; case-dropping evaluates centrality stability.
if (n_boots > 0L) {
  nonparametric <- bootnet::bootnet(network, nBoots = n_boots, type = "nonparametric")
  saveRDS(nonparametric, paste0(output_path, ".nonparametric.rds"))
  case_dropping <- bootnet::bootnet(network, nBoots = n_boots, type = "case")
  saveRDS(case_dropping, paste0(output_path, ".case_dropping_centrality.rds"))
}
utils::write.csv(result, output_path, row.names = FALSE)
capture.output(utils::sessionInfo(), file = paste0(output_path, ".sessionInfo.txt"))
