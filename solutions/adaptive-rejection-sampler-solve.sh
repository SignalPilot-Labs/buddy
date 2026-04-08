#!/bin/bash
set -e

# Solution for adaptive-rejection-sampler challenge
# Implements Adaptive Rejection Sampling (ARS) per Gilks & Wild (1992) in R

# Install R if not available
if ! command -v Rscript &>/dev/null; then
    apt-get update -qq
    apt-get install -y -qq r-base
fi

# Write the main ARS implementation to /app/ars.R
cat > /app/ars.R << 'REOF'
# Adaptive Rejection Sampler
# Reference: Gilks, W. R., & Wild, P. (1992). Adaptive rejection sampling for
# Gibbs sampling. Journal of the Royal Statistical Society: Series C
# (Applied Statistics), 41(2), 337-348.

# ---- Constants ----------------------------------------------------------------

MAX_HULL_POINTS <- 200L
LOG_CONCAVITY_TOL <- 1e-10
MIN_INITIAL_POINTS <- 2L
MAX_REJECTION_ITERATIONS <- 1e6L

# ---- Input validation --------------------------------------------------------

validate_inputs <- function(log_f, initial_points, n, lower, upper) {
    if (!is.function(log_f)) {
        stop("log_f must be a function")
    }
    if (!is.numeric(initial_points) || length(initial_points) < MIN_INITIAL_POINTS) {
        stop("initial_points must be a numeric vector with at least 2 elements")
    }
    if (!is.numeric(n) || length(n) != 1L || n < 1L || n != floor(n)) {
        stop("n must be a positive integer")
    }
    if (!is.numeric(lower) || !is.numeric(upper) || length(lower) != 1L || length(upper) != 1L) {
        stop("lower and upper must be single numeric values")
    }
    if (lower >= upper) {
        stop("lower bound must be strictly less than upper bound")
    }
    pts_in_domain <- initial_points[initial_points > lower & initial_points < upper]
    if (length(pts_in_domain) < MIN_INITIAL_POINTS) {
        stop("At least 2 initial_points must lie strictly inside (lower, upper)")
    }
    invisible(NULL)
}

# ---- Hull construction -------------------------------------------------------

# Evaluate log-density at abscissae; returns sorted data frame
build_abscissae <- function(log_f, xs) {
    xs <- sort(unique(xs))
    ys <- log_f(xs)
    if (any(!is.finite(ys))) {
        stop("log_f returned non-finite values at initial_points")
    }
    data.frame(x = xs, lf = ys)
}

# Compute derivative of log-density via finite differences
compute_derivatives <- function(ab) {
    n <- nrow(ab)
    dlf <- numeric(n)
    # Central differences for interior points
    if (n >= 3L) {
        for (i in seq(2L, n - 1L)) {
            dlf[i] <- (ab$lf[i + 1L] - ab$lf[i - 1L]) / (ab$x[i + 1L] - ab$x[i - 1L])
        }
    }
    # Forward difference at left end
    dlf[1L] <- (ab$lf[2L] - ab$lf[1L]) / (ab$x[2L] - ab$x[1L])
    # Backward difference at right end
    dlf[n] <- (ab$lf[n] - ab$lf[n - 1L]) / (ab$x[n] - ab$x[n - 1L])
    dlf
}

# Check log-concavity: slopes must be non-increasing
check_log_concavity <- function(dlf) {
    diffs <- diff(dlf)
    if (any(diffs > LOG_CONCAVITY_TOL)) {
        stop(
            "Density is not log-concave: slopes are increasing at some abscissae. ",
            "ARS requires a log-concave target density."
        )
    }
    invisible(NULL)
}

# Compute intersection x-coordinates of adjacent tangent lines
compute_intersections <- function(ab, dlf, lower, upper) {
    n <- nrow(ab)
    # z[i] = intersection of tangent at x[i] and tangent at x[i+1]
    # Line at x[i]: lf[i] + dlf[i] * (x - x[i])
    # Intersection: lf[i] + dlf[i]*(z - x[i]) = lf[j] + dlf[j]*(z - x[j])
    z <- numeric(n + 1L)
    z[1L] <- lower
    z[n + 1L] <- upper
    for (i in seq_len(n - 1L)) {
        j <- i + 1L
        if (abs(dlf[i] - dlf[j]) < 1e-14) {
            # Parallel tangents — pick midpoint
            z[i + 1L] <- (ab$x[i] + ab$x[j]) / 2.0
        } else {
            z[i + 1L] <- (ab$lf[j] - ab$lf[i] - ab$x[j] * dlf[j] + ab$x[i] * dlf[i]) /
                         (dlf[i] - dlf[j])
        }
    }
    z
}

# Evaluate upper hull (piecewise linear envelope on log scale) at point x_new
upper_hull_at <- function(x_new, ab, dlf, z) {
    n <- nrow(ab)
    # Find which segment x_new falls in
    seg <- findInterval(x_new, z, rightmost.closed = TRUE)
    seg <- pmax(1L, pmin(seg, n))
    ab$lf[seg] + dlf[seg] * (x_new - ab$x[seg])
}

# Evaluate lower hull (squeezing function on log scale) at point x_new
lower_hull_at <- function(x_new, ab) {
    n <- nrow(ab)
    if (n < 2L) return(-Inf)
    # Find the interval [x[i], x[i+1]] containing x_new
    idx <- findInterval(x_new, ab$x)
    idx <- pmax(1L, pmin(idx, n - 1L))
    # Linear interpolation between adjacent abscissae
    i <- idx
    j <- idx + 1L
    w <- (x_new - ab$x[i]) / (ab$x[j] - ab$x[i])
    (1.0 - w) * ab$lf[i] + w * ab$lf[j]
}

# ---- Envelope sampling -------------------------------------------------------

# Compute normalising weights for piecewise exponential upper hull
compute_hull_weights <- function(ab, dlf, z) {
    n <- nrow(ab)
    weights <- numeric(n)
    for (i in seq_len(n)) {
        h_zi  <- ab$lf[i] + dlf[i] * (z[i]     - ab$x[i])
        h_zi1 <- ab$lf[i] + dlf[i] * (z[i + 1L] - ab$x[i])
        if (abs(dlf[i]) < 1e-14) {
            weights[i] <- exp(h_zi) * (z[i + 1L] - z[i])
        } else {
            weights[i] <- (exp(h_zi1) - exp(h_zi)) / dlf[i]
        }
    }
    # Guard against numerical issues
    weights <- pmax(weights, 0.0)
    weights
}

# Sample one point from the piecewise exponential upper hull
sample_from_hull <- function(ab, dlf, z, weights) {
    n <- nrow(ab)
    probs <- weights / sum(weights)
    seg <- sample.int(n, size = 1L, prob = probs)
    # Inverse CDF within the chosen segment (exponential piece)
    u <- stats::runif(1L)
    h_lo <- ab$lf[seg] + dlf[seg] * (z[seg] - ab$x[seg])
    width <- z[seg + 1L] - z[seg]
    if (abs(dlf[seg]) < 1e-14) {
        x_star <- z[seg] + u * width
    } else {
        x_star <- z[seg] + log(1.0 + u * dlf[seg] * weights[seg] / exp(h_lo)) / dlf[seg]
    }
    x_star
}

# ---- ARS state update --------------------------------------------------------

update_hull <- function(ab, dlf, z, x_new, log_f, lower, upper) {
    new_lf <- log_f(x_new)
    if (!is.finite(new_lf)) {
        return(list(ab = ab, dlf = dlf, z = z))
    }
    ab_new <- rbind(ab, data.frame(x = x_new, lf = new_lf))
    ab_new <- ab_new[order(ab_new$x), ]
    dlf_new <- compute_derivatives(ab_new)
    check_log_concavity(dlf_new)
    z_new <- compute_intersections(ab_new, dlf_new, lower, upper)
    list(ab = ab_new, dlf = dlf_new, z = z_new)
}

# ---- Main ARS function -------------------------------------------------------

#' Adaptive Rejection Sampler
#'
#' @param f         Density function (possibly unnormalized, vectorized).
#'                  May be a log-density when log = TRUE.
#' @param initial_points  Numeric vector of >= 2 starting abscissae inside domain.
#' @param n         Number of samples to draw.
#' @param lower     Left bound of support (default -Inf).
#' @param upper     Right bound of support (default +Inf).
#' @param log       If TRUE, f is already the log-density. Default FALSE.
#' @return Numeric vector of length n drawn from the target density.
ars <- function(f, initial_points, n, lower = -Inf, upper = Inf, log = FALSE) {
    n <- as.integer(n)
    validate_inputs(f, initial_points, n, lower, upper)

    # Build log-density wrapper
    log_f <- if (log) f else function(x) base::log(f(x))

    # Restrict initial points to open domain
    pts <- initial_points[initial_points > lower & initial_points < upper]
    pts <- sort(unique(pts))

    # Initialise abscissae and derivatives
    ab   <- build_abscissae(log_f, pts)
    dlf  <- compute_derivatives(ab)
    check_log_concavity(dlf)
    z    <- compute_intersections(ab, dlf, lower, upper)

    samples <- numeric(n)
    collected <- 0L
    iterations <- 0L

    while (collected < n) {
        iterations <- iterations + 1L
        if (iterations > MAX_REJECTION_ITERATIONS) {
            stop("ARS exceeded maximum iterations without collecting enough samples.")
        }

        # Limit hull size to avoid excessive memory use
        if (nrow(ab) < MAX_HULL_POINTS) {
            weights <- compute_hull_weights(ab, dlf, z)
            x_star  <- sample_from_hull(ab, dlf, z, weights)
        } else {
            # Fallback: rejection from bounding box when hull is large
            x_star <- stats::runif(1L, lower, upper)
        }

        u_sq  <- stats::runif(1L)
        l_val <- lower_hull_at(x_star, ab)
        u_val <- upper_hull_at(x_star, ab, dlf, z)

        # Squeezing test (cheap, no log_f evaluation)
        if (log(u_sq) <= l_val - u_val) {
            collected <- collected + 1L
            samples[collected] <- x_star
        } else {
            # Rejection test with true log-density
            lf_star <- log_f(x_star)
            accepted <- is.finite(lf_star) && log(u_sq) <= lf_star - u_val

            # Update hull with new point regardless of acceptance
            if (nrow(ab) < MAX_HULL_POINTS) {
                result <- update_hull(ab, dlf, z, x_star, log_f, lower, upper)
                ab  <- result$ab
                dlf <- result$dlf
                z   <- result$z
            }

            if (accepted) {
                collected <- collected + 1L
                samples[collected] <- x_star
            }
        }
    }

    samples
}

# ---- Test helpers ------------------------------------------------------------

run_ks_test <- function(samples, ref_cdf, name, mean_ref, sd_ref) {
    ks  <- stats::ks.test(samples, ref_cdf)
    m   <- mean(samples)
    s   <- stats::sd(samples)
    passed <- ks$p.value > 0.001
    result <- if (passed) "PASS" else "FAIL"
    cat(sprintf("%s: %s (mean=%.4f, sd=%.4f, ks.pvalue=%.4f)\n",
                name, result, m, s, ks$p.value))
    invisible(passed)
}

# ---- Test function -----------------------------------------------------------

test <- function() {
    set.seed(42L)
    cat("Running ARS formal tests\n")
    cat(strrep("-", 60L), "\n")

    # --- Test 1: Standard normal N(0,1) ---
    samples_norm <- ars(
        f               = function(x) stats::dnorm(x, mean = 0.0, sd = 1.0),
        initial_points  = c(-1.5, 0.0, 1.5),
        n               = 10000L,
        lower           = -8.0,
        upper           =  8.0
    )
    run_ks_test(samples_norm,
                function(x) stats::pnorm(x, mean = 0.0, sd = 1.0),
                "NORMAL_N(0,1)",
                mean_ref = 0.0, sd_ref = 1.0)

    # Write normal samples file
    write(samples_norm, file = "/app/normal_samples.txt", ncolumns = 1L)

    # --- Test 2: Standard exponential Exp(1) ---
    samples_exp <- ars(
        f               = function(x) stats::dexp(x, rate = 1.0),
        initial_points  = c(0.5, 1.0, 2.0),
        n               = 2000L,
        lower           = 0.0,
        upper           = 30.0
    )
    run_ks_test(samples_exp,
                function(x) stats::pexp(x, rate = 1.0),
                "EXPONENTIAL_Exp(1)",
                mean_ref = 1.0, sd_ref = 1.0)

    write(samples_exp, file = "/app/exponential_samples.txt", ncolumns = 1L)

    # --- Test 3: Gamma(3, 1) ---
    samples_gamma <- ars(
        f               = function(x) stats::dgamma(x, shape = 3.0, rate = 1.0),
        initial_points  = c(1.0, 2.5, 5.0),
        n               = 2000L,
        lower           = 0.0,
        upper           = 30.0
    )
    run_ks_test(samples_gamma,
                function(x) stats::pgamma(x, shape = 3.0, rate = 1.0),
                "GAMMA_Gamma(3,1)",
                mean_ref = 3.0, sd_ref = sqrt(3.0))

    # --- Test 4: Input validation - negative n ---
    val_neg_n <- tryCatch({
        ars(stats::dnorm, c(-1.0, 0.0, 1.0), n = -5L)
        "FAIL"
    }, error = function(e) "PASS")
    cat(sprintf("VALIDATE_NEGATIVE_N: %s\n", val_neg_n))

    # --- Test 5: Input validation - reversed bounds ---
    val_bounds <- tryCatch({
        ars(stats::dnorm, c(-1.0, 0.0, 1.0), n = 10L, lower = 5.0, upper = -5.0)
        "FAIL"
    }, error = function(e) "PASS")
    cat(sprintf("VALIDATE_REVERSED_BOUNDS: %s\n", val_bounds))

    # --- Test 6: Log-concavity check with bimodal density ---
    bimodal <- function(x) {
        0.5 * stats::dnorm(x, mean = -2.0, sd = 1.0) +
        0.5 * stats::dnorm(x, mean =  2.0, sd = 1.0)
    }
    val_concave <- tryCatch({
        ars(bimodal, c(-3.0, 0.0, 3.0), n = 50L, lower = -10.0, upper = 10.0)
        "FAIL"
    }, error = function(e) "PASS")
    cat(sprintf("LOG_CONCAVITY_CHECK: %s\n", val_concave))

    # --- Test 7: Log-scale input ---
    samples_log <- ars(
        f               = function(x) stats::dnorm(x, mean = 0.0, sd = 1.0, log = TRUE),
        initial_points  = c(-1.0, 0.0, 1.0),
        n               = 1000L,
        lower           = -6.0,
        upper           =  6.0,
        log             = TRUE
    )
    run_ks_test(samples_log,
                function(x) stats::pnorm(x, mean = 0.0, sd = 1.0),
                "NORMAL_LOG_INPUT",
                mean_ref = 0.0, sd_ref = 1.0)

    cat(strrep("-", 60L), "\n")
    cat("Tests complete.\n")
    invisible(NULL)
}

# ---- Run if executed directly ------------------------------------------------

if (!interactive()) {
    test()
}
REOF

echo "ars.R written to /app/ars.R"

# Run the test function to generate sample files and verify correctness
echo "Running ARS tests..."
Rscript /app/ars.R

echo "Done. Sample files written:"
ls -lh /app/normal_samples.txt /app/exponential_samples.txt 2>/dev/null || true
