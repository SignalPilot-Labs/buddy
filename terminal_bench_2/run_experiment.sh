#!/usr/bin/env bash
# Runs a terminal-bench experiment fork against one or more tasks.
# Usage: ./run_experiment.sh <fork_name> <task1> [task2 ...]
# Example: ./run_experiment.sh caveman hello-world
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
JOBS_DIR="jobs"
SYMLINK_BASE="/tmp/tb2"
MODEL="anthropic/claude-opus-4-6"
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

if [[ -z "${DAYTONA_API_KEY:-}" ]]; then
    echo "Error: DAYTONA_API_KEY is not set." >&2
    exit 1
fi

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
    TASK_PATHS+=("${TERMINAL_BENCH_2_DIR}/${TASKS_DIR}/${TASK}")
done

# ---------------------------------------------------------------------------
# Setup caveman fixture (idempotent)
# ---------------------------------------------------------------------------
"${TERMINAL_BENCH_2_DIR}/setup_caveman_fixture.sh"

# ---------------------------------------------------------------------------
# Point per-fork symlink at the chosen fork (avoids race conditions)
# ---------------------------------------------------------------------------
SYMLINK_PARENT="${SYMLINK_BASE}-${FORK_NAME}"
SYMLINK_PATH="${SYMLINK_PARENT}/terminal_bench"
mkdir -p "${SYMLINK_PARENT}"
ln -sfn "${FORK_DIR}" "${SYMLINK_PATH}"
echo "Symlink: ${SYMLINK_PATH} -> ${FORK_DIR}"

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
    "--agent-import-path" "terminal_bench.agent:AutoFynAgent"
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

PYTHONPATH="${SYMLINK_PARENT}" "${HARBOR_BIN}" "${HARBOR_ARGS[@]}"

echo ""
echo "Job output directory: ${OUTPUT_DIR}/${JOB_NAME}"
