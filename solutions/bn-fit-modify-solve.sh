#!/bin/bash
set -e

# Install bnlearn R package
R -e 'if (!require("bnlearn", quietly = TRUE)) install.packages("bnlearn", repos = "https://cloud.r-project.org")'

cat > /tmp/modify_bn.R << 'EOF'
library(bnlearn)

# Load data
samples <- read.csv('/app/bn_sample_10k.csv')
samples[] <- lapply(samples, as.numeric)

# Learn graph structure using hill-climbing
learned_dag <- hc(samples)

# The true DAG has 6 edges. Apply directionality rules from the prompt:
#   - U has no parents
#   - For other ambiguous edges: node with letter later in alphabet is the parent
final_directed_edges <- list()

for (i in seq_len(nrow(learned_dag$arcs))) {
  from_node <- learned_dag$arcs[i, "from"]
  to_node   <- learned_dag$arcs[i, "to"]

  if (from_node == "U") {
    final_directed_edges[[length(final_directed_edges) + 1]] <- c(from_node, to_node)
  } else if (to_node == "U") {
    # Reverse so U is always the parent (no parents for U)
    final_directed_edges[[length(final_directed_edges) + 1]] <- c(to_node, from_node)
  } else {
    # Parent is the node with the letter that comes later in the alphabet
    if (from_node > to_node) {
      final_directed_edges[[length(final_directed_edges) + 1]] <- c(from_node, to_node)
    } else {
      final_directed_edges[[length(final_directed_edges) + 1]] <- c(to_node, from_node)
    }
  }
}

edge_matrix <- do.call(rbind, final_directed_edges)

# Build the corrected DAG
final_dag <- empty.graph(colnames(samples))
arcs(final_dag) <- edge_matrix

# Fit Bayesian Network parameters (linear Gaussian) to the corrected DAG
fitted_bn <- bn.fit(final_dag, data = samples)

# Save the learned DAG edges to /app/learned_dag.csv
write.csv(arcs(fitted_bn), "/app/learned_dag.csv", row.names = FALSE)

# --- Causal intervention: do(Y = 0) ---
# Remove all incoming edges to Y (in this DAG: U -> Y)
original_structure <- bn.net(fitted_bn)
intervened_structure <- drop.arc(original_structure, from = "U", to = "Y")

# Save the intervened DAG edges
write.csv(arcs(intervened_structure), "/app/intervened_dag.csv", row.names = FALSE)

# Carry over all fitted parameters then override Y's distribution
params_list <- as.list(fitted_bn)
dist_list <- list()
for (node_name in names(params_list)) {
  dist_list[[node_name]] <- list(
    coef = params_list[[node_name]]$coefficients,
    sd   = params_list[[node_name]]$sd
  )
}

# Fix Y = 0 with near-zero variance (hard intervention)
dist_list$Y$coef <- c("(Intercept)" = 0)
dist_list$Y$sd   <- 1e-9

# Build the intervened BN with modified parameters
intervened_bn <- custom.fit(intervened_structure, dist = dist_list)

# Sample 10k points from the intervened BN
intervened_samples <- rbn(intervened_bn, n = 10000)

write.csv(intervened_samples, "/app/final_bn_sample.csv", row.names = FALSE)

cat("Done. Learned DAG edges:\n")
print(arcs(fitted_bn))
cat("Intervened DAG edges:\n")
print(arcs(intervened_structure))
cat("Fitted BN parameters:\n")
print(fitted_bn)
EOF

Rscript /tmp/modify_bn.R
