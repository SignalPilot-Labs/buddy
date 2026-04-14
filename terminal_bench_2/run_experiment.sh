#!/usr/bin/env bash
# Runs a terminal-bench experiment fork against one or more tasks.
# Usage: ./run_experiment.sh <fork_name> <task1> [task2 ...]
# Example: ./run_experiment.sh caveman fix-git
# Example: ./run_experiment.sh lean write-compressor overfull-hbox
set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HARBOR_BIN="/home/agentuser/.local/bin/harbor"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TERMINAL_BENCH_2_DIR="${REPO_DIR}/terminal_bench_2"
TASKS_DIR="tasks/tasks-run2"
FORKS_PREFIX="autofyn_agent_"
ADAPTERS_DIR="${TERMINAL_BENCH_2_DIR}/adapters"
JOBS_DIR="jobs"
SYMLINK_BASE="/tmp/tb2"
MODEL="anthropic/claude-opus-4-5"
ENVIRONMENT="daytona"
CONCURRENCY=1

# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------
if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <fork_name> <task1> [task2 ...]" >&2
    exit 1
fi

FORK_NAME="$1"
shift
TASKS=("$@")

if [[ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]]; then
    echo "Error: CLAUDE_CODE_OAUTH_TOKEN is not set." >&2
    exit 1
fi

FORK_DIR="${TERMINAL_BENCH_2_DIR}/${FORKS_PREFIX}${FORK_NAME}"
if [[ ! -d "${FORK_DIR}" ]]; then
    echo "Error: fork directory not found: ${FORK_DIR}" >&2
    exit 1
fi

TASK_PATHS=()
for TASK in "${TASKS[@]}"; do
    TASK_DIR="${TERMINAL_BENCH_2_DIR}/${TASKS_DIR}/${TASK}"
    if [[ ! -d "${TASK_DIR}" ]]; then
        echo "Error: task directory not found: ${TASK_DIR}" >&2
        exit 1
    fi
    TASK_PATHS+=("${TASK_DIR}")
done

# ---------------------------------------------------------------------------
# Setup caveman fixture (idempotent)
# ---------------------------------------------------------------------------
"${TERMINAL_BENCH_2_DIR}/setup_caveman_fixture.sh"

# ---------------------------------------------------------------------------
# Point per-fork symlink at the chosen fork (avoids race conditions).
#
# PYTHONPATH is set to the symlink parent so that `terminal_bench.agent` and
# related fork modules (orchestrator, prompts, constants, etc.) resolve to the
# fork directory.  The harbor binary imports `harbor.cli.main` (not
# `terminal_bench.cli`), so there is no package shadowing conflict.
#
# The adapter (adapters/harbor_agent.py) provides the harbor.BaseInstalledAgent
# interface while delegating to the fork's orchestrator for business logic.
# ---------------------------------------------------------------------------
SYMLINK_PARENT="${SYMLINK_BASE}-${FORK_NAME}"
SYMLINK_PATH="${SYMLINK_PARENT}/terminal_bench"
mkdir -p "${SYMLINK_PARENT}"
ln -sfn "${FORK_DIR}" "${SYMLINK_PATH}"
echo "Symlink: ${SYMLINK_PATH} -> ${FORK_DIR}"

# The adapters directory must also be on PYTHONPATH so harbor can import
# adapters.harbor_agent:AutoFynAgent
FULL_PYTHONPATH="${SYMLINK_PARENT}:${ADAPTERS_DIR}"

# ---------------------------------------------------------------------------
# Build and run the harbor command
# ---------------------------------------------------------------------------
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
JOB_NAME="${FORK_NAME}-${TIMESTAMP}"
OUTPUT_DIR="${TERMINAL_BENCH_2_DIR}/${JOBS_DIR}"

HARBOR_ARGS=(
    "run"
)

for TASK_PATH in "${TASK_PATHS[@]}"; do
    HARBOR_ARGS+=("-p" "${TASK_PATH}")
done

HARBOR_ARGS+=(
    "--agent-import-path" "harbor_agent:AutoFynAgent"
    "-m" "${MODEL}"
    "-e" "${ENVIRONMENT}"
    "-y"
    "--ae" "CLAUDE_CODE_OAUTH_TOKEN=${CLAUDE_CODE_OAUTH_TOKEN}"
    "-o" "${OUTPUT_DIR}"
    "--job-name" "${JOB_NAME}"
    "-n" "${CONCURRENCY}"
)

echo "Running harbor job: ${JOB_NAME}"
echo "Tasks: ${TASKS[*]}"
echo "Fork:  ${FORK_NAME}"
echo ""

PYTHONPATH="${FULL_PYTHONPATH}" "${HARBOR_BIN}" "${HARBOR_ARGS[@]}"

echo ""
echo "Job output directory: ${OUTPUT_DIR}/${JOB_NAME}"
